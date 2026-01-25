from fastapi import FastAPI, BackgroundTasks, HTTPException
from models import UserLogin, LoginResponse, LibroSincro
from auth import session_exists
# Importamos las funciones principales desde scraper
from scraper import do_login, run_scraper
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor
import httpx
import os
from datetime import datetime

# Inicializar aplicación FastAPI
app = FastAPI(
    title="Goodreads Tracker API", 
    version="2.0",
    description="API Multi-usuario para sincronizar lectura desde KOReader a Goodreads"
)

# Thread pool para ejecutar código síncrono (Playwright) sin bloquear asyncio
executor = ThreadPoolExecutor(max_workers=4)

@app.post("/login", response_model=LoginResponse)
async def login(user: UserLogin):
    """
    Endpoint para loguearse en Goodreads.
    Retorna un user_id que debe usarse en las peticiones de /sync.
    """
    try:
        # Ejecutamos do_login en un thread separado para no bloquear el loop asyncio
        loop = asyncio.get_event_loop()
        user_id = await loop.run_in_executor(executor, do_login, user)
        return {
            "user_id": user_id, 
            "status": "success", 
            "message": "Login exitoso. Guarda el user_id para futuras peticiones."
        }
    except Exception as e:
        # Retornamos 401 si falla el login
        raise HTTPException(status_code=401, detail=f"Login fallido: {str(e)}")

@app.post("/sync")
async def sync_progress(libro: LibroSincro):
    """
    Sincroniza el progreso de lectura con Goodreads.
    Requiere un user_id válido obtenido en /login.
    Ejecuta DOS VECES: (1) Marcar libro, (2) Actualizar progreso.
    
    Retorna información sobre el estado de la sincronización, incluyendo
    si Goodreads ya tenía un progreso mayor.
    """
    from scraper import get_last_sync_result
    
    # 1. Validaciones de Datos
    if libro.pagina_actual < 0 or libro.total_paginas <= 0:
        raise HTTPException(status_code=400, detail="Número de páginas inválido")
    if libro.pagina_actual > libro.total_paginas:
        raise HTTPException(status_code=400, detail="La página actual no puede ser mayor al total")
    
    # 2. Validación de Sesión
    if not session_exists(libro.user_id):
        raise HTTPException(
            status_code=401, 
            detail="Sesión no encontrada o expirada. Por favor realiza /login nuevamente."
        )
    
    # 3. Ejecutar sincronización de forma SÍNCRONA para poder devolver el resultado
    loop = asyncio.get_event_loop()
    
    print("\n" + "="*60)
    print("SYNC 1/2: Marcando libro como Currently Reading")
    print("="*60)
    await loop.run_in_executor(executor, run_scraper, libro)
    
    print("\n" + "="*60)
    print("SYNC 2/2: Actualizando progreso de lectura")
    print("="*60)
    await loop.run_in_executor(executor, run_scraper, libro)
    print("\n✅ Sincronización completa (2/2)")
    
    # 4. Obtener resultado de la sincronización
    sync_result = get_last_sync_result()
    
    if sync_result:
        return {
            "status": "completed",
            "book": libro.titulo,
            "user_id": libro.user_id,
            "updated": sync_result.get("updated", True),
            "reason": sync_result.get("reason", "unknown"),
            "gr_progress": {
                "percent": sync_result.get("gr_percent", 0),
                "page": sync_result.get("gr_page", 0),
                "total_pages": sync_result.get("gr_total_pages", 0),
                "page_equivalent_kr": sync_result.get("gr_page_equivalent_kr", 0)
            },
            "kr_progress": {
                "page": sync_result.get("kr_page", libro.pagina_actual),
                "total_pages": sync_result.get("kr_total", libro.total_paginas)
            },
            "message": sync_result.get("message", "Sincronización completada")
        }
    else:
        # Fallback si no hay resultado
        return {
            "status": "completed", 
            "book": libro.titulo, 
            "user_id": libro.user_id,
            "updated": True,
            "message": "Sincronización completada"
        }

@app.get("/ping")
async def ping():
    """
    Endpoint de health check para mantener el servidor activo.
    Render Free Tier suspende el servidor después de 15 minutos de inactividad.
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "message": "Server is running"
    }

# Variable global para controlar el auto-ping
auto_ping_task = None

async def keep_alive():
    """
    Tarea en background que hace ping a sí mismo cada 10 minutos
    para evitar que Render Free Tier suspenda el servidor.
    """
    # Obtener la URL del servidor desde variable de entorno o usar la URL de producción
    server_url = os.getenv("RENDER_EXTERNAL_URL", "https://tracker-reader.onrender.com")
    
    async with httpx.AsyncClient() as client:
        while True:
            try:
                await asyncio.sleep(600)  # Esperar 10 minutos (600 segundos)
                response = await client.get(f"{server_url}/ping", timeout=10.0)
                print(f"🏓 Auto-ping exitoso: {response.status_code} - {datetime.now().isoformat()}")
            except Exception as e:
                print(f"⚠️ Error en auto-ping: {str(e)}")

@app.on_event("startup")
async def startup_event():
    """
    Evento que se ejecuta al iniciar el servidor.
    Inicia la tarea de auto-ping en background.
    """
    global auto_ping_task
    auto_ping_task = asyncio.create_task(keep_alive())
    print("✅ Auto-ping activado - El servidor se mantendrá activo")

@app.on_event("shutdown")
async def shutdown_event():
    """
    Evento que se ejecuta al apagar el servidor.
    Cancela la tarea de auto-ping.
    """
    global auto_ping_task
    if auto_ping_task:
        auto_ping_task.cancel()
        print("🛑 Auto-ping detenido")


if __name__ == "__main__":
    # Obtener puerto desde variable de entorno (Render) o usar 8000 por defecto
    port = int(os.getenv("PORT", 8000))
    
    # Iniciar servidor ##
    print(f"🚀 Servidor iniciado en http://0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True, loop="asyncio")