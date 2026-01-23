# Usamos una imagen ligera de Python
FROM python:3.11-slim

# Evitar que Python genere archivos .pyc y permitir logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalar dependencias del sistema necesarias para Playwright y navegadores
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    libgbm-dev \
    libasound2 \
    libnss3 \
    libxss1 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar archivos de dependencias
COPY requirements.txt .

# Instalar dependencias de Python
# Agregamos setuptools para solucionar el error de pkg_resources
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir -r requirements.txt

# Instalar los navegadores de Playwright y sus dependencias de sistema
RUN playwright install chromium --with-deps

# Copiar el resto del código
COPY . .

# Exponer el puerto que Render asigna automáticamente
EXPOSE 10000

# Comando para arrancar la app con Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]