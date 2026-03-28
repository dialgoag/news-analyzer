#!/usr/bin/env python3
"""
Repara symlinks en uploads/: uno a uno, comprobando si el destino existe.

- Si el archivo destino existe → no se hace nada.
- Si no existe y el nombre encaja en prefijo duplicado {8hex}_{8hex}_… →
  - si el fichero con nombre doble existe en ese directorio → renombrar a un solo prefijo y actualizar el symlink;
  - si ya existe el fichero con un solo prefijo → solo actualizar el symlink;
  - si hay colisión (existen ambos) → avisar y no tocar.
- Cualquier otro destino roto → se deja como está.

Usage:
  python cleanup_duplicate_processed_prefix.py [--report] [--apply] [--uploads-dir PATH]

  --report   Solo estadísticas: symlinks totales, rotos, con doble prefijo en el destino.
  --delete-redundant-double-prefix --apply  Borrar copia con doble prefijo si el nombre
             normalizado existe y SHA256 coincide; actualiza symlinks (--local-data-root).
  --local-data-root  En el host: carpeta local-data (mapea /app/inbox y /app/uploads del contenedor).

  (sin --report) revisión / reparación en dry-run; --apply aplica cambios.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import re
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

RE_DUPLICATE_PREFIX = re.compile(r"^([0-9a-f]{8})_\1_(.+)$")


def strip_repeated_hash_prefixes(basename: str) -> str:
    """Quita prefijos hex duplicados adyacentes hasta estabilizar."""
    name = basename
    while True:
        m = RE_DUPLICATE_PREFIX.match(name)
        if not m:
            return name
        name = f"{m.group(1)}_{m.group(2)}"


def basename_has_double_prefix(basename: str) -> bool:
    """True si el nombre incluye al menos un par duplicado {8hex}_{8hex}_… adyacente."""
    return strip_repeated_hash_prefixes(basename) != basename


def resolve_symlink_target(symlink_path: str) -> str:
    t = os.readlink(symlink_path)
    if os.path.isabs(t):
        return t
    return os.path.normpath(os.path.join(os.path.dirname(symlink_path), t))


def inbox_processed_container_path(basename: str) -> str:
    """Ruta que usan los symlinks dentro del contenedor (volúmenes montados)."""
    return "/app/inbox/processed/" + basename


def preferred_symlink_target(
    physical_file: str, local_data_root: Optional[str]
) -> str:
    """Destino del symlink: ruta Docker /app/... en host, o absoluta local si no hay mapeo."""
    if local_data_root:
        return inbox_processed_container_path(os.path.basename(physical_file))
    return os.path.abspath(physical_file)


def physical_symlink_target(target: str, local_data_root: Optional[str]) -> str:
    """
    En el host, los symlinks suelen apuntar a /app/inbox/... (Docker).
    Si local_data_root es la carpeta local-data del proyecto, mapéala a disco local.
    """
    if not local_data_root:
        return target
    root = os.path.abspath(local_data_root)
    if target.startswith("/app/inbox/"):
        return os.path.normpath(
            os.path.join(root, "inbox", target[len("/app/inbox/") :])
        )
    if target.startswith("/app/inbox"):
        return os.path.normpath(os.path.join(root, "inbox"))
    if target.startswith("/app/uploads/"):
        return os.path.normpath(
            os.path.join(root, "uploads", target[len("/app/uploads/") :])
        )
    return target


def try_fix_broken_symlink(
    link_path: str, dry_run: bool, local_data_root: Optional[str] = None
) -> str:
    """
    Returns:
      'ok' — destino ya era un archivo válido
      'fixed' — se corrigió (relink y/o rename)
      'not_double_prefix' — roto y no encaja prefijo duplicado; no tocar
      'collision' — conflicto de nombres; no tocar
      'error' — fallo de lectura/IO
    """
    try:
        target = resolve_symlink_target(link_path)
    except OSError as e:
        logger.warning("No se pudo leer symlink %s: %s", link_path, e)
        return "error"

    phys = physical_symlink_target(target, local_data_root)
    entry = os.path.basename(link_path)

    if os.path.exists(phys) and not os.path.isfile(phys):
        logger.info(
            "SALTAR %s → %s (existe pero no es un archivo)",
            entry,
            phys,
        )
        return "not_double_prefix"

    if os.path.isfile(phys):
        logger.info("OK  %s → %s", entry, target)
        return "ok"

    d, b = os.path.split(phys)
    b2 = strip_repeated_hash_prefixes(b)

    logger.info(
        "ROTO %s → %s (no existe o no es archivo)",
        entry,
        phys,
    )

    if b2 == b:
        logger.info(
            "     dejar: el nombre no tiene el patrón {8hex}_{8hex}_… repetido",
        )
        return "not_double_prefix"

    path_double = os.path.join(d, b)
    path_single = os.path.join(d, b2)

    exists_double = os.path.isfile(path_double)
    exists_single = os.path.isfile(path_single)

    if exists_double and exists_single:
        logger.warning(
            "     colisión: existen %s y %s — no se modifica",
            b,
            b2,
        )
        return "collision"

    if exists_double and not exists_single:
        logger.info(
            "     renombrar %s → %s y actualizar symlink",
            b,
            b2,
        )
        if not dry_run:
            os.rename(path_double, path_single)
            os.unlink(link_path)
            os.symlink(
                preferred_symlink_target(path_single, local_data_root), link_path
            )
        else:
            logger.info("     [dry-run] no se renombra ni se actualiza symlink")
        return "fixed"

    if exists_single and not exists_double:
        logger.info(
            "     actualizar symlink → %s (archivo ya con un prefijo)",
            path_single,
        )
        if not dry_run:
            os.unlink(link_path)
            os.symlink(
                preferred_symlink_target(path_single, local_data_root), link_path
            )
        else:
            logger.info("     [dry-run] no se actualiza symlink")
        return "fixed"

    logger.info(
        "     dejar: no hay %s ni %s en %s",
        b,
        b2,
        d,
    )
    return "not_double_prefix"


def collect_symlink_report(
    uploads_dir: str, local_data_root: Optional[str] = None
) -> Dict[str, Any]:
    """
    Cuenta symlinks en uploads_dir: rotos y con basename de destino con doble prefijo.

    Roto = el destino del symlink no es un archivo regular existente.
    Doble prefijo = basename(destino) encaja en reducción por strip_repeated_hash_prefixes.
    """
    total = 0
    broken = 0
    double_prefix = 0
    broken_and_double_prefix = 0
    ok_with_double_prefix = 0
    read_errors = 0

    for name in sorted(os.listdir(uploads_dir)):
        link_path = os.path.join(uploads_dir, name)
        if not os.path.islink(link_path):
            continue
        total += 1
        try:
            target = resolve_symlink_target(link_path)
        except OSError:
            read_errors += 1
            broken += 1
            continue

        phys = physical_symlink_target(target, local_data_root)
        base = os.path.basename(target)
        has_dbl = basename_has_double_prefix(base)
        if has_dbl:
            double_prefix += 1

        is_ok_file = os.path.isfile(phys)
        if is_ok_file and has_dbl:
            ok_with_double_prefix += 1
        if not is_ok_file:
            broken += 1
            if has_dbl:
                broken_and_double_prefix += 1

    return {
        "uploads_dir": uploads_dir,
        "local_data_root": local_data_root,
        "total_symlinks": total,
        "broken": broken,
        "double_prefix_basename": double_prefix,
        "ok_but_double_prefix_basename": ok_with_double_prefix,
        "broken_and_double_prefix": broken_and_double_prefix,
        "read_errors": read_errors,
    }


def print_report(uploads_dir: str, local_data_root: Optional[str] = None) -> int:
    if not os.path.isdir(uploads_dir):
        logger.error("No existe el directorio: %s", uploads_dir)
        return 1
    r = collect_symlink_report(uploads_dir, local_data_root=local_data_root)
    print(f"Directorio: {r['uploads_dir']}")
    if r.get("local_data_root"):
        print(f"Mapeo host (local-data): {os.path.abspath(r['local_data_root'])}")
    print(f"Total symlinks:                 {r['total_symlinks']}")
    print(f"Rotos (destino no es archivo):  {r['broken']}")
    print(f"Destino con doble prefijo (nombre): {r['double_prefix_basename']}")
    print(f"  de ellos, symlink OK (archivo existe): {r['ok_but_double_prefix_basename']}")
    print(f"  de ellos, symlink roto:           {r['broken_and_double_prefix']}")
    if r["read_errors"]:
        print(f"No se pudo leer readlink:       {r['read_errors']}")
    return 0


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_symlinks_pointing_to_basename(uploads_dir: str, target_basename: str) -> List[str]:
    """Symlinks en uploads/ cuyo destino (basename) coincide."""
    out: List[str] = []
    if not os.path.isdir(uploads_dir):
        return out
    for name in os.listdir(uploads_dir):
        link_path = os.path.join(uploads_dir, name)
        if not os.path.islink(link_path):
            continue
        try:
            target = resolve_symlink_target(link_path)
        except OSError:
            continue
        if os.path.basename(target) == target_basename:
            out.append(link_path)
    return out


def run_delete_redundant_double_prefix(
    uploads_dir: str,
    local_data_root: str,
    dry_run: bool,
) -> int:
    """
    Elimina en processed/ el fichero con nombre de doble prefijo cuando ya existe
    el nombre normalizado y el contenido (SHA256) es idéntico. Actualiza symlinks
    que apuntaban al nombre doble para que apunten al canónico.
    """
    root = os.path.abspath(local_data_root)
    processed_dir = os.path.join(root, "inbox", "processed")
    if not os.path.isdir(processed_dir):
        logger.error("No existe processed: %s", processed_dir)
        return 1
    if not os.path.isdir(uploads_dir):
        logger.error("No existe uploads: %s", uploads_dir)
        return 1

    deleted = 0
    skipped_hash_mismatch = 0
    skipped_no_pair = 0

    for fname in sorted(os.listdir(processed_dir)):
        path_double = os.path.join(processed_dir, fname)
        if not os.path.isfile(path_double):
            continue
        if not basename_has_double_prefix(fname):
            continue
        b2 = strip_repeated_hash_prefixes(fname)
        path_single = os.path.join(processed_dir, b2)
        if path_double == path_single:
            continue
        if not os.path.isfile(path_single):
            skipped_no_pair += 1
            continue
        hd = sha256_file(path_double)
        hs = sha256_file(path_single)
        if hd != hs:
            logger.warning(
                "Mismo nombre normalizado pero contenido distinto; no borro: %s",
                fname,
            )
            skipped_hash_mismatch += 1
            continue

        for link_path in find_symlinks_pointing_to_basename(uploads_dir, fname):
            logger.info(
                "Symlink %s: destino %s → %s",
                os.path.basename(link_path),
                fname,
                b2,
            )
            if not dry_run:
                os.unlink(link_path)
                os.symlink(inbox_processed_container_path(b2), link_path)

        logger.info("Eliminar duplicado (mismo contenido): %s", fname)
        if not dry_run:
            os.remove(path_double)
        deleted += 1

    logger.info(
        "Eliminación duplicados: borrados=%d, sin par (solo doble)=%d, hash distinto=%d",
        deleted,
        skipped_no_pair,
        skipped_hash_mismatch,
    )
    return 0


def collect_pointed_basenames(uploads_dir: str) -> set:
    """Basenames de destino de todos los symlinks (string readlink)."""
    out = set()
    for name in os.listdir(uploads_dir):
        link_path = os.path.join(uploads_dir, name)
        if not os.path.islink(link_path):
            continue
        try:
            target = resolve_symlink_target(link_path)
        except OSError:
            continue
        out.add(os.path.basename(target))
    return out


def run_normalize_double_prefix(
    uploads_dir: str,
    local_data_root: str,
    dry_run: bool,
) -> int:
    """
    1) Symlinks cuyo archivo existe y tiene doble prefijo → renombrar + relink a /app/inbox/processed/<nombre>.
    2) Archivos huérfanos en processed/ con doble prefijo → renombrar si no hay colisión.
    3) Re-ejecutar reparación de symlinks rotos (destino con doble prefijo ausente, etc.).
    """
    root = os.path.abspath(local_data_root)
    processed_dir = os.path.join(root, "inbox", "processed")
    if not os.path.isdir(processed_dir):
        logger.error("No existe processed: %s", processed_dir)
        return 1

    renamed_linked = 0
    symlinks_relinked = 0
    renamed_orphan = 0
    skipped_collision = 0

    # --- Fase 1: archivos enlazados con nombre de doble prefijo (agrupado por ruta física) ---
    by_phys: Dict[str, List[str]] = defaultdict(list)
    for name in sorted(os.listdir(uploads_dir)):
        link_path = os.path.join(uploads_dir, name)
        if not os.path.islink(link_path):
            continue
        try:
            target = resolve_symlink_target(link_path)
        except OSError:
            continue
        phys = physical_symlink_target(target, local_data_root)
        if not os.path.isfile(phys):
            continue
        b = os.path.basename(phys)
        if not basename_has_double_prefix(b):
            continue
        by_phys[phys].append(link_path)

    for phys in sorted(by_phys.keys()):
        links = by_phys[phys]
        b = os.path.basename(phys)
        b2 = strip_repeated_hash_prefixes(b)
        new_phys = os.path.join(os.path.dirname(phys), b2)
        if new_phys == phys:
            continue
        if os.path.isfile(new_phys):
            logger.warning(
                "Colisión: existe %s; no renombro el enlazado %s (%d symlink(s))",
                b2,
                b,
                len(links),
            )
            skipped_collision += 1
            continue
        logger.info(
            "Fase1 renombrar + %d symlink(s): %s → %s",
            len(links),
            b,
            b2,
        )
        if not dry_run:
            os.rename(phys, new_phys)
            for link_path in links:
                os.unlink(link_path)
                os.symlink(inbox_processed_container_path(b2), link_path)
        renamed_linked += 1
        symlinks_relinked += len(links)

    # --- Fase 2: huérfanos (ningún symlink apunta a ese basename) ---
    pointed = collect_pointed_basenames(uploads_dir)
    for fname in sorted(os.listdir(processed_dir)):
        old_path = os.path.join(processed_dir, fname)
        if not os.path.isfile(old_path):
            continue
        if not basename_has_double_prefix(fname):
            continue
        if fname in pointed:
            continue
        b2 = strip_repeated_hash_prefixes(fname)
        new_path = os.path.join(processed_dir, b2)
        if new_path == old_path:
            continue
        if os.path.exists(new_path):
            logger.warning(
                "Huérfano: colisión con %s; no renombro %s",
                b2,
                fname,
            )
            skipped_collision += 1
            continue
        logger.info("Fase2 renombrar huérfano: %s → %s", fname, b2)
        if not dry_run:
            os.rename(old_path, new_path)
        renamed_orphan += 1

    # --- Fase 3: reparar symlinks rotos (lógica existente) ---
    stats = {
        "ok": 0,
        "fixed": 0,
        "not_double_prefix": 0,
        "collision": 0,
        "error": 0,
    }
    for name in sorted(os.listdir(uploads_dir)):
        link_path = os.path.join(uploads_dir, name)
        if not os.path.islink(link_path):
            continue
        outcome = try_fix_broken_symlink(
            link_path, dry_run=dry_run, local_data_root=local_data_root
        )
        if outcome in stats:
            stats[outcome] += 1

    logger.info(
        "Normalización: ficheros renombrados (fase1)=%d, symlinks actualizados (fase1)=%d, "
        "huérfanos (fase2)=%d, colisiones_omitidas=%d",
        renamed_linked,
        symlinks_relinked,
        renamed_orphan,
        skipped_collision,
    )
    logger.info(
        "Fase3 reparación symlinks: ok=%d, corregidos=%d, otros=%d, colisiones=%d, errores=%d",
        stats["ok"],
        stats["fixed"],
        stats["not_double_prefix"],
        stats["collision"],
        stats["error"],
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Revisar symlinks en uploads/ y corregir prefijos duplicados cuando el destino falta",
    )
    parser.add_argument(
        "--uploads-dir",
        default=os.environ.get("UPLOAD_DIR", "/app/uploads"),
        help="Directorio de uploads (symlinks hacia processed/; default UPLOAD_DIR o /app/uploads)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Solo imprimir conteos (rotos / doble prefijo) y salir",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplicar renombres y nuevos symlinks",
    )
    parser.add_argument(
        "--local-data-root",
        default=os.environ.get("LOCAL_DATA_ROOT"),
        metavar="PATH",
        help="Carpeta local-data del proyecto (host): resuelve /app/inbox → PATH/inbox",
    )
    parser.add_argument(
        "--normalize-double-prefix",
        action="store_true",
        help=(
            "Renombrar ficheros con doble prefijo en processed/, actualizar symlinks, "
            "huérfanos y reparar rotos (requiere --local-data-root en el host)"
        ),
    )
    parser.add_argument(
        "--delete-redundant-double-prefix",
        action="store_true",
        help=(
            "Eliminar ficheros con doble prefijo si existe el nombre normalizado y "
            "SHA256 coincide; actualizar symlinks (requiere --local-data-root)"
        ),
    )
    args = parser.parse_args()

    uploads_dir = args.uploads_dir
    local_root = os.path.abspath(args.local_data_root) if args.local_data_root else None

    if args.report:
        return print_report(uploads_dir, local_data_root=local_root)

    if args.delete_redundant_double_prefix:
        if not local_root:
            logger.error(
                "--delete-redundant-double-prefix requiere --local-data-root"
            )
            return 1
        dry_run = not args.apply
        if dry_run:
            logger.info(
                "DRY-RUN eliminación — sin borrar. Usa --apply para ejecutar."
            )
        return run_delete_redundant_double_prefix(
            uploads_dir, local_root, dry_run=dry_run
        )

    if args.normalize_double_prefix:
        if not local_root:
            logger.error(
                "--normalize-double-prefix requiere --local-data-root (carpeta local-data)"
            )
            return 1
        dry_run = not args.apply
        if dry_run:
            logger.info(
                "MODO DRY-RUN normalización — sin cambios. Usa --apply para ejecutar."
            )
        if not os.path.isdir(uploads_dir):
            logger.error("No existe el directorio: %s", uploads_dir)
            return 1
        return run_normalize_double_prefix(uploads_dir, local_root, dry_run=dry_run)

    dry_run = not args.apply

    if dry_run:
        logger.info("MODO DRY-RUN — sin cambios en disco. Usa --apply para ejecutar.")

    if not os.path.isdir(uploads_dir):
        logger.error("No existe el directorio: %s", uploads_dir)
        return 1

    stats = {
        "ok": 0,
        "fixed": 0,
        "not_double_prefix": 0,
        "collision": 0,
        "error": 0,
    }
    symlinks_seen = 0

    for name in sorted(os.listdir(uploads_dir)):
        link_path = os.path.join(uploads_dir, name)
        if not os.path.islink(link_path):
            continue
        symlinks_seen += 1
        outcome = try_fix_broken_symlink(
            link_path, dry_run=dry_run, local_data_root=local_root
        )
        if outcome in stats:
            stats[outcome] += 1

    logger.info("Symlinks revisados: %d", symlinks_seen)
    logger.info(
        "Resumen: ok=%d, corregidos=%d, rotos_otros=%d, colisiones=%d, errores=%d",
        stats["ok"],
        stats["fixed"],
        stats["not_double_prefix"],
        stats["collision"],
        stats["error"],
    )
    if dry_run:
        logger.info("Re-ejecuta con --apply para aplicar.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
