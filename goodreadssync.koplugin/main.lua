local WidgetContainer = require("ui/widget/container/widgetcontainer")
local UIManager = require("ui/uimanager")
local InfoMessage = require("ui/widget/infomessage")
local InputDialog = require("ui/widget/inputdialog")
local https = require("ssl.https")
local ltn12 = require("ltn12")
local _ = require("gettext")

local API_URL = "https://tracker-reader.onrender.com"

local GoodreadsSync = WidgetContainer:extend{
    name = "goodreadssync",
}

function GoodreadsSync:init()
    self.ui.menu:registerToMainMenu(self)
    self.settings = G_reader_settings:readSetting("goodreadssync") or {}
end

function GoodreadsSync:addToMainMenu(menu_items)
    menu_items.goodreadssync = {
        text = _("Goodreads Sync"),
        sub_item_table = {
            {
                text = _("Login"),
                callback = function()
                    self:showLoginDialog()
                end,
            },
            {
                text = _("Sincronizar"),
                callback = function()
                    self:syncProgress()
                end,
            },
            {
                text = _("Estado"),
                callback = function()
                    self:showStatus()
                end,
            },
        },
    }
end

function GoodreadsSync:showLoginDialog()
    local email_dialog
    email_dialog = InputDialog:new{
        title = _("Email de Goodreads"),
        input = self.settings.email or "",
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
                        self:showPasswordDialog(email)
                    end,
                },
            }
        },
    }
    UIManager:show(email_dialog)
    email_dialog:onShowKeyboard()
end

function GoodreadsSync:showPasswordDialog(email)
    local pass_dialog
    pass_dialog = InputDialog:new{
        title = _("Password"),
        text_type = "password",
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
                        self:doLogin(email, password)
                    end,
                },
            }
        },
    }
    UIManager:show(pass_dialog)
    pass_dialog:onShowKeyboard()
end

function GoodreadsSync:httpPost(url, body)
    local response_body = {}
    local res, code, headers, status = https.request{
        url = url,
        method = "POST",
        headers = {
            ["Content-Type"] = "application/json",
            ["Content-Length"] = tostring(#body)
        },
        source = ltn12.source.string(body),
        sink = ltn12.sink.table(response_body),
        protocol = "any",
        options = "all",
        verify = "none"
    }
    
    if res == 1 then
        return table.concat(response_body), code
    else
        return nil, tostring(code)
    end
end

function GoodreadsSync:doLogin(email, password)
    UIManager:show(InfoMessage:new{
        text = _("Conectando..."),
        timeout = 1,
    })
    
    local body = '{"username":"' .. email .. '","password":"' .. password .. '"}'
    local resp, code = self:httpPost(API_URL .. "/login", body)
    
    if not resp then
        UIManager:show(InfoMessage:new{
            text = _("Error: ") .. tostring(code),
            timeout = 3,
        })
        return
    end
    
    local uid = resp:match('"user_id"%s*:%s*"([^"]+)"')
    
    if uid then
        self.settings.user_id = uid
        self.settings.email = email
        G_reader_settings:saveSetting("goodreadssync", self.settings)
        G_reader_settings:flush()
        UIManager:show(InfoMessage:new{
            text = _("Login OK!"),
            timeout = 2,
        })
    else
        UIManager:show(InfoMessage:new{
            text = _("Login fallido: ") .. tostring(code) .. "\n" .. (resp or ""),
            timeout = 5,
        })
    end
end

function GoodreadsSync:showStatus()
    local msg
    if self.settings.user_id then
        msg = "Sesion activa\nEmail: " .. (self.settings.email or "?")
    else
        msg = "Sin sesion"
    end
    UIManager:show(InfoMessage:new{
        text = msg,
        timeout = 4,
    })
end

-- Escapar caracteres especiales para JSON
local function escapeJSON(str)
    if not str then return "" end
    str = str:gsub('\\', '\\\\')
    str = str:gsub('"', '\\"')
    str = str:gsub('\n', '\\n')
    str = str:gsub('\r', '\\r')
    str = str:gsub('\t', '\\t')
    return str
end

function GoodreadsSync:syncProgress()
    if not self.settings.user_id then
        UIManager:show(InfoMessage:new{
            text = _("Haz login primero"),
            timeout = 2,
        })
        return
    end
    
    local doc = self.ui.document
    if not doc then
        UIManager:show(InfoMessage:new{
            text = _("Abre un libro"),
            timeout = 2,
        })
        return
    end
    
    -- Usar pcall para capturar errores
    local success, error_msg = pcall(function()
        local props = doc:getProps()
        local titulo = escapeJSON(props.title or "Desconocido")
        local autor = escapeJSON(props.authors or "Desconocido")
        
        -- Obtener página actual y total correctamente
        local pag, total
        
        -- Para documentos PDF o con páginas fijas (paging mode)
        if self.ui.paging then
            pag = self.ui.paging.current_page or 1
            total = self.ui.document:getPageCount() or 1
            
        -- Para EPUB u otros documentos reflowables (rolling mode)
        elseif self.ui.rolling then
            -- Obtener el view (ReaderView)
            local view = self.ui.view
            if view and view.state then
                -- state.page contiene el número de página actual
                pag = view.state.page or 1
                -- Obtener el número total de páginas del documento
                total = self.ui.document:getPageCount() or 100
                
                -- Asegurarse de que los valores sean válidos
                if pag > total then
                    pag = total
                end
            else
                -- Fallback: intentar obtener de estadísticas
                local stats = self.ui.doc_settings:readSetting("stats") or {}
                pag = stats.page or 1
                total = self.ui.document:getPageCount() or 100
            end
        else
            -- Último fallback
            pag = 1
            total = self.ui.document:getPageCount() or 100
        end
        
        -- Asegurar que los valores sean números válidos
        pag = tonumber(pag) or 1
        total = tonumber(total) or 100
        
        -- Asegurar que pag no sea mayor que total
        if pag > total then
            pag = total
        end
        
        local body = '{"user_id":"' .. self.settings.user_id .. '",'
        body = body .. '"titulo":"' .. titulo .. '",'
        body = body .. '"autor":"' .. autor .. '",'
        body = body .. '"isbn":"",'
        body = body .. '"pagina_actual":' .. tostring(pag) .. ','
        body = body .. '"total_paginas":' .. tostring(total) .. ','
        body = body .. '"dispositivo":"KOReader"}'
        
        self:httpPost(API_URL .. "/sync", body)
    end)
    
    if success then
        UIManager:show(InfoMessage:new{
            text = "Sincronizado OK",
            timeout = 2,
        })
    else
        UIManager:show(InfoMessage:new{
            text = "Error: " .. tostring(error_msg),
            timeout = 3,
        })
    end
end

function GoodreadsSync:onCloseDocument()
    if self.settings.user_id then
        self:syncProgress()
    end
end

return GoodreadsSync
