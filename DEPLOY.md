# 🚀 Guía de Despliegue en Render.com

Esta guía te ayudará a desplegar la API de Goodreads Tracker en Render.com (Free Tier).

## 📋 Pre-requisitos

1. Cuenta en [Render.com](https://render.com)
2. Repositorio Git con el código (GitHub, GitLab, o Bitbucket)

---

## 🔧 Configuración en Render

### 1. Crear un nuevo Web Service

1. Ve a tu [Dashboard de Render](https://dashboard.render.com/)
2. Click en **"New +"** → **"Web Service"**
3. Conecta tu repositorio Git

### 2. Configuración del Servicio

Completa los siguientes campos:

| Campo | Valor |
|-------|-------|
| **Name** | `goodreads-tracker-api` (o el nombre que prefieras) |
| **Region** | Selecciona la región más cercana |
| **Branch** | `main` (o tu rama principal) |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt && playwright install chromium && playwright install-deps` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | `Free` |

### 3. Variables de Entorno

En la sección **"Environment"**, añade las siguientes variables:

| Key | Value | Descripción |
|-----|-------|-------------|
| `HEADLESS` | `True` | Ejecuta Playwright en modo headless (sin UI) |
| `PYTHON_VERSION` | `3.11.0` | Versión de Python a usar |
| `RENDER_EXTERNAL_URL` | `https://tu-app.onrender.com` | URL de tu app (cámbiala después del primer deploy) |

> **Nota**: Después del primer despliegue, actualiza `RENDER_EXTERNAL_URL` con la URL real que Render te asigne.

### 4. Deploy

1. Click en **"Create Web Service"**
2. Render comenzará a construir y desplegar tu aplicación
3. El proceso puede tardar 5-10 minutos la primera vez

---

## ✅ Verificación

Una vez desplegado, verifica que todo funciona:

### 1. Health Check
```bash
curl https://tu-app.onrender.com/ping
```

Deberías recibir:
```json
{
  "status": "alive",
  "timestamp": "2026-01-23T16:09:22.123456",
  "message": "Server is running"
}
```

### 2. Documentación Interactiva

Visita `https://tu-app.onrender.com/docs` para ver la documentación automática de FastAPI.

---

## 🏓 Sistema de Auto-Ping

La API incluye un sistema de **auto-ping** que:

- ✅ Hace ping a sí misma cada **10 minutos**
- ✅ Evita que Render Free Tier suspenda el servidor por inactividad (15 min)
- ✅ Se activa automáticamente al iniciar el servidor
- ✅ Muestra logs en la consola de Render

### Logs esperados:

```
✅ Auto-ping activado - El servidor se mantendrá activo
🏓 Auto-ping exitoso: 200 - 2026-01-23T16:19:22.123456
🏓 Auto-ping exitoso: 200 - 2026-01-23T16:29:22.123456
```

---

## ⚠️ Limitaciones de Render Free Tier

1. **Sin persistencia de archivos**: La carpeta `sessions/` se borra cada vez que el servidor se reinicia
   - **Solución**: Los usuarios deberán hacer login nuevamente si el servidor se reinicia
   - **Alternativa**: Migrar a una base de datos externa (MongoDB Atlas, PostgreSQL)

2. **Timeout de 30 segundos**: Las peticiones HTTP tienen un límite de 30s
   - El scraper puede tardar más en algunos casos
   - La sincronización se ejecuta en **background** para evitar timeouts

3. **Suspensión por inactividad**: Sin el auto-ping, el servidor se suspende después de 15 minutos
   - El auto-ping lo mantiene activo indefinidamente

---

## 🔄 Actualizar el Despliegue

Render detecta automáticamente cambios en tu repositorio Git:

1. Haz `git push` a tu rama principal
2. Render reconstruirá y redesplegar automáticamente
3. El proceso tarda ~3-5 minutos

---

## 📱 Configurar KOReader Plugin

Una vez desplegada la API, configura el plugin de KOReader:

1. Abre cualquier libro en KOReader
2. Menú superior → **Hector's Tracker** → **Configurar Servidor**
3. Ingresa la URL: `https://tu-app.onrender.com`
4. Guarda la configuración
5. Realiza el login desde el plugin

---

## 🐛 Troubleshooting

### El servidor se suspende a pesar del auto-ping

**Causa**: La variable `RENDER_EXTERNAL_URL` no está configurada correctamente.

**Solución**:
1. Ve a tu servicio en Render
2. Copia la URL completa (ej: `https://goodreads-tracker-api.onrender.com`)
3. Actualiza la variable de entorno `RENDER_EXTERNAL_URL`
4. Redeploy manual si es necesario

### Error: "playwright install-deps failed"

**Causa**: Render Free Tier tiene limitaciones de memoria.

**Solución**:
1. Intenta redeploy (a veces funciona en el segundo intento)
2. Si persiste, considera usar el plan Starter ($7/mes)

### Las sesiones se pierden constantemente

**Causa**: Render Free Tier no tiene persistencia de disco.

**Solución**:
- Implementar almacenamiento en base de datos externa (próxima actualización)
- O usar Render Starter plan que sí tiene persistencia

---

## 📞 Soporte

Si encuentras problemas:

1. Revisa los logs en Render Dashboard → Tu servicio → Logs
2. Verifica que todas las variables de entorno estén configuradas
3. Prueba el endpoint `/ping` para confirmar que el servidor está activo

---

## 🎯 Próximos Pasos

- [ ] Migrar sesiones a MongoDB Atlas (gratis)
- [ ] Implementar caché de búsquedas
- [ ] Añadir métricas de uso
- [ ] Dockerizar la aplicación
