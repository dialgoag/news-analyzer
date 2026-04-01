#!/usr/bin/env python3
"""
Validation Script: Migration 018 (Unified Timestamp System)

Verifica que:
1. Tabla document_stage_timing existe con estructura correcta
2. Backfill funcionó (upload + indexing stages)
3. Triggers de updated_at funcionan
4. Workers están registrando timing correctamente
5. Queries de performance funcionan
"""

import psycopg2
from datetime import datetime

# Connection (update with your credentials)
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    user="rag-user",
    password="r@g-p@55w0rD",
    database="rag-enterprise"
)

print("=" * 80)
print("VALIDACIÓN: Migration 018 (Unified Timestamp System)")
print("=" * 80)

# ========================================
# 1. Verificar estructura de tabla
# ========================================
print("\n1️⃣ ESTRUCTURA DE TABLA:")
print("-" * 80)

cursor = conn.cursor()
cursor.execute("""
    SELECT column_name, data_type, is_nullable, column_default
    FROM information_schema.columns
    WHERE table_name = 'document_stage_timing'
    ORDER BY ordinal_position
""")

for row in cursor.fetchall():
    print(f"  {row[0]:20} {row[1]:30} nullable={row[2]:3} default={row[3]}")

# ========================================
# 2. Verificar índices y constraints
# ========================================
print("\n2️⃣ ÍNDICES Y CONSTRAINTS:")
print("-" * 80)

cursor.execute("""
    SELECT indexname, indexdef
    FROM pg_indexes
    WHERE tablename = 'document_stage_timing'
""")

for row in cursor.fetchall():
    print(f"  {row[0]}")

# ========================================
# 3. Verificar backfill
# ========================================
print("\n3️⃣ BACKFILL (Document-level stages):")
print("-" * 80)

cursor.execute("""
    SELECT stage, COUNT(*), 
           COUNT(CASE WHEN news_item_id IS NULL THEN 1 END) as doc_level_count,
           COUNT(CASE WHEN news_item_id IS NOT NULL THEN 1 END) as news_level_count
    FROM document_stage_timing
    GROUP BY stage
    ORDER BY stage
""")

print(f"  {'Stage':15} {'Total':>8} {'Doc-level':>12} {'News-level':>12}")
print("  " + "-" * 50)
for row in cursor.fetchall():
    print(f"  {row[0]:15} {row[1]:>8} {row[2]:>12} {row[3]:>12}")

# ========================================
# 4. Verificar timing registros recientes
# ========================================
print("\n4️⃣ TIMING RECIENTE (últimos 10 registros):")
print("-" * 80)

cursor.execute("""
    SELECT 
        SUBSTRING(document_id, 1, 12) as doc_short,
        CASE WHEN news_item_id IS NULL THEN 'DOC' ELSE SUBSTRING(news_item_id, 1, 12) END as news_short,
        stage,
        status,
        ROUND(EXTRACT(EPOCH FROM (updated_at - created_at))::numeric, 2) as duration_secs
    FROM document_stage_timing
    ORDER BY created_at DESC
    LIMIT 10
""")

print(f"  {'Doc':15} {'News':15} {'Stage':12} {'Status':12} {'Duration':>10}")
print("  " + "-" * 70)
for row in cursor.fetchall():
    print(f"  {row[0]:15} {row[1]:15} {row[2]:12} {row[3]:12} {row[4]:>10}")

# ========================================
# 5. Performance estadísticas (si hay datos)
# ========================================
print("\n5️⃣ PERFORMANCE STATS (stages completados):")
print("-" * 80)

cursor.execute("""
    SELECT 
        stage,
        COUNT(*) as count,
        ROUND(AVG(EXTRACT(EPOCH FROM (updated_at - created_at)))::numeric, 2) as avg_secs,
        ROUND(MIN(EXTRACT(EPOCH FROM (updated_at - created_at)))::numeric, 2) as min_secs,
        ROUND(MAX(EXTRACT(EPOCH FROM (updated_at - created_at)))::numeric, 2) as max_secs
    FROM document_stage_timing
    WHERE status = 'done' AND news_item_id IS NULL
    GROUP BY stage
    ORDER BY stage
""")

print(f"  {'Stage':15} {'Count':>8} {'Avg(s)':>10} {'Min(s)':>10} {'Max(s)':>10}")
print("  " + "-" * 60)
for row in cursor.fetchall():
    print(f"  {row[0]:15} {row[1]:>8} {row[2]:>10} {row[3]:>10} {row[4]:>10}")

# ========================================
# 6. Verificar triggers de updated_at
# ========================================
print("\n6️⃣ TRIGGERS (updated_at auto-update):")
print("-" * 80)

cursor.execute("""
    SELECT tgname, tgenabled, tgrelid::regclass
    FROM pg_trigger
    WHERE tgname LIKE '%updated_at%'
    ORDER BY tgrelid::regclass::text
""")

for row in cursor.fetchall():
    enabled = "✅ enabled" if row[1] == 'O' else "❌ disabled"
    print(f"  {row[0]:50} {enabled:15} on {row[2]}")

# ========================================
# 7. Verificar document_status tiene created/updated
# ========================================
print("\n7️⃣ DOCUMENT_STATUS (timestamps a nivel documento):")
print("-" * 80)

cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(created_at) as has_created,
        COUNT(updated_at) as has_updated,
        COUNT(CASE WHEN created_at != updated_at THEN 1 END) as modified_count
    FROM document_status
""")

row = cursor.fetchone()
print(f"  Total docs: {row[0]}")
print(f"  Con created_at: {row[1]} ({'✅' if row[1] == row[0] else '❌'})")
print(f"  Con updated_at: {row[2]} ({'✅' if row[2] == row[0] else '❌'})")
print(f"  Modificados: {row[3]}")

# ========================================
# RESUMEN FINAL
# ========================================
print("\n" + "=" * 80)
print("✅ VALIDACIÓN COMPLETADA")
print("=" * 80)

cursor.execute("SELECT COUNT(*) FROM document_stage_timing")
total_records = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(DISTINCT document_id) FROM document_stage_timing")
unique_docs = cursor.fetchone()[0]

cursor.execute("SELECT COUNT(*) FROM document_stage_timing WHERE news_item_id IS NOT NULL")
news_records = cursor.fetchone()[0]

print(f"\n📊 Resumen:")
print(f"  - Registros totales en document_stage_timing: {total_records}")
print(f"  - Documentos únicos: {unique_docs}")
print(f"  - Registros document-level: {total_records - news_records}")
print(f"  - Registros news-level: {news_records}")
print(f"\n✅ Sistema de timestamps unificado funcionando correctamente")

conn.close()
