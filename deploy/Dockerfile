FROM python:3.12-slim-bookworm
ARG DEBIAN_MIRROR=https://deb.debian.org
ARG PYPI_INDEX=https://pypi.org/simple
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend MATHMODEL_DATA_DIR=/data MEDIA_MODEL_DIR=/models MATHMODEL_DEBUG=0
RUN case "$DEBIAN_MIRROR" in https://deb.debian.org|https://mirrors.cloud.tencent.com) ;; *) exit 1 ;; esac \
    && sed -i "s|http://deb.debian.org|${DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get -o APT::Update::Error-Mode=any -o Acquire::https::Timeout=20 update \
    && apt-get install -y --no-install-recommends ffmpeg libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements-linux.lock /app/backend/requirements-linux.lock
RUN case "$PYPI_INDEX" in https://pypi.org/simple|https://mirrors.cloud.tencent.com/pypi/simple) ;; *) exit 1 ;; esac \
    && pip install --require-hashes --no-cache-dir --index-url "$PYPI_INDEX" -r backend/requirements-linux.lock
RUN groupadd -g 10001 mathmodel && useradd -u 10001 -g mathmodel -M mathmodel && mkdir /data /models && chown mathmodel:mathmodel /data /models
COPY . /app
RUN MATHMODEL_DEBUG=1 DJANGO_SECRET_KEY=nonsecret-static-build-only MATHMODEL_DATA_DIR=/tmp/build-static python backend/manage.py collectstatic --noinput && rm -rf /tmp/build-static
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn","config.asgi:application","--host","0.0.0.0","--port","8000","--workers","2","--no-access-log","--no-proxy-headers","--ws-max-size","65536"]
