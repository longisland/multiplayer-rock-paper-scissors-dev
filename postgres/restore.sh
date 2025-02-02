#!/bin/bash
set -e

# Get the latest backup file
LATEST_BACKUP=$(ls -t /backup/backup_*.sql.gz | head -n1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "No backup file found"
    exit 1
fi

echo "Restoring from backup: ${LATEST_BACKUP}"

# Decompress backup
gunzip -c "${LATEST_BACKUP}" | psql -U rps_user -d rps_db

echo "Restore completed successfully"