FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
        gdal-bin libgdal-dev libgeos-dev libproj-dev binutils curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tailwind standalone CLI (no Node needed)
ARG TARGETARCH
RUN ARCH=$([ "$TARGETARCH" = "arm64" ] && echo arm64 || echo x64) && \
    curl -sSLo /usr/local/bin/tailwindcss \
      https://github.com/tailwindlabs/tailwindcss/releases/download/v3.4.17/tailwindcss-linux-${ARCH} && \
    chmod +x /usr/local/bin/tailwindcss

COPY . .
RUN tailwindcss -i static/src/input.css -o static/css/app.css --minify

EXPOSE 8000
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "alcove.asgi:application"]
