# API de Baja Gas - FastAPI + SQLAlchemy sobre SQLite.
FROM python:3.12-slim

# tzdata NO viene en la imagen slim, y aqui no es un adorno:
# core/tiempo.py hace ZoneInfo("America/Tijuana") dentro de un try/except que,
# si falla, se cae en silencio a UTC. Sin este paquete el contenedor calcularia
# el dia operativo con siete u ocho horas de corrimiento y nadie se enteraria.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tzdata \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Tijuana

WORKDIR /srv

# Las dependencias van en su propia capa: cambiar codigo no reinstala nada.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# La base NO vive dentro de la imagen: vive en un volumen, para que reconstruir
# el contenedor no borre lo capturado en el demo.
ENV DATABASE_URL=sqlite:////datos/bajagas.db
EXPOSE 8000

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
