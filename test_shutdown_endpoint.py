#!/usr/bin/env python3
"""
Script de prueba para el endpoint de shutdown ordenado.
Verifica que el endpoint funciona correctamente y muestra el estado antes/después.
"""

import requests
import json
import sys
from datetime import datetime

# Configuración
API_URL = "http://localhost:8000"
# Necesitarás un token válido - puedes obtenerlo del login
TOKEN = None  # Reemplazar con token real o leer de variable de entorno

def get_token():
    """Obtener token de autenticación"""
    # Intentar leer de variable de entorno
    import os
    token = os.getenv('API_TOKEN')
    if token:
        return token
    
    # Si no hay token, intentar login
    print("⚠️  No se encontró token. Intentando login...")
    login_data = {
        "username": "admin",  # Ajustar según tu configuración
        "password": "admin"   # Ajustar según tu configuración
    }
    
    try:
        response = requests.post(f"{API_URL}/api/auth/login", json=login_data)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"❌ Error en login: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error conectando al backend: {e}")
        return None

def get_workers_status(token):
    """Obtener estado actual de workers"""
    try:
        response = requests.get(
            f"{API_URL}/api/workers/status",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️  Error obteniendo estado: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def get_analysis(token):
    """Obtener análisis del dashboard"""
    try:
        response = requests.get(
            f"{API_URL}/api/dashboard/analysis",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️  Error obteniendo análisis: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def shutdown_workers(token):
    """Ejecutar shutdown ordenado"""
    try:
        print("\n🛑 Ejecutando shutdown ordenado...")
        response = requests.post(
            f"{API_URL}/api/workers/shutdown",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error en shutdown: {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def print_status(title, data):
    """Imprimir estado formateado"""
    print(f"\n{'='*60}")
    print(f"📊 {title}")
    print(f"{'='*60}")
    
    if not data:
        print("⚠️  Sin datos disponibles")
        return
    
    if 'workers' in data:
        workers = data.get('workers', [])
        print(f"\n👷 Workers: {len(workers)}")
        if workers:
            active = [w for w in workers if w.get('status') in ['active', 'started']]
            errors = [w for w in workers if w.get('status') == 'error']
            print(f"   - Activos: {len(active)}")
            print(f"   - Errores: {len(errors)}")
    
    if 'workers' in data and isinstance(data['workers'], dict):
        # Formato del endpoint de análisis
        workers_info = data['workers']
        print(f"\n👷 Workers:")
        print(f"   - Activos: {workers_info.get('active', 0)}")
        print(f"   - Stuck: {workers_info.get('stuck', 0)}")
        if workers_info.get('summary'):
            print(f"   - Resumen: {workers_info['summary']}")

def main():
    print("🧪 Prueba del Endpoint de Shutdown Ordenado")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Obtener token
    token = get_token()
    if not token:
        print("\n❌ No se pudo obtener token. Abortando.")
        sys.exit(1)
    
    print("✅ Token obtenido")
    
    # Estado ANTES del shutdown
    print("\n" + "="*60)
    print("📋 ESTADO ANTES DEL SHUTDOWN")
    print("="*60)
    
    workers_before = get_workers_status(token)
    analysis_before = get_analysis(token)
    
    if workers_before:
        print_status("Workers Status (antes)", workers_before)
    
    if analysis_before:
        print_status("Dashboard Analysis (antes)", analysis_before)
        
        # Mostrar tareas en processing
        if 'database' in analysis_before and 'processing_queue' in analysis_before['database']:
            pq = analysis_before['database']['processing_queue']
            if 'by_type' in pq:
                print("\n📋 Processing Queue (antes):")
                for task_type, statuses in pq['by_type'].items():
                    processing = statuses.get('processing', 0)
                    if processing > 0:
                        print(f"   - {task_type}: {processing} en processing")
    
    # Confirmar antes de ejecutar
    print("\n" + "="*60)
    print("⚠️  ADVERTENCIA: Esto detendrá todos los workers activos")
    print("="*60)
    confirm = input("\n¿Continuar con el shutdown? (s/N): ").strip().lower()
    
    if confirm != 's':
        print("❌ Shutdown cancelado por el usuario")
        sys.exit(0)
    
    # Ejecutar shutdown
    shutdown_result = shutdown_workers(token)
    
    if shutdown_result:
        print("\n✅ Shutdown ejecutado correctamente")
        print(json.dumps(shutdown_result, indent=2, ensure_ascii=False))
    else:
        print("\n❌ Error en el shutdown")
        sys.exit(1)
    
    # Esperar un momento para que se complete
    import time
    print("\n⏳ Esperando 3 segundos para que se complete el proceso...")
    time.sleep(3)
    
    # Estado DESPUÉS del shutdown
    print("\n" + "="*60)
    print("📋 ESTADO DESPUÉS DEL SHUTDOWN")
    print("="*60)
    
    workers_after = get_workers_status(token)
    analysis_after = get_analysis(token)
    
    if workers_after:
        print_status("Workers Status (después)", workers_after)
    
    if analysis_after:
        print_status("Dashboard Analysis (después)", analysis_after)
        
        # Mostrar tareas revertidas
        if 'database' in analysis_after and 'processing_queue' in analysis_after['database']:
            pq = analysis_after['database']['processing_queue']
            if 'by_type' in pq:
                print("\n📋 Processing Queue (después):")
                for task_type, statuses in pq['by_type'].items():
                    pending = statuses.get('pending', 0)
                    processing = statuses.get('processing', 0)
                    print(f"   - {task_type}: {pending} pending, {processing} processing")
        
        # Mostrar errores de shutdown
        if 'errors' in analysis_after:
            errors = analysis_after['errors']
            shutdown_errors = errors.get('shutdown_errors', 0)
            if shutdown_errors > 0:
                print(f"\nℹ️  Errores de shutdown detectados: {shutdown_errors}")
                print("   (Estos son esperados después de un shutdown ordenado)")
    
    print("\n" + "="*60)
    print("✅ Prueba completada")
    print("="*60)
    print("\n💡 Para reiniciar los workers, usa: POST /api/workers/start")

if __name__ == "__main__":
    main()
