FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY config.yaml /app/config.yaml
COPY src/ /app/src/

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Lightweight healthcheck — entrypoint writes /tmp/healthy after the
# scheduler binds. Without an HTTP listener we rely on a marker file.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD test -f /tmp/healthy || exit 1

CMD ["python", "-m", "src.main"]
