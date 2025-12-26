# Usamos la imagen oficial de Playwright con Python
# Esta imagen ya trae las dependencias de sistema para correr navegadores
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Directorio de trabajo
WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar el navegador específico (Chromium) para ahorrar espacio
RUN playwright install chromium

# Copiar el resto del código
COPY . .

# Puerto donde corre FastAPI
EXPOSE 8000

# Comando para iniciar la aplicación
# Usamos uvicorn para correr la API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
