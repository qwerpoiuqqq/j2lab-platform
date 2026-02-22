FROM python:3.11-slim

# System dependencies for Playwright + curl_cffi
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    fonts-nanum \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

# Install Playwright Chromium
RUN playwright install chromium

# Copy source code
COPY src/ ./src/
COPY web/ ./web/
COPY data/ ./data/

# settings.json is volume-mounted at runtime
# COPY settings.json ./settings.json

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV SETTINGS_PATH=/app/settings.json

CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
