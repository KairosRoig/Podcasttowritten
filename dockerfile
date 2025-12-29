# Usar imagen base de Python
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para audio
RUN apt-get update && apt-get install -y \
    libsndfile1 \
    libsndfile1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código de la aplicación
COPY main.py .

# Exponer el puerto de Streamlit
EXPOSE 8501

# Configurar Streamlit
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Comando para ejecutar la aplicación
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0"]