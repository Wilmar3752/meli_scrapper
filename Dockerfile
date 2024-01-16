# Usar una imagen base de Python
FROM python:3.10

# Establecer el directorio de trabajo en /app
WORKDIR /app

# Copiar los archivos de requisitos y el archivo Dockerfile en el contenedor
COPY requirements.txt ./
COPY api/ ./api/
COPY src/ ./src/

# Instalar las dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Establecer PYTHONPATH al directorio raíz
ENV PYTHONPATH "${PYTHONPATH}:/app"

# Exponer el puerto 8000 para que otros contenedores puedan acceder a tu API
EXPOSE 8000

# Comando para iniciar la aplicación
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
