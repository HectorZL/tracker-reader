from playwright.sync_api import Page

def update_pages_js(page: Page, container, data, goodreads_total_pages: int):
    """
    Función auxiliar para actualizar las páginas manipulando el DOM directamente con JS.
    Aísla la lógica compleja de interacción con el formulario de Goodreads.
    """
    try:
        # Calcular página objetivo en Python (más seguro/limpio que en JS)
        final_page = data.pagina_actual
        if goodreads_total_pages > 0 and data.total_paginas > 0:
            proporcion = data.pagina_actual / data.total_paginas
            final_page = int(proporcion * goodreads_total_pages)
            final_page = min(final_page, goodreads_total_pages)
            print(f"INFO: Calculando página: {data.pagina_actual}/{data.total_paginas} -> {final_page} (Total GR: {goodreads_total_pages})")
            
        # Script JS de acción con logging detallado
        result = page.evaluate("""
            ([container, pageValue]) => {
                console.log('DEBUG: Iniciando update_pages_js con pageValue:', pageValue);
                
                const pageInput = container.querySelector('input[name="user_status[page]"]');
                console.log('DEBUG: pageInput encontrado?', !!pageInput);
                
                const submitBtn = container.querySelector('button.gr-form--compact__submitButton');
                console.log('DEBUG: submitBtn encontrado?', !!submitBtn);
                
                const toggleBtn = container.querySelector('.wtrNewUserStatusProgressTypeToggle');
                console.log('DEBUG: toggleBtn encontrado?', !!toggleBtn);
                
                // Asegurar modo página
                if (toggleBtn && pageInput && !pageInput.offsetParent) {
                    console.log('DEBUG: Haciendo toggle para mostrar input de página');
                    toggleBtn.click();
                }
                
                // Llenar valor
                if (pageInput) {
                    pageInput.value = pageValue;
                    console.log('DEBUG: Valor asignado al input:', pageInput.value);
                    // Disparar eventos para que Frameworks reactivos detecten el cambio
                    pageInput.dispatchEvent(new Event('change', { bubbles: true }));
                    pageInput.dispatchEvent(new Event('input', { bubbles: true }));
                } else {
                    return { success: false, error: 'Input de página no encontrado' };
                }
                
                // Submit
                if (submitBtn) {
                    console.log('DEBUG: Haciendo click en submit button');
                    submitBtn.click();
                    return { success: true };
                } else {
                    return { success: false, error: 'Botón submit no encontrado' };
                }
            }
        """, [container, str(final_page)])
        
        if result.get('success'):
            print(f"SUCCESS: Progreso actualizado a página {final_page}")
            page.wait_for_timeout(2000)
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"ERROR actualizando páginas (JS): {str(e)}")

def prepare_form_js(page: Page, container):
    """
    Prepara el formulario: lo hace visible y extrae info inicial (total paginas).
    Retorna un diccionario con {success: bool, totalPages: int, error: str}
    """
    js_script = """
    (container) => {
        console.log('DEBUG prepare_form: Iniciando...');
        
        const formContainer = container.querySelector('.wtrFloatingBox.wtrNewUserStatus');
        console.log('DEBUG prepare_form: formContainer encontrado?', !!formContainer);
        
        if (!formContainer) return { success: false, error: "Contenedor de formulario no encontrado" };
        
        // 1. Forzar visibilidad del formulario
        formContainer.style.display = 'block';
        formContainer.style.visibility = 'visible';
        formContainer.style.opacity = '1';
        console.log('DEBUG prepare_form: Formulario forzado a visible');
        
        // 2. Buscar input de páginas para validar
        const pageInput = container.querySelector('input[name="user_status[page]"]');
        console.log('DEBUG prepare_form: pageInput encontrado?', !!pageInput);
        
        if (!pageInput) return { success: false, error: "Input de página no encontrado" };
        
        // 3. Extraer total de páginas de Goodreads para cálculo proporcional
        let totalPages = 0;
        const text = container.innerText || "";
        const match = text.match(/of\\s+(\\d+)/);
        if (match) {
            totalPages = parseInt(match[1]);
            console.log('DEBUG prepare_form: Total páginas extraído:', totalPages);
        } else {
            console.log('DEBUG prepare_form: No se pudo extraer total de páginas del texto');
        }
        
        return { success: true, totalPages: totalPages };
    }
    """
    result = page.evaluate(js_script, container)
    print(f"DEBUG prepare_form_js result: {result}")
    return result
