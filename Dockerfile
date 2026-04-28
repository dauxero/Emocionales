FROM python:3.11-slim

WORKDIR /app

# Variables para que los modelos se almacenen dentro de la imagen
ENV HF_HOME=/app/models
ENV TRANSFORMERS_CACHE=/app/models

# Dependencias de sistema mínimas
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# PyTorch CPU (mucho más ligero que la versión con CUDA)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descargar modelos de Hugging Face en la imagen
COPY preload_models.py .
RUN python preload_models.py

# Código de la aplicación
COPY main.py .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
