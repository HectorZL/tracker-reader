import asyncio
import sys

# CRITICAL: Fix para Windows - Debe ir ANTES de cualquier otro import
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from playwright.sync_api import sync_playwright  # Cambiado a sync_api para evitar conflictos de event loop
from playwright_stealth import Stealth
from thefuzz import fuzz

app = FastAPI(title="Hector Reading Tracker API")

# --- Configuración ---
SESSION_FILE = "state.json"
USER_EMAIL = "zambranohector2002@gmail.com"
USER_PASS = "@Hector0406G"
MIN_CONFIDENCE = 80  # Porcentaje de similitud mínima

# --- Modelos de Datos ---
class LibroSincro(BaseModel):
    titulo: str
    autor: str
    isbn: str = ""
    pagina_actual: int  # Página en la que vas (de tu libro)
    total_paginas: int  # Total de páginas de tu libro
    dispositivo: str = "KOReader"

# --- Lógica del Scraper con Playwright ---
def run_scraper(data: LibroSincro):
    """
    Ejecuta el scraper de forma sincrónica usando sync_playwright.
    Esto evita conflictos con el event loop de uvicorn en Windows.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Cambiar a False para ver el proceso
        
        # Cargar sesión si existe
        if os.path.exists(SESSION_FILE):
            context = browser.new_context(storage_state=SESSION_FILE)
            print("INFO: Sesión cargada desde archivo.")
        else:
            context = browser.new_context()
            print("INFO: Iniciando sesión nueva.")

        # Stealth temporalmente deshabilitado - playwright-stealth 2.0.1 no soporta sync API
        # stealth = Stealth()
        # stealth.apply_stealth(context)
        
        page = context.new_page()

        try:
            # 1. Verificar si estamos logueados, si no, ir a login
            page.goto("https://www.goodreads.com/search")
            
            # Guardar HTML para depuración
            html_content = page.content()
            with open("page_debug.html", "w", encoding="utf-8") as f:
                f.write(html_content)
            print("INFO: HTML de la página guardado en page_debug.html")
            
            if page.query_selector('text="Sign In"') is not None:
                print("INFO: No está logueado, iniciando proceso de login...")
                page.goto("https://www.goodreads.com/user/sign_in")
                
                # Esperar y hacer clic en "Sign in with email"
                page.wait_for_selector('.authPortalSignInButton', timeout=10000)
                page.click('.authPortalSignInButton')
                print("INFO: Clic en 'Sign in with email'")
                
                # Esperar a que aparezcan los campos de login
                page.wait_for_selector('#ap_email', timeout=10000)
                
                # Llenar email
                page.fill("#ap_email", USER_EMAIL)
                print(f"INFO: Email ingresado: {USER_EMAIL}")
                
                # Llenar contraseña
                page.fill("#ap_password", USER_PASS)
                print("INFO: Contraseña ingresada")
                
                # Hacer clic en submit
                page.click('#signInSubmit')
                print("INFO: Clic en botón de login")
                
                # Esperar a que termine el login
                page.wait_for_load_state("networkidle")
                
                # Guardar HTML después del login para verificar
                html_after_login = page.content()
                with open("page_after_login_debug.html", "w", encoding="utf-8") as f:
                    f.write(html_after_login)
                print("INFO: HTML después del login guardado en page_after_login_debug.html")
                
                # Guardar sesión para la próxima vez
                context.storage_state(path=SESSION_FILE)
                print("INFO: Login exitoso y sesión guardada.")

            # 2. Búsqueda del libro (SOLO por título)
            query = data.titulo
            
            print(f"INFO: Buscando libro con título: {query}")
            page.goto(f"https://www.goodreads.com/search?q={query}")
            
            # Esperar 10 segundos para que cargue completamente
            print("INFO: Esperando 5 segundos para que cargue la página...")
            page.wait_for_timeout(5000)
            
            # Guardar HTML de resultados de búsqueda
            search_html = page.content()
            with open("search_results_debug.html", "w", encoding="utf-8") as f:
                f.write(search_html)
            print("INFO: HTML de resultados guardado en search_results_debug.html")
            
            # 3. Validación de Resultados (Fuzzy Matching)
            first_result_selector = ".bookTitle span"
            
            # Intentar encontrar el selector con timeout más largo
            try:
                page.wait_for_selector(first_result_selector, timeout=15000)
                titulo_encontrado = page.inner_text(first_result_selector)
                
                # Limpiar el título encontrado (quitar lo que está entre paréntesis como "(Series, #1)")
                titulo_limpio = titulo_encontrado.split('(')[0].strip()
                
                # Usar token_set_ratio que es más flexible con palabras extra o diferente orden
                # Esto permitirá que "El Psicoanalista" coincida con "El Psicoanalista John Katzenbach"
                score = fuzz.token_set_ratio(data.titulo, titulo_limpio)
                
                if score >= MIN_CONFIDENCE:
                    print(f"MATCH: '{titulo_limpio}' coincide con '{data.titulo}' ({score}%)")
                    
                    # 4. Actualizar progreso desde los resultados de búsqueda (SIN ir a la página del libro)
                    # Goodreads puede mostrar resultados en dos formatos: lista (li.book) o tabla (tr)
                    
                    # Intentar primero con formato de lista
                    first_book_item_element = page.query_selector('li.book')
                    
                    if not first_book_item_element:
                        # Si no hay li.book, buscar formato de tabla
                        print("INFO: No se encontró formato de lista, buscando formato de tabla...")
                        first_book_item_element = page.query_selector('tr[itemtype*="Book"]')
                        
                        if first_book_item_element:
                            print("INFO: Encontrado libro en formato de tabla (tr)")
                        else:
                            print("ERROR: No se encontró el contenedor del libro en ningún formato")
                            return
                    else:
                        print("INFO: Encontrado libro en formato de lista (li.book)")
                    
                    
                    # Extraer el ID del libro (diferente formato según lista o tabla)
                    book_id = None
                    
                    # Intentar extraer del atributo id (formato lista)
                    book_id_attr = first_book_item_element.get_attribute('id')
                    if book_id_attr and 'book_list_item_' in book_id_attr:
                        book_id = book_id_attr.replace('book_list_item_', '')
                        print(f"INFO: Book ID encontrado en formato lista: {book_id}")
                    else:
                        # Si no está en el atributo id, buscar en div.u-anchorTarget (formato tabla)
                        anchor_div = first_book_item_element.query_selector('div.u-anchorTarget')
                        if anchor_div:
                            book_id = anchor_div.get_attribute('id')
                            if book_id:
                                print(f"INFO: Book ID encontrado en formato tabla: {book_id}")
                    
                    if not book_id:
                        print("ERROR: No se pudo extraer el book ID")
                        return
                    
                    # Buscar el botón .wtrShelfButton dentro de este resultado
                    shelf_button = first_book_item_element.query_selector('.wtrShelfButton')
                    
                    if not shelf_button:
                        print("ERROR: No se encontró el botón wtrShelfButton")
                        return
                    
                    # Hacer click en el botón para mostrar el menú
                    print("INFO: Haciendo click en wtrShelfButton para mostrar el menú...")
                    shelf_button.click()
                    page.wait_for_timeout(1000)
                    
                    # Buscar el botón "Currently Reading" en el menú desplegable
                    currently_reading_menu_button = first_book_item_element.query_selector('button[value="currently-reading"]')
                    
                    if currently_reading_menu_button:
                        print("INFO: Haciendo click en 'Currently Reading' del menú...")
                        currently_reading_menu_button.click()
                        page.wait_for_timeout(2000)
                        print("INFO: Libro marcado como 'Currently Reading'")
                        
                        # Ahora hacer hover sobre el botón de estado para actualizar páginas
                        # Esperar a que aparezca el botón de "Currently Reading"
                        page.wait_for_timeout(1000)
                        
                        # Buscar el botón de estado actual
                        status_button = first_book_item_element.query_selector('.wtrStatusReadingNow')
                        
                        if status_button:
                            print(f"INFO: Actualizando progreso de página {data.pagina_actual}/{data.total_paginas}...")
                            
                            # Hacer hover para mostrar el formulario
                            status_button.hover()
                            page.wait_for_timeout(1500)
                            
                            # Extraer el total de páginas del libro en Goodreads
                            # El formulario muestra algo como "of 528" para el total de páginas
                            page_text = first_book_item_element.inner_text()
                            
                            # Buscar el input de páginas
                            page_input = first_book_item_element.query_selector('input[name="user_status[page]"]')
                            
                            if page_input:
                                # Extraer el total de páginas de Goodreads del texto del formulario
                                # Buscar patrón "of XXX"
                                import re
                                match = re.search(r'of\s+(\d+)', page_text)
                                
                                if match:
                                    goodreads_total_pages = int(match.group(1))
                                    print(f"INFO: Total de páginas en Goodreads: {goodreads_total_pages}")
                                    
                                    # Calcular la página equivalente en Goodreads
                                    if data.total_paginas > 0:
                                        proporcion = data.pagina_actual / data.total_paginas
                                        goodreads_page = int(proporcion * goodreads_total_pages)
                                        
                                        # Asegurar que no exceda el máximo
                                        goodreads_page = min(goodreads_page, goodreads_total_pages)
                                        
                                        print(f"INFO: Calculando página equivalente: {data.pagina_actual}/{data.total_paginas} → {goodreads_page}/{goodreads_total_pages}")
                                    else:
                                        goodreads_page = 0
                                else:
                                    # Si no se puede extraer, usar directamente la página del usuario
                                    print("WARNING: No se pudo extraer el total de páginas de Goodreads, usando página directa")
                                    goodreads_page = data.pagina_actual
                                
                                # Hacer click en el toggle para cambiar a modo página si está en porcentaje
                                toggle_button = first_book_item_element.query_selector('.wtrNewUserStatusProgressTypeToggle')
                                if toggle_button:
                                    toggle_text = toggle_button.inner_text().strip()
                                    if 'page' in toggle_text.lower():
                                        # Ya está en modo página, no hacer nada
                                        pass
                                    else:
                                        # Está en modo porcentaje, cambiar a página
                                        print("INFO: Cambiando a modo página...")
                                        toggle_button.click()
                                        page.wait_for_timeout(500)
                                
                                # Limpiar y llenar el campo de página
                                page_input.fill('')
                                page_input.fill(str(goodreads_page))
                                print(f"INFO: Página actualizada a {goodreads_page}")
                                
                                # Hacer click en Submit
                                submit_button = first_book_item_element.query_selector('button.gr-form--compact__submitButton')
                                if submit_button:
                                    submit_button.click()
                                    page.wait_for_timeout(2000)
                                    print(f"SUCCESS: Progreso actualizado a página {goodreads_page} de {goodreads_total_pages if match else 'desconocido'}")
                                else:
                                    print("WARNING: No se encontró el botón Submit")
                            else:
                                print("WARNING: No se encontró el campo de página")
                        else:
                            print("WARNING: No se encontró el botón de estado 'Currently Reading'")
                    else:
                        print("INFO: El libro no está en 'Currently Reading', marcándolo...")
                        # El botón no existe, probablemente ya está marcado de otra forma
                    
                else:
                    print(f"ERROR: No se encontró un match confiable ({score}%).")
                    print(f"Buscado: '{data.titulo}'")
                    print(f"Encontrado: '{titulo_encontrado}' (Limpio: '{titulo_limpio}')")
            except Exception as selector_error:
                print(f"WARNING: No se encontró el selector '{first_result_selector}'. Error: {str(selector_error)}")
                print("INFO: Revisa el archivo search_results_debug.html para ver la estructura de la página")

        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}")
        finally:
            browser.close()

# --- Endpoints ---
@app.post("/sync")
async def sync_progress(libro: LibroSincro, background_tasks: BackgroundTasks):
    # Validamos páginas
    if libro.pagina_actual < 0 or libro.total_paginas <= 0:
        raise HTTPException(status_code=400, detail="Las páginas deben ser válidas")
    if libro.pagina_actual > libro.total_paginas:
        raise HTTPException(status_code=400, detail="La página actual no puede ser mayor al total")
    
    # Mandamos el scraper al background para no bloquear a KOReader
    background_tasks.add_task(run_scraper, libro)
    
    return {
        "status": "received", 
        "book": libro.titulo, 
        "target": "Goodreads/StoryGraph"
    }

if __name__ == "__main__":
    import uvicorn
    # Se usa "main:app" y reload=True para que el servidor se reinicie solo al guardar cambios.
    # loop="asyncio" asegura que uvicorn use el loop configurado arriba.
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, loop="asyncio")