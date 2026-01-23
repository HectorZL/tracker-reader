# ✅ Checklist de Configuración de Render

## 📋 Archivos Críticos

- ✅ `requirements.txt` - Incluye todas las dependencias con versiones específicas
- ✅ `install_playwright.sh` - Script que instala Playwright y Chromium automáticamente
- ✅ `main.py` - Puerto dinámico usando variable `$PORT`
- ✅ `Procfile` - Comando de inicio correcto
- ✅ `.env.render` - Variables de entorno recomendadas

## 🔧 Configuración en Render Dashboard

### Build Command (CRÍTICO)
```bash
chmod +x install_playwright.sh && ./install_playwright.sh
```

### Start Command
```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### Variables de Entorno (TODAS OBLIGATORIAS)

| Variable | Valor | ¿Por qué es importante? |
|----------|-------|-------------------------|
| `PYTHON_VERSION` | `3.11.0` | Define la versión de Python |
| `HEADLESS` | `True` | Playwright sin interfaz gráfica |
| `PLAYWRIGHT_BROWSERS_PATH` | `0` | ⚠️ **CRÍTICO** - Ubicación de navegadores |
| `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD` | `0` | ⚠️ **CRÍTICO** - Fuerza descarga de Chromium |
| `RENDER_EXTERNAL_URL` | `https://tracker-reader.onrender.com` | Para auto-ping (opcional) |

## 🚨 Si obtienes el error "Executable doesn't exist"

1. ✅ Verifica que el **Build Command** sea exactamente el de arriba
2. ✅ Confirma que las variables `PLAYWRIGHT_BROWSERS_PATH` y `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD` estén configuradas
3. ✅ Revisa los logs de build y busca:
   - `playwright install chromium` ✅
   - `playwright install-deps chromium` ✅
4. ✅ Haz un **Manual Deploy** desde Render Dashboard

## 📝 Orden de Pasos en Render

1. Crear nuevo Web Service
2. Conectar repositorio Git
3. Configurar:
   - Runtime: `Python 3`
   - Build Command: `chmod +x install_playwright.sh && ./install_playwright.sh`
   - Start Command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Agregar **TODAS** las variables de entorno
5. Click en "Create Web Service"
6. Esperar 5-10 minutos
7. Verificar con: `https://tu-app.onrender.com/ping`

## ✅ Verificación Post-Deploy

```bash
# Health check
curl https://tracker-reader.onrender.com/ping

# Debería retornar:
{
  "status": "alive",
  "timestamp": "...",
  "message": "Server is running"
}
```

## 🔄 Si necesitas redeploy

1. Ve a tu servicio en Render Dashboard
2. Click en "Manual Deploy" → "Deploy latest commit"
3. Espera a que termine el build
4. Verifica los logs para confirmar que Playwright se instaló
