FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 설치 (Playwright용)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright 브라우저 설치
RUN playwright install chromium
RUN playwright install-deps

# 데이터 디렉토리 생성
RUN mkdir -p /app/data /app/logs

# 애플리케이션 코드 복사
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
