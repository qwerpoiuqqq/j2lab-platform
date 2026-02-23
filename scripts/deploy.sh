#!/usr/bin/env bash
# =============================================================================
# J2LAB Platform - Production Deployment Script
# =============================================================================
# Usage:
#   ./scripts/deploy.sh          # Full deploy (build + up + migrate)
#   ./scripts/deploy.sh update   # Update only (pull + rebuild + restart)
#   ./scripts/deploy.sh status   # Show service status
#   ./scripts/deploy.sh logs     # Tail all logs
#   ./scripts/deploy.sh stop     # Stop all services
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

ACTION="${1:-deploy}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_env() {
    if [ ! -f .env ]; then
        log_error ".env file not found! Copy from .env.example:"
        echo "  cp .env.example .env"
        echo "  nano .env  # Fill in actual values"
        exit 1
    fi
    log_info ".env file found"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    log_info "Docker is available"
}

case "$ACTION" in
    deploy)
        echo "=========================================="
        echo "  J2LAB Platform - Full Deployment"
        echo "=========================================="
        echo ""

        check_docker
        check_env

        log_info "Building images..."
        docker compose build

        log_info "Starting services..."
        docker compose up -d

        log_info "Waiting for services to be healthy..."
        sleep 10

        log_info "Running database migrations..."
        docker compose exec -T api-server alembic upgrade head

        log_info "Seeding initial data..."
        bash "$SCRIPT_DIR/seed-data.sh" || true

        echo ""
        log_info "Deployment complete!"
        echo ""
        docker compose ps
        echo ""
        echo "  Application: http://localhost"
        echo "  API Docs:    http://localhost/docs"
        echo "  Health:      http://localhost/health"
        echo ""
        ;;

    update)
        echo "=========================================="
        echo "  J2LAB Platform - Update Deployment"
        echo "=========================================="
        echo ""

        check_docker
        check_env

        log_info "Pulling latest code..."
        git pull

        log_info "Rebuilding images..."
        docker compose build

        log_info "Restarting services..."
        docker compose up -d

        log_info "Waiting for services to be healthy..."
        sleep 10

        log_info "Running database migrations..."
        docker compose exec -T api-server alembic upgrade head

        echo ""
        log_info "Update complete!"
        docker compose ps
        ;;

    status)
        echo "=========================================="
        echo "  J2LAB Platform - Service Status"
        echo "=========================================="
        echo ""
        docker compose ps
        echo ""
        echo "--- Health Checks ---"
        curl -s http://localhost/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "API server not responding"
        ;;

    logs)
        docker compose logs -f --tail=100
        ;;

    stop)
        echo "Stopping all services..."
        docker compose down
        log_info "All services stopped"
        ;;

    *)
        echo "Usage: $0 {deploy|update|status|logs|stop}"
        exit 1
        ;;
esac
