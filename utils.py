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
            
        # Script JS de acción (Llenar y Enviar)
        # Usamos evaluate pasando los argumentos necesarios
        page.evaluate("""
            ([container, pageValue]) => {
                const pageInput = container.querySelector('input[name="user_status[page]"]');
                const submitBtn = container.querySelector('button.gr-form--compact__submitButton');
                const toggleBtn = container.querySelector('.wtrNewUserStatusProgressTypeToggle');
                
                // Asegurar modo página
                // Si el input está oculto o no visible, intentar toggle
                if (toggleBtn && pageInput && !pageInput.offsetParent) {
                     toggleBtn.click();
                }
                
                // Llenar valor
                if (pageInput) {
                    pageInput.value = pageValue;
                    // Disparar eventos para que Frameworks reactivos detecten el cambio
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
        print(f"ERROR actualizando páginas (JS): {str(e)}")

def prepare_form_js(page: Page, container):
    """
    Prepara el formulario: lo hace visible y extrae info inicial (total paginas).
    Retorna un diccionario con {success: bool, totalPages: int, error: str}
    """
    js_script = """
    (container) => {
        const formContainer = container.querySelector('.wtrFloatingBox.wtrNewUserStatus');
        if (!formContainer) return { success: false, error: "Contenedor de formulario no encontrado" };
        
        // 1. Forzar visibilidad del formulario
        formContainer.style.display = 'block';
        formContainer.style.visibility = 'visible';
        formContainer.style.opacity = '1';
        
        // 2. Buscar input de páginas para validar
        const pageInput = container.querySelector('input[name="user_status[page]"]');
        if (!pageInput) return { success: false, error: "Input de página no encontrado" };
        
        // 3. Extraer total de páginas de Goodreads para cálculo proporcional
        let totalPages = 0;
        const text = container.innerText || "";
        const match = text.match(/of\\s+(\\d+)/);
        if (match) totalPages = parseInt(match[1]);
        
        return { success: true, totalPages: totalPages };
    }
    """
    return page.evaluate(js_script, container)
