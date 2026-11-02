FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UPTIME_CONFIG=/data/config.json

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin uptime \
    && mkdir /data && chown 10001:10001 /data

WORKDIR /app
COPY uptimewatch ./uptimewatch

VOLUME /data
EXPOSE 8080
USER uptime

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=4).status == 200 else 1)"]

CMD ["python", "-m", "uptimewatch", "serve", "--config", "/data/config.json"]
