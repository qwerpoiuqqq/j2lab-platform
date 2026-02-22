# Quantum Campaign Automation

superap.io(퀀텀) 리워드 광고 캠페인 대량 등록 및 일일 키워드 자동 교체 시스템

## Tech Stack

- **Backend**: Python FastAPI
- **Frontend**: React + TypeScript + TailwindCSS
- **Database**: SQLite
- **Web Automation**: Playwright
- **Scheduler**: APScheduler
- **Container**: Docker + Docker Compose

## Quick Start

### Development (Local)

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# Access
# API: http://localhost:8000
# Docs: http://localhost:8000/docs
# Health: http://localhost:8000/health
```

### Production (Docker)

```bash
# Setup
cp .env.example .env
# Edit .env with your settings

# Run
docker-compose up -d

# Access
# API: http://localhost:8000
# Frontend: http://localhost:3000
```

## Project Structure

```
quantum-campaign-automation/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   ├── routers/
│   │   ├── services/
│   │   └── utils/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
├── data/
├── logs/
├── docs/
├── docker-compose.yml
└── .env.example
```

## API Endpoints

- `GET /health` - Health check
- `GET /docs` - Swagger UI documentation

## Development

### Run Tests

```bash
cd backend
pytest tests/ -v
```
