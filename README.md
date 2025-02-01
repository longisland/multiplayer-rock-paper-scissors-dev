# Rock Paper Scissors Multiplayer Game

A multiplayer game where players can create and join matches to play Rock Paper Scissors against each other.

## Prerequisites

- Docker
- Docker Compose
- Git
- Python 3.12 or later

## Project Structure

```
.
├── app/                    # Main application package
│   ├── config/            # Configuration settings
│   ├── game/              # Game logic
│   ├── models/            # Database models
│   ├── routes/            # Route handlers
│   ├── static/            # Static files (CSS, JavaScript)
│   ├── templates/         # HTML templates
│   └── version.py         # Version tracking
├── init.sql/              # SQL initialization scripts
├── deploy.sh             # Deployment script
├── Dockerfile            # Docker configuration
├── docker-compose.yml    # Docker Compose configuration
├── init_db.py           # Database initialization script
└── requirements.txt     # Python dependencies
```

## Installation and Setup

1. Clone the repository:
```bash
git clone https://github.com/longisland/multiplayer-rock-paper-scissors-dev.git
cd multiplayer-rock-paper-scissors-dev
```

2. Create a persistent volume for the database:
```bash
docker volume create rps_game_data
```

3. Build and start the containers:
```bash
docker-compose up -d --build
```

The application will be available at http://localhost:5000

## Version Tracking

The application uses semantic versioning based on git tags. The version number is automatically generated from:

- The latest git tag (e.g., v1.2.3)
- Number of commits since the tag
- Current commit hash

For example:
- If you're on tag v1.2.3: version = "v1.2.3"
- If you're 2 commits after v1.2.3 with commit abc123: version = "v1.2.3.post2+abc123"

To create a new version:
```bash
# Create a new version tag
git tag -a v1.2.3 -m "Version 1.2.3"

# Push the tag
git push origin v1.2.3
```

Check the current version:
- Access `/api/version` endpoint to see:
  - Application version (auto-generated from git)
  - Build time
  - Git commit hash

This helps verify that deployments are successful and the correct version is running.

## Environment Variables

The following environment variables are configured in docker-compose.yml:

- `FLASK_APP` - Flask application entry point
- `FLASK_DEBUG` - Enable/disable debug mode
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Flask secret key
- `CORS_ALLOWED_ORIGINS` - CORS configuration
- `GIT_COMMIT` - Git commit hash for version tracking

## Database

The application uses PostgreSQL as its database. The database files are persisted in an external Docker volume named `rps_game_data`. This ensures that your data remains intact across container restarts and redeployments.

### Database Management

1. To view current volumes:
```bash
docker volume ls
```

2. To backup the database:
```bash
# Create a backup
docker exec rps-game-db-1 pg_dump -U postgres rps_game > backup.sql

# Restore from backup (if needed)
cat backup.sql | docker exec -i rps-game-db-1 psql -U postgres rps_game
```

## Deployment

### Development

1. Create a new branch:
```bash
git checkout -b feature-branch
```

2. Make your changes and test locally:
```bash
docker-compose up -d --build
```

3. Verify the version endpoint:
```bash
curl http://localhost:5000/api/version
```

### Production

1. Create the external volume:
```bash
docker volume create rps_game_data
```

2. Clone and deploy:
```bash
cd /var/www
git clone https://github.com/longisland/multiplayer-rock-paper-scissors-dev.git rps-game
cd rps-game
./deploy.sh
```

3. To update the production deployment:
```bash
cd /var/www/rps-game
git pull origin main
./deploy.sh
```

The deploy script will:
1. Stop existing containers
2. Remove old images
3. Build new images with version information
4. Start new containers
5. Verify that the correct version is running

## Troubleshooting

1. If the application is not responding:
```bash
# Check container status
docker ps

# View web application logs
docker logs rps-game-web-1

# View database logs
docker logs rps-game-db-1

# Check version information
curl http://localhost:5000/api/version
```

2. If you need to reset the database (WARNING: This will delete all data):
```bash
# Stop containers
docker-compose down

# Remove volume
docker volume rm rps_game_data

# Create new volume
docker volume create rps_game_data

# Restart containers
./deploy.sh
```

3. If you need to rebuild from scratch while preserving data:
```bash
# Stop containers
docker-compose down

# Remove all images
docker images | grep 'rps-game-web' | awk '{print $3}' | xargs -r docker rmi -f

# Rebuild and restart
./deploy.sh
```
