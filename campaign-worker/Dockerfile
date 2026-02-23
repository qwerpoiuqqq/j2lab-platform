# === campaign-worker Dockerfile ===
# Playwright-based campaign automation worker
# Uses Microsoft's official Playwright image with Chromium pre-installed

FROM mcr.microsoft.com/playwright/python:v1.49.1-noble

LABEL maintainer="J2LAB <dev@j2lab.com>"
LABEL description="J2LAB Campaign Automation Worker (Playwright + APScheduler)"

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only)
RUN playwright install chromium

# Copy application code
COPY . .

# Remove unnecessary files
RUN rm -rf tests/ .pytest_cache/ __pycache__/ .gitkeep

EXPOSE 8002

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8002/internal/health')" || exit 1

# Run with uvicorn (single worker for APScheduler singleton)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002", "--workers", "1"]
