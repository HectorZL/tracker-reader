import json
from playwright.sync_api import sync_playwright
from rapidfuzz import fuzz
from models import UserLogin, LibroSincro
from auth import generate_user_id, get_session_file
from utils import prepare_form_js, update_pages_js
import time
import os
from playwright_stealth import stealth_sync

# Configuración Headless: Toma el valor de la variable de entorno o False por defecto
HEADLESS = True
MIN_CONFIDENCE = 60

def do_login(user: UserLogin) -> str:
    """
    Realiza login en Goodreads y guarda la sesión en session_file.
    Retorna el user_id generado.
    """
    user_id = generate_user_id(user.username)
    session_file = get_session_file(user_id)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/New_York",
            permissions=["geolocation"],
            geolocation={"latitude": 40.7128, "longitude": -74.0060},
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1"
            }
        )
        page = context.new_page()
        stealth_sync(page) # Activar modo sigilo
        
        
        try:
            print(f"INFO: Iniciando login para {user.username}...")
            page.goto("https://www.goodreads.com/user/sign_in")
            
            # Click en "Sign in with email" si existe (a veces GR lo pide)
            try:
                email_btn = page.query_selector('button:has-text("Sign in with email")')
                if email_btn: email_btn.click()
            except: pass

            # Llenar credenciales
            page.fill("input[name='email']", user.username)
            page.fill("input[name='password']", user.password)
            page.click("input[type='submit']")
            
            # Esperar a que cargue tras el submit
            page.wait_for_load_state("networkidle")
            
            # Verificación simple de éxito
            if "sign_in" in page.url:
                # Si seguimos en sign_in, probablemente falló
                raise Exception("Login fallido. Verifica tus credenciales.")
                
            print(f"SUCCESS: Login exitoso para {user.username}")
            
            # Guardar sesión
            storage = context.storage_state()
            with open(session_file, "w") as f:
                json.dump(storage, f)
            print(f"INFO: Sesión guardada en {session_file}")
            
            return user_id
            
        except Exception as e:
            print(f"ERROR Login: {str(e)}")
            raise e
        finally:
            browser.close()

def run_scraper(data: LibroSincro):
    """
    Ejecuta el proceso de sincronización para un usuario específico.
    """
    print(f"--- Iniciando sincronización para usuario {data.user_id} ---")
    session_file = get_session_file(data.user_id)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process"
            ]
        )
        
        # Cargar sesión
        try:
            with open(session_file, 'r') as f:
                state_data = json.load(f)
            # User Agent común para evitar bloqueos
            context = browser.new_context(
                storage_state=session_file,
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"],
                geolocation={"latitude": 40.7128, "longitude": -74.0060},
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1"
                }
            )
            print(f"INFO: Sesión cargada para usuario {data.user_id}")
        except Exception as e:
            print(f"ERROR cargando sesión: {e}")
            browser.close()
            return

        page = context.new_page()
        stealth_sync(page) # Activar modo sigilo
        

        try:
            # 1. Buscar Libro
            query = f"{data.titulo} {data.autor}"
            print(f"INFO: Buscando: '{data.titulo}' de '{data.autor}'")
            page.goto(f"https://www.goodreads.com/search?q={query}")
            
            print("INFO: Esperando 5s carga...")
            page.wait_for_timeout(5000)
            
            # 2. Extracción de Candidatos (Primeros 5)
            print("INFO: Analizando candidatos...")
            candidates_data = page.evaluate('''() => {
                const results = [];
                const rows = document.querySelectorAll('tr[itemtype*="Book"]');
                const listItems = document.querySelectorAll('li.book');
                const elements = rows.length > 0 ? rows : listItems;
                
                for (let i = 0; i < Math.min(elements.length, 5); i++) {
                    const el = elements[i];
                    const titleEl = el.querySelector('.bookTitle span') || el.querySelector('.bookTitle');
                    const authorEl = el.querySelector('.authorName span') || el.querySelector('.authorName');
                    
                    results.push({
                        index: i,
                        title: titleEl ? titleEl.innerText : "",
                        author: authorEl ? authorEl.innerText : "",
                        is_table: rows.length > 0
                    });
                }
                return results;
            }''')
            
            best_match = None
            best_score = 0
            
            for candidate in candidates_data:
                # Calcular Scores
                cand_title = candidate['title']
                cand_title_clean = cand_title.split('(')[0].strip()
                
                title_score = fuzz.token_set_ratio(data.titulo.lower(), cand_title_clean.lower())
                author_score = fuzz.token_sort_ratio(data.autor.lower(), candidate['author'].lower())
                total_score = (title_score * 0.6) + (author_score * 0.4)
                
                # Detección y Manejo de Sagas
                import re
                # Detectar número de saga en el candidato: puede ser "#2" o "(Serie, #2)" 
                saga_match = re.search(r'#(\d+(\.\d+)?)', cand_title)
                
                # Detectar número en el título del usuario: puede ser "#2" o simplemente " 2" al final
                # Primero intentamos con #
                user_saga = re.search(r'#(\d+(\.\d+)?)', data.titulo)
                if not user_saga:
                    # Si no tiene #, buscar número al final del título (ej. "El Psicoanalista 2")
                    user_saga = re.search(r'\s+(\d+(\.\d+)?)$', data.titulo.strip())

                
                if user_saga:
                    # El usuario PIDIÓ un número específico (ej. #2)
                    user_num = float(user_saga.group(1))
                    
                    if saga_match:
                        cand_num = float(saga_match.group(1))
                        if cand_num == user_num:
                            # ¡Match exacto de número! Bonificar fuertemente
                            total_score += 20
                            print(f"   -> BONIFICANDO '{cand_title}' por coincidir con #{user_num}")
                        else:
                            # Número diferente al solicitado, penalizar
                            total_score -= 25
                            print(f"   -> Penalizando '{cand_title}' (es #{cand_num}, se pidió #{user_num})")
                    else:
                        # Candidato sin número, pero usuario pidió uno específico
                        total_score -= 10
                else:
                    # El usuario NO especificó número (busca el libro base o #1)
                    if saga_match:
                        num = float(saga_match.group(1))
                        if num > 1.0:
                            # Penalizar secuelas si no se pidió número
                            total_score -= 15
                            print(f"   -> Penalizando '{cand_title}' por ser secuela #{num} no solicitada")
                
                print(f"   Candidato {candidate['index']}: {cand_title} - Score: {total_score:.1f}")
                
                if total_score > best_score and total_score >= MIN_CONFIDENCE:
                    best_match = candidate
                    best_score = total_score
            
            # 3. Procesar Ganador
            if best_match:
                print(f"MATCH: '{best_match['title']}' ({best_score:.1f})")
                
                # Obtener ElementHandle
                selector_base = "tr[itemtype*='Book']" if best_match['is_table'] else "li.book"
                element = page.evaluate_handle(f'document.querySelectorAll("{selector_base}")[{best_match["index"]}]').as_element()
                
                # 4. Actualizar Estado
                status_btn = element.query_selector('.wtrStatusReadingNow')
                
                if status_btn:
                    print("INFO: Ya en 'Currently Reading'.")
                    # Hover para mostrar el formulario (o sobre el contenedor si existe)
                    wtr_down = element.query_selector('.wtrDown')
                    if wtr_down: wtr_down.hover()
                    else: status_btn.hover()
                    page.wait_for_timeout(1000)
                    
                    # Preparar JS
                    prep_result = prepare_form_js(page, element)
                    if prep_result['success']:
                        update_pages_js(page, element, data, prep_result['totalPages'])
                    else:
                        print(f"WARNING: No se pudo preparar formulario: {prep_result['error']}")
                else:
                    print("INFO: No está en lectura. Marcando...")
                    shelf_btn = element.query_selector('.wtrShelfButton')
                    if shelf_btn:
                        shelf_btn.click()
                        page.wait_for_timeout(1000)
                        
                        cr_btn = element.query_selector('button[value="currently-reading"]')
                        if cr_btn:
                            cr_btn.click()
                            page.wait_for_timeout(2000)
                            print("INFO: Marcado como Currently Reading.")
                            
                            # Intentar actualizar páginas ahora
                            # Recargar selectores
                            status_btn_new = element.query_selector('.wtrStatusReadingNow')
                            if status_btn_new:
                                status_btn_new.hover()
                                page.wait_for_timeout(1500)
                                prep = prepare_form_js(page, element)
                                if prep['success']:
                                    update_pages_js(page, element, data, prep['totalPages'])
                        else:
                            print("WARNING: Botón Currently Reading no encontrado en menú.")
                    else:
                        print("WARNING: Botón de estante no encontrado.")
            else:
                print(f"ERROR: No se encontró libro coincidente.")

        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}")
        finally:
            browser.close()
