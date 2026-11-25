#!/bin/bash
set -e
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/var/backups/dating
mkdir -p "$BACKUP_DIR"
PGPASSWORD="DatingSecure_2026_x9Qv7!" pg_dump -U dating_user -h localhost dating_db | gzip > "$BACKUP_DIR/dating_db_$TIMESTAMP.gz"
find "$BACKUP_DIR" -name "*.gz" -mtime +7 -delete
echo "Backup completed: dating_db_$TIMESTAMP.gz"
