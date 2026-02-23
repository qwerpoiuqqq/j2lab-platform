#!/usr/bin/env bash
# =============================================================================
# J2LAB Platform - PostgreSQL Backup Script
# =============================================================================
# Creates a compressed backup of the PostgreSQL database.
#
# Usage:
#   ./scripts/backup-db.sh                    # Manual backup
#   # Add to crontab for daily backups:
#   # 0 3 * * * /path/to/j2lab-platform/scripts/backup-db.sh
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Configuration
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_DIR/backups}"
KEEP_DAYS="${KEEP_DAYS:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Load environment variables
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

DB_NAME="${DB_NAME:-j2lab_platform}"
DB_USER="${DB_USER:-j2lab}"
BACKUP_FILE="$BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz"

echo "=========================================="
echo "  J2LAB Platform - Database Backup"
echo "=========================================="
echo ""
echo "  Database: $DB_NAME"
echo "  Backup:   $BACKUP_FILE"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Run pg_dump inside the postgres container
echo "[1/3] Creating backup..."
docker compose exec -T db pg_dump -U "$DB_USER" -d "$DB_NAME" --clean --if-exists | gzip > "$BACKUP_FILE"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "[OK] Backup created: $BACKUP_FILE ($BACKUP_SIZE)"
else
    echo "[ERROR] Backup failed!"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# Clean up old backups
echo ""
echo "[2/3] Cleaning up backups older than $KEEP_DAYS days..."
DELETED=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql.gz" -mtime +$KEEP_DAYS -delete -print | wc -l | tr -d ' ')
echo "[OK] Deleted $DELETED old backup(s)"

# List remaining backups
echo ""
echo "[3/3] Current backups:"
ls -lh "$BACKUP_DIR"/${DB_NAME}_*.sql.gz 2>/dev/null || echo "  (none)"

echo ""
echo "=========================================="
echo "  Backup Complete!"
echo "=========================================="
echo ""
echo "  Restore with:"
echo "    gunzip -c $BACKUP_FILE | docker compose exec -T db psql -U $DB_USER -d $DB_NAME"
echo ""
