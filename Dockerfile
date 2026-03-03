FROM node:22-alpine AS frontend

WORKDIR /build/web_client
COPY web_client/package.json ./
RUN npm install
COPY web_client/ ./
RUN npm run build

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    fonts-liberation \
    fonts-noto-color-emoji \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libnspr4 \
    libnss3 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /opt/openbotx
COPY . .
COPY --from=frontend /build/openbotx/web_client/ ./openbotx/web_client/
RUN uv pip install --system .

WORKDIR /app
RUN openbotx init

EXPOSE 8000

CMD ["sh", "-c", "openbotx start --no-browser --port ${PORT:-8000}"]
