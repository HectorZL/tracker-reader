# 📚 Goodreads Tracker API

API multi-usuario para sincronizar progreso de lectura desde **KOReader** a **Goodreads** automáticamente.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.48.0-2EAD33?logo=playwright)](https://playwright.dev/)

---

## 🎯 Características

- ✅ **Multi-usuario**: Soporta múltiples usuarios simultáneos con sesiones independientes
- ✅ **Búsqueda inteligente**: Fuzzy matching avanzado para títulos y autores
- ✅ **Manejo de sagas**: Detecta y diferencia libros de series automáticamente
- ✅ **Auto-ping**: Mantiene el servidor activo en Render Free Tier
- ✅ **Sincronización en background**: No bloquea las peticiones HTTP
- ✅ **Plugin KOReader**: Integración completa con interfaz gráfica

---

## 🚀 Inicio Rápido

### Opción 1: Usar el servidor desplegado (Recomendado)

El servidor ya está desplegado y listo para usar en:

```
https://tracker-reader.onrender.com
```

Solo necesitas configurar el plugin de KOReader (ver sección [Plugin KOReader](#-plugin-koreader)).

### Opción 2: Ejecutar localmente

1. **Clonar el repositorio**
   ```bash
   git clone <tu-repositorio>
   cd api-tracker-reader
   ```

2. **Instalar dependencias**
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

3. **Ejecutar el servidor**
   ```bash
   python main.py
   ```

4. **Verificar que funciona**
   ```bash
   curl http://localhost:8000/ping
   ```

---

## 📡 API Endpoints

### `POST /login`

Inicia sesión en Goodreads y obtiene un token de usuario.

**Request:**
```json
{
  "username": "tu-email@ejemplo.com",
  "password": "tu-contraseña"
}
```

**Response:**
```json
{
  "user_id": "abc123def456",
  "status": "success",
  "message": "Login exitoso. Guarda el user_id para futuras peticiones."
}
```

### `POST /sync`

Sincroniza el progreso de lectura con Goodreads.

**Request:**
```json
{
  "user_id": "abc123def456",
  "titulo": "El Señor de los Anillos",
  "autor": "J.R.R. Tolkien",
  "pagina_actual": 150,
  "total_paginas": 500
}
```

**Response:**
```json
{
  "status": "received",
  "book": "El Señor de los Anillos",
  "user_id": "abc123def456",
  "message": "Sincronización iniciada en segundo plano"
}
```

### `GET /ping`

Health check para verificar que el servidor está activo.

**Response:**
```json
{
  "status": "alive",
  "timestamp": "2026-01-23T16:19:22.123456",
  "message": "Server is running"
}
```

### `GET /docs`

Documentación interactiva de la API (Swagger UI).

---

## 📱 Plugin KOReader

### Instalación

1. Descarga la carpeta `tracker_hector.koplugin`
2. Cópiala a la carpeta de plugins de KOReader:
   - **Android**: `/sdcard/koreader/plugins/`
   - **Kobo/Kindle**: `.adds/koreader/plugins/`
3. Reinicia KOReader

### Configuración

1. Abre cualquier libro
2. Menú superior → **Hector's Tracker** → **Configurar Servidor**
3. Ingresa la URL: `https://tracker-reader.onrender.com`
4. Guarda la configuración
5. Ve a **Login en Goodreads**
6. Ingresa tu email y contraseña de Goodreads

### Uso

**Sincronización Manual:**
- Menú → **Hector's Tracker** → **Sincronizar Ahora**

**Sincronización Automática:**
- Se sincroniza automáticamente al cerrar un libro

---

## 🏗️ Arquitectura

```
┌─────────────────┐
│   KOReader      │
│   (Plugin Lua)  │
└────────┬────────┘
         │ HTTP POST
         ▼
┌─────────────────────────────────┐
│   FastAPI Server                │
│   ┌─────────────────────────┐   │
│   │  /login   /sync  /ping  │   │
│   └───────────┬─────────────┘   │
│               │                 │
│   ┌───────────▼─────────────┐   │
│   │  ThreadPoolExecutor     │   │
│   │  (Playwright Sync API)  │   │
│   └───────────┬─────────────┘   │
│               │                 │
│   ┌───────────▼─────────────┐   │
│   │  Scraper Logic          │   │
│   │  - Login                │   │
│   │  - Search (Fuzzy)       │   │
│   │  - Update Progress      │   │
│   └─────────────────────────┘   │
└─────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│   Goodreads     │
│   (Web Scraping)│
└─────────────────┘
```

---

## 🛠️ Tecnologías

- **[FastAPI](https://fastapi.tiangolo.com/)**: Framework web moderno y rápido
- **[Playwright](https://playwright.dev/)**: Automatización de navegador para scraping
- **[Rapidfuzz](https://github.com/maxbachmann/RapidFuzz)**: Fuzzy matching de strings
- **[Pydantic](https://pydantic-docs.helpmanual.io/)**: Validación de datos
- **[httpx](https://www.python-httpx.org/)**: Cliente HTTP asíncrono

---

## 📂 Estructura del Proyecto

```
api-tracker-reader/
├── main.py                 # Punto de entrada de FastAPI
├── scraper.py              # Lógica de Playwright (login, búsqueda, actualización)
├── auth.py                 # Manejo de sesiones y user_id
├── models.py               # Modelos Pydantic
├── utils.py                # Funciones auxiliares (JS injection)
├── requirements.txt        # Dependencias Python
├── Procfile                # Configuración para Render
├── DEPLOY.md               # Guía de despliegue
├── README.md               # Este archivo
└── tracker_hector.koplugin/
    ├── _meta.lua           # Metadatos del plugin
    ├── main.lua            # Lógica del plugin KOReader
    └── README.md           # Documentación del plugin
```

---

## 🔧 Despliegue

### Render.com (Recomendado)

Consulta la [Guía de Despliegue](DEPLOY.md) para instrucciones detalladas.

**Resumen rápido:**

1. **Build Command:**
   ```bash
   pip install -r requirements.txt && playwright install chromium && playwright install-deps
   ```

2. **Start Command:**
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```

3. **Variables de Entorno:**
   - `HEADLESS=True`
   - `PYTHON_VERSION=3.11.0`

---

## 🏓 Sistema de Auto-Ping

El servidor incluye un sistema de **auto-ping** que:

- Hace ping a sí mismo cada **10 minutos**
- Evita que Render Free Tier suspenda el servidor (timeout de 15 min)
- Se activa automáticamente al iniciar
- Configurable mediante la variable `RENDER_EXTERNAL_URL`

**Logs esperados:**
```
✅ Auto-ping activado - El servidor se mantendrá activo
🏓 Auto-ping exitoso: 200 - 2026-01-23T16:19:22.123456
```

---

## ⚠️ Limitaciones

### Render Free Tier

1. **Sin persistencia de archivos**: Las sesiones se pierden al reiniciar el servidor
   - **Solución temporal**: Los usuarios deben hacer login nuevamente
   - **Solución futura**: Migrar a base de datos externa (MongoDB Atlas)

2. **Timeout de 30 segundos**: Las peticiones HTTP tienen límite de 30s
   - La sincronización se ejecuta en **background** para evitar timeouts

3. **Suspensión por inactividad**: Sin auto-ping, el servidor se suspende en 15 min
   - El auto-ping lo mantiene activo indefinidamente

---

## 🐛 Troubleshooting

### El servidor no responde

**Solución**: Verifica que el auto-ping esté funcionando en los logs de Render.

### Las sesiones se pierden constantemente

**Causa**: Render Free Tier no tiene persistencia de disco.

**Solución**: Realiza login nuevamente desde el plugin de KOReader.

### Error: "Sesión no encontrada o expirada"

**Solución**: Ejecuta el login nuevamente desde KOReader.

---

## 🎯 Roadmap

- [ ] Migrar sesiones a MongoDB Atlas (persistencia)
- [ ] Implementar caché de búsquedas
- [ ] Añadir métricas de uso
- [ ] Dockerizar la aplicación
- [ ] Soporte para otros servicios (LibraryThing, StoryGraph)

---

## 📄 Licencia

MIT License - Siéntete libre de usar y modificar este proyecto.

---

## 🙏 Contribuciones

Las contribuciones son bienvenidas! Por favor:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📞 Soporte

Si encuentras problemas:

1. Revisa la [Guía de Despliegue](DEPLOY.md)
2. Consulta la documentación del [Plugin KOReader](tracker_hector.koplugin/README.md)
3. Abre un issue en GitHub

---

**Hecho con ❤️ para la comunidad de KOReader**
