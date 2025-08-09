# syntax=docker/dockerfile:1.6
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VERSION=1.7.1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates tini git && \
    rm -rf /var/lib/apt/lists/*

# Install supercronic
ENV SUPERCRONIC_VERSION=v0.2.29
RUN curl -fsSLo /usr/local/bin/supercronic \
    https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64 && \
    chmod +x /usr/local/bin/supercronic

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir poetry==${POETRY_VERSION} && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main --no-root

COPY . /app
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["tini","--"]
CMD ["/app/entrypoint.sh"]
