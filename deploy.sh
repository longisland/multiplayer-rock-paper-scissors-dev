#!/bin/bash

# Exit on error
set -e

# Deploy to remote server
echo "Deploying to remote server..."

# Copy files to server
sshpass -p "TMPpass99" scp -o StrictHostKeyChecking=no -r \
    app.py \
    config.py \
    models.py \
    requirements.txt \
    docker-compose.yml \
    Dockerfile \
    init_db.py \
    static \
    templates \
    root@165.227.160.131:/opt/rps-game/

# Connect to server and set up the application
sshpass -p "TMPpass99" ssh -o StrictHostKeyChecking=no root@165.227.160.131 << 'ENDSSH'
    cd /opt/rps-game

    # Install Docker if not installed
    if ! command -v docker &> /dev/null; then
        curl -fsSL https://get.docker.com -o get-docker.sh
        sh get-docker.sh
    fi

    # Install Docker Compose if not installed
    if ! command -v docker-compose &> /dev/null; then
        curl -L "https://github.com/docker/compose/releases/download/v2.23.3/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
    fi

    # Stop and remove existing containers
    docker-compose down || true

    # Build and start containers
    docker-compose up -d --build

    echo "Deployment completed successfully!"
ENDSSH