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
            
            # 3. Validación de Resultados (Fuzzy Matching Avanzado)
            print("INFO: Analizando los primeros 5 resultados para encontrar la mejor coincidencia...")
            
            # Script para extraer datos de los primeros 5 resultados
            # Devuelve una lista de objetos {index, title, author, element_found}
            # Nota: element_found no se puede devolver, así que devolveremos índices y luego seleccionaremos
            candidates_data = page.evaluate('''() => {
                const results = [];
                // Intentar selector de lista y tabla
                const rows = document.querySelectorAll('tr[itemtype*="Book"]');
                const listItems = document.querySelectorAll('li.book');
                
                const elements = rows.length > 0 ? rows : listItems;
                
                // Analizar hasta 5 resultados
                for (let i = 0; i < Math.min(elements.length, 5); i++) {
                    const el = elements[i];
                    
                    // Extraer título
                    const titleEl = el.querySelector('.bookTitle span') || el.querySelector('.bookTitle');
                    const title = titleEl ? titleEl.innerText : "";
                    
                    // Extraer autor
                    const authorEl = el.querySelector('.authorName span') || el.querySelector('.authorName');
                    const author = authorEl ? authorEl.innerText : "";
                    
                    results.push({
                        index: i,
                        title: title,
                        author: author,
                        is_table: rows.length > 0
                    });
                }
                return results;
            }''')
            
            best_match = None
            best_score = 0
            best_element_handle = None
            
            print(f"INFO: Candidatos encontrados: {len(candidates_data)}")
            
            for candidate in candidates_data:
                cand_title = candidate['title']
                cand_author = candidate['author']
                
                # Limpieza básica
                cand_title_clean = cand_title.split('(')[0].strip() # Quitar series info por ahora
                
                # Puntaje de Título
                # Usamos parcial_ratio para el título para permitir subtítulos, pero token_sort para autor
                title_score = fuzz.token_set_ratio(data.titulo.lower(), cand_title_clean.lower())
                
                # Puntaje de Autor
                author_score = fuzz.token_sort_ratio(data.autor.lower(), cand_author.lower())
                
                # Puntaje Total Ponderado
                # Damos mucho peso al autor para evitar libros de otro autor con mismo nombre
                # Y penalizamos si es una secuela (ej. #3.5) y no lo pedimos
                
                total_score = (title_score * 0.6) + (author_score * 0.4)
                
                # Detección de sagas/numéricos (heurística simple)
                # Si el título candidato tiene números como "#2", "#3.5" y nuestra búsqueda no, penalizar
                import re
                saga_number_match = re.search(r'#(\d+(\.\d+)?)', cand_title)
                user_saga_match = re.search(r'#(\d+(\.\d+)?)', data.titulo)
                
                if saga_number_match and not user_saga_match:
                    # El candidato es una secuela específica, pero el usuario no pidió número
                    # Si es #1, no penalizamos tanto. Si es #2+, penalizamos.
                    num = float(saga_number_match.group(1))
                    if num > 1.0:
                        print(f"   -> Penalizando candidato '{cand_title}' por ser secuela #{num} no solicitada")
                        total_score -= 15
                
                print(f"   Candidato {candidate['index']}: '{cand_title}' por {cand_author}")
                print(f"   Scores - Título: {title_score}, Autor: {author_score} -> Total: {total_score}")
                
                # Umbral de aceptación y mejor que el anterior
                if total_score > best_score and total_score >= 60: # Umbral 60 razonable para combinada
                    best_match = candidate
                    best_score = total_score
            
            if best_match:
                print(f"MATCH GANADOR: '{best_match['title']}' por {best_match['author']} (Score: {best_score})")
                
                # Ahora recuperamos el elemento del DOM correspondiente al ganador
                if best_match['is_table']:
                    # Re-seleccionar usando nth-child (recordar que nth-child es 1-based, index es 0-based)
                    # En tablas a veces hay headers, mejor ir por querySelectorAll y index
                    first_book_item_element = page.evaluate_handle(f'document.querySelectorAll("tr[itemtype*=\'Book\']")[{best_match["index"]}]')
                else:
                    first_book_item_element = page.evaluate_handle(f'document.querySelectorAll("li.book")[{best_match["index"]}]')
                
                # Convertir JSHandle a ElementHandle si es necesario (Playwright Python lo maneja usualmente)
                first_book_item_element = first_book_item_element.as_element()
                
                titulo_limpio = best_match['title']
                
                if True: # Bloque dummy para mantener indentación del código siguiente
                    # 4. Actualizar progreso...
                    pass

                    
                    
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
                    if not book_id:
                        print("ERROR: No se pudo extraer el book ID")
                        return
                    
                    # 5. Detectar estado y actualizar
                    # Primero verificar si YA está en Currently Reading (para evitar clicks innecesarios)
                    status_button = first_book_item_element.query_selector('.wtrStatusReadingNow')
                    
                    if status_button:
                        print("INFO: El libro ya está en 'Currently Reading'. Actualizando directamente...")
                        # Si ya está leyendo, solo hacer hover sobre el contenedor para mostrar el input
                        # A veces es mejor hacer hover sobre el padre .wtrDown
                        wtr_down = first_book_item_element.query_selector('.wtrDown')
                        if wtr_down:
                            wtr_down.hover()
                        else:
                            status_button.hover()
                            
                        page.wait_for_timeout(1500)
                        
                        # Lógica de actualización de páginas (reutilizable)
                        update_pages(page, first_book_item_element, data)
                        
                    else:
                        # Si no está leyendo, buscar el botón del menú
                        print("INFO: El libro no parece estar en 'Currently Reading'. Buscando botón de estante...")
                        
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
                            
                            # Ahora intentar actualizar páginas
                            # Esperar a que se actualice el estado en la UI
                            page.wait_for_timeout(1000)
                            
                            # Buscar el botón de estado actualizado
                            status_button = first_book_item_element.query_selector('.wtrStatusReadingNow')
                            if status_button:
                                status_button.hover()
                                page.wait_for_timeout(1500)
                                update_pages(page, first_book_item_element, data)
                        else:
                            print("WARNING: No se encontró la opción 'Currently Reading' en el menú")

            else:
                print(f"ERROR: No se encontró ningún libro candidato con puntaje suficiente (Min: 60).")
                print(f"Buscado: '{data.titulo}' - Autor: '{data.autor}'")
                if len(candidates_data) > 0:
                    print("Mejores candidatos descartados:")
                    for c in candidates_data[:3]:
                        print(f"- {c['title']} ({c['author']})")


        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}")
        finally:
            browser.close()

def update_pages(page, container, data):
    """Función auxiliar para actualizar las páginas manipulando el DOM directamente con JS"""
    try:
        # Script JS robusto para hacer todo el proceso
        js_script = """
        (container) => {
            const formContainer = container.querySelector('.wtrFloatingBox.wtrNewUserStatus');
            if (!formContainer) return { success: false, error: "Contenedor de formulario no encontrado" };
            
            // 1. Forzar visibilidad del formulario
            formContainer.style.display = 'block';
            formContainer.style.visibility = 'visible';
            formContainer.style.opacity = '1';
            
            // 2. Buscar input de páginas
            const pageInput = container.querySelector('input[name="user_status[page]"]');
            if (!pageInput) return { success: false, error: "Input de página no encontrado" };
            
            // 3. Extraer total para cálculo (opcional, pero útil)
            let totalPages = 0;
            const text = container.innerText || "";
            const match = text.match(/of\\s+(\\d+)/);
            if (match) totalPages = parseInt(match[1]);
            
            // 4. Calcular página objetivo (pasada como argumento sería mejor, pero calculamos aquí si es necesario)
            // Nota: Aquí usaremos el valor que pasaremos desde Python
            
            return { 
                success: true, 
                totalPages: totalPages,
                inputSelector: 'input[name="user_status[page]"]',
                submitSelector: 'button.gr-form--compact__submitButton',
                toggleSelector: '.wtrNewUserStatusProgressTypeToggle'
            };
        }
        """
        
        # Ejecutar fase de preparación
        result = page.evaluate(js_script, container)
        
        if not result['success']:
            print(f"WARNING: Fallo en preparación JS: {result.get('error')}")
            return
            
        goodreads_total_pages = result['totalPages']
        if goodreads_total_pages > 0:
             print(f"INFO: Total de páginas detectado en JS: {goodreads_total_pages}")
        
        # Calcular página exacta en Python
        final_page = data.pagina_actual
        if goodreads_total_pages > 0 and data.total_paginas > 0:
            proporcion = data.pagina_actual / data.total_paginas
            final_page = int(proporcion * goodreads_total_pages)
            final_page = min(final_page, goodreads_total_pages)
            print(f"INFO: Página calculada: {final_page}")
            
        # Ejecutar fase de acción (llenar y enviar)
        action_script = """
        (params) => {
            const container = document.querySelector(params.containerSelector); # Esto no funcionará porque container es un objeto handle
            // Necesitamos pasar el elemento container de nuevo
        }
        """
        
        # Usamos evaluate pasando los argumentos necesarios
        page.evaluate("""
            ([container, pageValue]) => {
                const pageInput = container.querySelector('input[name="user_status[page]"]');
                const submitBtn = container.querySelector('button.gr-form--compact__submitButton');
                const toggleBtn = container.querySelector('.wtrNewUserStatusProgressTypeToggle');
                
                // Asegurar modo página
                if (toggleBtn && pageInput && !pageInput.offsetParent) {
                     // Si el input está oculto, intentar toggle
                     toggleBtn.click();
                }
                
                // Llenar valor
                if (pageInput) {
                    pageInput.value = pageValue;
                    pageInput.dispatchEvent(new Event('change', { bubbles: true }));
                    pageInput.dispatchEvent(new Event('input', { bubbles: true }));
                }
                
                // Submit
                if (submitBtn) {
                    submitBtn.click();
                }
            }
        """, [container, str(final_page)])
        
        print(f"SUCCESS: Comando de actualización enviado para página {final_page}")
        page.wait_for_timeout(2000)
            
    except Exception as e:
        print(f"ERROR actualizando páginas: {str(e)}")
    except Exception as e:
        print(f"ERROR actualizando páginas: {str(e)}")
                    


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