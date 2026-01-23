# Hector's Goodreads Tracker - Plugin para KOReader

Plugin para sincronizar automáticamente tu progreso de lectura con Goodreads usando tu API personalizada.

## Instalación

1. Copia la carpeta `tracker_hector.koplugin` a la carpeta de plugins de KOReader:
   - **Android**: `/sdcard/koreader/plugins/`
   - **Kobo**: `.adds/koreader/plugins/`
   - **Kindle**: `koreader/plugins/`

2. Reinicia KOReader.

## Configuración Inicial

1. Abre cualquier libro en KOReader.
2. Toca el menú superior → **Hector's Tracker** → **Configurar Servidor**.
3. Ingresa la URL de tu servidor API (ej: `http://192.168.1.100:8000`).
4. Ingresa tu email y contraseña de Goodreads cuando se te solicite.
5. El plugin guardará tu token de sesión automáticamente.

## Uso

### Sincronización Manual
- Menú → **Hector's Tracker** → **Sincronizar Ahora**

### Sincronización Automática
- El plugin sincroniza automáticamente cuando cierras un libro.

### Ver Estado
- Menú → **Hector's Tracker** → **Estado de Sesión**

## Requisitos

- Servidor API corriendo en tu red local (puerto 8000).
- KOReader con acceso a red (WiFi).
- Cuenta de Goodreads.

## Troubleshooting

**"No hay sesión activa"**: Configura el servidor y haz login primero.

**"Error en login"**: Verifica que:
- La URL del servidor sea correcta.
- El servidor esté corriendo (`python main.py`).
- Tu email/contraseña sean correctos.

**No sincroniza**: Verifica que tu dispositivo esté en la misma red que el servidor.

## Arquitectura

```
KOReader (Plugin Lua)
    ↓ HTTP POST
Tu Servidor FastAPI (main.py)
    ↓ Playwright
Goodreads.com
```

El plugin envía:
- `user_id`: Token de sesión
- `titulo`: Título del libro
- `autor`: Autor del libro
- `pagina_actual`: Página en la que vas
- `total_paginas`: Total de páginas del libro

## Autor

Hector Zambrano - 2026
