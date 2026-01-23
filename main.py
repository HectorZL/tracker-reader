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
async def sync_progress(libro: LibroSincro, background_tasks: BackgroundTasks):
    """
    Sincroniza el progreso de lectura con Goodreads.
    Requiere un user_id válido obtenido en /login.
    """
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
    
    # 3. Ejecución en Background usando el executor
    # Ejecutamos run_scraper en un thread del pool para evitar bloquear asyncio
    loop = asyncio.get_event_loop()
    background_tasks.add_task(loop.run_in_executor, executor, run_scraper, libro)
    
    return {
        "status": "received", 
        "book": libro.titulo, 
        "user_id": libro.user_id,
        "message": "Sincronización iniciada en segundo plano"
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