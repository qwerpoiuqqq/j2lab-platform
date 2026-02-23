#!/usr/bin/env bash
# =============================================================================
# J2LAB Platform - Database Initialization Script
# =============================================================================
# Usage:
#   # From host (Docker Compose must be running)
#   ./scripts/init-db.sh
#
#   # Or run inside api-server container
#   docker compose exec api-server bash /app/scripts/init-db.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "  J2LAB Platform - DB Initialization"
echo "=========================================="

# Check if running inside Docker or on host
if [ -f /.dockerenv ]; then
    echo "[INFO] Running inside Docker container"
    cd /app
else
    echo "[INFO] Running on host machine"
    cd "$PROJECT_DIR"
fi

# --- Step 1: Wait for PostgreSQL ---
echo ""
echo "[1/3] Waiting for PostgreSQL to be ready..."

if [ -f /.dockerenv ]; then
    # Inside container: use environment variables
    DB_HOST="${DB_HOST:-db}"
    DB_PORT="${DB_PORT:-5432}"
    DB_USER="${DB_USER:-j2lab}"
    DB_NAME="${DB_NAME:-j2lab_platform}"

    for i in $(seq 1 30); do
        if python -c "
import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect(host='${DB_HOST}', port=${DB_PORT}, user='${DB_USER}', database='${DB_NAME}', password='${DB_PASSWORD:-}')
    await conn.close()
asyncio.run(check())
" 2>/dev/null; then
            echo "[OK] PostgreSQL is ready"
            break
        fi
        echo "  Attempt $i/30 - waiting..."
        sleep 2
    done
else
    # On host: use docker compose
    echo "  Checking via docker compose..."
    docker compose exec -T db pg_isready -U "${DB_USER:-j2lab}" -d "${DB_NAME:-j2lab_platform}" || {
        echo "[ERROR] PostgreSQL is not ready. Make sure 'docker compose up db' is running."
        exit 1
    }
    echo "[OK] PostgreSQL is ready"
fi

# --- Step 2: Run Alembic Migrations ---
echo ""
echo "[2/3] Running Alembic migrations..."

if [ -f /.dockerenv ]; then
    cd /app
    alembic upgrade head
else
    docker compose exec -T api-server alembic upgrade head
fi

echo "[OK] Migrations applied successfully"

# --- Step 3: Seed initial data ---
echo ""
echo "[3/3] Seeding initial data..."

if [ -f /.dockerenv ]; then
    python -c "
import asyncio
from app.core.database import async_session_factory
from app.services.seed import seed_initial_data

async def main():
    async with async_session_factory() as session:
        await seed_initial_data(session)
        await session.commit()

asyncio.run(main())
" 2>/dev/null && echo "[OK] Seed data applied" || echo "[SKIP] Seed script not available or already seeded"
else
    bash "$SCRIPT_DIR/seed-data.sh"
fi

echo ""
echo "=========================================="
echo "  DB Initialization Complete!"
echo "=========================================="
echo ""
echo "  API Server: http://localhost:8000"
echo "  API Docs:   http://localhost:8000/docs"
echo "  Health:     http://localhost:8000/health"
echo ""
