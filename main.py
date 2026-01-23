from fastapi import FastAPI, BackgroundTasks, HTTPException
from models import UserLogin, LoginResponse, LibroSincro
from auth import session_exists
# Importamos las funciones principales desde scraper
from scraper import do_login, run_scraper
import uvicorn
import asyncio
from concurrent.futures import ThreadPoolExecutor

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

if __name__ == "__main__":
    # Iniciar servidor
    print("🚀 Servidor iniciado en http://0.0.0.0:8000")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, loop="asyncio")