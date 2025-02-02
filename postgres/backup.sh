#!/bin/bash

# Configuration
BACKUP_DIR="/backup"
POSTGRES_DB="rps_db"
POSTGRES_USER="rps_user"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${DATE}.sql"

# Create backup
pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} > ${BACKUP_FILE}

# Compress backup
gzip ${BACKUP_FILE}

# Keep only last 7 days of backups
find ${BACKUP_DIR} -name "backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: ${BACKUP_FILE}.gz"