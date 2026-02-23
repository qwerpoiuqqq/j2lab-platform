# === keyword-worker Dockerfile ===
# Playwright-based keyword extraction worker
# Uses Microsoft's official Playwright image with Chromium pre-installed

FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

LABEL maintainer="J2LAB <dev@j2lab.com>"
LABEL description="J2LAB Keyword Extraction Worker (Playwright)"

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only)
RUN playwright install chromium

# Copy application code
COPY . .

# Remove unnecessary files
RUN rm -rf tests/ .pytest_cache/ .venv/ __pycache__/ .gitkeep

EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/internal/health')" || exit 1

# Run with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
