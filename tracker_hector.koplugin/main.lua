local WidgetContainer = require("ui/widget/container/widgetcontainer")
local UIManager = require("ui/uimanager")
local InfoMessage = require("ui/widget/infomessage")
local InputDialog = require("ui/widget/inputdialog")
local NetworkMgr = require("ui/network/manager")
local logger = require("logger")
local _ = require("gettext")

local HectorTracker = WidgetContainer:extend{
    name = "tracker_hector",
}

function HectorTracker:init()
    self.ui.menu:registerToMainMenu(self)
    -- Cargar configuración guardada
    self.settings = G_reader_settings:readSetting("tracker_hector") or {}
end

function HectorTracker:addToMainMenu(menu_items)
    menu_items.tracker_hector = {
        text = _("Hector's Tracker"),
        sub_item_table = {
            {
                text = _("Configurar Servidor"),
                keep_menu_open = true,
                callback = function()
                    self:mostrarConfiguracion()
                end,
            },
            {
                text = _("Sincronizar Ahora"),
                callback = function()
                    self:sincronizarProgreso()
                end,
            },
            {
                text = _("Estado de Sesión"),
                callback = function()
                    self:mostrarEstadoSesion()
                end,
            },
        },
    }
end

function HectorTracker:mostrarConfiguracion()
    local input_dialog
    input_dialog = InputDialog:new{
        title = _("Configuración del Servidor"),
        input = self.settings.api_url or "http://192.168.1.100:8000",
        input_hint = _("URL del servidor (ej: http://192.168.1.100:8000)"),
        buttons = {
            {
                {
                    text = _("Cancelar"),
                    callback = function()
                        UIManager:close(input_dialog)
                    end,
                },
                {
                    text = _("Guardar"),
                    is_enter_default = true,
                    callback = function()
                        self.settings.api_url = input_dialog:getInputText()
                        G_reader_settings:saveSetting("tracker_hector", self.settings)
                        UIManager:close(input_dialog)
                        UIManager:show(InfoMessage:new{
                            text = _("Configuración guardada"),
                            timeout = 2,
                        })
                        -- Ahora pedir login
                        self:mostrarLoginDialog()
                    end,
                },
            }
        },
    }
    UIManager:show(input_dialog)
    input_dialog:onShowKeyboard()
end

function HectorTracker:mostrarLoginDialog()
    local email_dialog
    email_dialog = InputDialog:new{
        title = _("Email de Goodreads"),
        input = self.settings.email or "",
        input_hint = _("tu_email@ejemplo.com"),
        buttons = {
            {
                {
                    text = _("Cancelar"),
                    callback = function()
                        UIManager:close(email_dialog)
                    end,
                },
                {
                    text = _("Siguiente"),
                    is_enter_default = true,
                    callback = function()
                        local email = email_dialog:getInputText()
                        UIManager:close(email_dialog)
                        self:mostrarPasswordDialog(email)
                    end,
                },
            }
        },
    }
    UIManager:show(email_dialog)
    email_dialog:onShowKeyboard()
end

function HectorTracker:mostrarPasswordDialog(email)
    local pass_dialog
    pass_dialog = InputDialog:new{
        title = _("Contraseña de Goodreads"),
        input_type = "text",
        text_type = "password",
        input_hint = _("Contraseña"),
        buttons = {
            {
                {
                    text = _("Cancelar"),
                    callback = function()
                        UIManager:close(pass_dialog)
                    end,
                },
                {
                    text = _("Login"),
                    is_enter_default = true,
                    callback = function()
                        local password = pass_dialog:getInputText()
                        UIManager:close(pass_dialog)
                        self:realizarLogin(email, password)
                    end,
                },
            }
        },
    }
    UIManager:show(pass_dialog)
    pass_dialog:onShowKeyboard()
end

function HectorTracker:realizarLogin(email, password)
    UIManager:show(InfoMessage:new{
        text = _("Conectando con Goodreads..."),
        timeout = 2,
    })
    
    local api_url = self.settings.api_url or "http://192.168.1.100:8000"
    local login_url = api_url .. "/login"
    
    local payload = string.format('{"username":"%s","password":"%s"}', email, password)
    
    local cmd = string.format(
        "curl -X POST -H 'Content-Type: application/json' -d '%s' '%s' 2>/dev/null",
        payload:gsub("'", "'\\''"),
        login_url
    )
    
    local handle = io.popen(cmd)
    local response = handle:read("*a")
    handle:close()
    
    -- Parsear respuesta JSON simple (buscar user_id)
    local user_id = response:match('"user_id"%s*:%s*"([^"]+)"')
    
    if user_id then
        self.settings.user_id = user_id
        self.settings.email = email
        G_reader_settings:saveSetting("tracker_hector", self.settings)
        
        UIManager:show(InfoMessage:new{
            text = _("¡Login exitoso! Token guardado."),
            timeout = 3,
        })
    else
        UIManager:show(InfoMessage:new{
            text = _("Error en login. Verifica tus credenciales."),
            timeout = 3,
        })
    end
end

function HectorTracker:mostrarEstadoSesion()
    local estado
    if self.settings.user_id then
        estado = string.format("✓ Sesión activa\nEmail: %s\nToken: %s...", 
            self.settings.email or "N/A",
            self.settings.user_id:sub(1, 8))
    else
        estado = "✗ No hay sesión activa\nConfigura el servidor primero."
    end
    
    UIManager:show(InfoMessage:new{
        text = estado,
        timeout = 5,
    })
end

function HectorTracker:sincronizarProgreso()
    if not self.settings.user_id then
        UIManager:show(InfoMessage:new{
            text = _("Primero debes configurar el servidor y hacer login"),
            timeout = 3,
        })
        return
    end
    
    -- Extraer metadatos del libro actual
    local doc = self.ui.document
    local props = doc:getProps()
    
    local titulo = props.title or "Sin Título"
    local autor = props.authors or "Autor Desconocido"
    
    -- Obtener páginas actuales
    local stats = self.ui.doc_settings:readSetting("stats") or {}
    local pagina_actual = self.ui.paging:getCurrentPage()
    local total_paginas = self.ui.document:getPageCount()
    
    -- Construir payload
    local payload = string.format(
        '{"user_id":"%s","titulo":"%s","autor":"%s","pagina_actual":%d,"total_paginas":%d}',
        self.settings.user_id,
        titulo:gsub('"', '\\"'),
        autor:gsub('"', '\\"'),
        pagina_actual,
        total_paginas
    )
    
    local api_url = self.settings.api_url or "http://192.168.1.100:8000"
    local sync_url = api_url .. "/sync"
    
    local cmd = string.format(
        "curl -X POST -H 'Content-Type: application/json' -d '%s' '%s' &",
        payload:gsub("'", "'\\''"),
        sync_url
    )
    
    os.execute(cmd)
    
    UIManager:show(InfoMessage:new{
        text = string.format("Sincronizando: %s\nPágina %d/%d", titulo, pagina_actual, total_paginas),
        timeout = 3,
    })
end

-- Hook automático al cerrar el libro
function HectorTracker:onCloseDocument()
    if self.settings.user_id and self.settings.auto_sync ~= false then
        self:sincronizarProgreso()
    end
end

return HectorTracker
