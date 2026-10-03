FROM ghcr.io/home-assistant/base-python:3.12-alpine3.24

ARG BUILD_VERSION=0.1.22
ARG BUILD_ARCH=amd64

LABEL \
  org.opencontainers.image.source="https://github.com/ktgregson93-collab/Getfit" \
  org.opencontainers.image.description="Getfit Home Workout Assistant for Home Assistant" \
  io.hass.version="${BUILD_VERSION}" \
  io.hass.type="app" \
  io.hass.arch="${BUILD_ARCH}"

WORKDIR /app

COPY pyproject.toml README.md alembic.ini /app/
COPY migrations /app/migrations
COPY src /app/src
COPY programme_seed /app/programme_seed

RUN pip install --no-cache-dir /app

COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]
