# 1. Usamos la imagen oficial de Playwright que ya tiene TODO configurado
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Evitar archivos .pyc y permitir logs fluidos
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# 2. Instalar dependencias de Python
COPY requirements.txt .
# Instalamos setuptools para evitar el error de pkg_resources en Python 3.12+
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir setuptools && \
    pip install --no-cache-dir -r requirements.txt

# 3. Copiar el código de la aplicación
COPY . .

# 4. El navegador ya está instalado en la imagen base, 
# pero nos aseguramos de que Chromium esté listo
RUN playwright install chromium

# Puerto de Render
EXPOSE 10000

# Comando para arrancar
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]