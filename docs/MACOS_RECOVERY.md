# Recuperar archivos borrados en macOS

**Contexto**: Archivos eliminados durante refactor (local-data, .env, código modificado).

---

## Opciones de recuperación

### 1. Time Machine (si tienes backups)
```bash
# Abrir Time Machine
open -a "Time Machine"

# O desde Terminal, navegar a la carpeta y usar "Enter Time Machine"
# Buscar: news-analyzer/app/
```

**Pasos**:
1. Abrir Finder → ir a la carpeta del proyecto
2. Clic en el icono de Time Machine (barra de menú)
3. Navegar al momento anterior al borrado
4. Seleccionar `local-data`, `.env`, o la carpeta `RAG-Enterprise`
5. "Restaurar"

### 2. Papelera (si no se vació)
- Los archivos borrados con `rm` o `git rm` **no** van a la Papelera
- Solo los eliminados desde Finder o con "mover a papelera" pueden recuperarse

### 3. Software de recuperación de datos
Para archivos borrados con `rm`/`git rm` (bypass de Papelera):

| Herramienta | Uso |
|-------------|-----|
| **Disk Drill** | Escaneo de disco, recuperación por tipo de archivo |
| **PhotoRec** (gratis) | `brew install testdisk` → `photorec` |
| **Data Rescue** | Comercial, buena reputación |

**Importante**: Dejar de escribir en el disco aumenta la probabilidad de recuperación. Los datos pueden estar marcados como libres pero aún no sobrescritos.

### 4. Git (solo para código versionado)
- `local-data` y `.env` estaban en `.gitignore` → **no recuperables** por Git
- Código no commiteado en el submodule → **perdido**

### 5. Cursor / IDE local history
- Algunos IDEs guardan historial local de archivos
- Revisar: Cursor → File → Local History (si está habilitado)

---

## Prevención futura

1. **Backups regulares** de `local-data` y `.env`
2. **Regla no-delete-without-auth** ya creada en `.cursor/rules/`
3. Antes de refactors: `cp -r local-data local-data.backup`
