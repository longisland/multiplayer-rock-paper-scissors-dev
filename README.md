# Rock Paper Scissors Multiplayer Game

A multiplayer game where players can create and join matches to play Rock Paper Scissors against each other.

## Prerequisites

- Docker
- Docker Compose
- Git

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

## Updating the Application

To update the application with the latest code from the repository while preserving the database data:

1. Pull the latest changes:
```bash
git pull origin main
```

2. Rebuild and restart the containers:
```bash
docker-compose down
docker-compose up -d --build
```

The database data will be preserved in the external volume `rps_game_data`.

## Project Structure

- `app.py` - Main application file
- `models.py` - Database models
- `config.py` - Configuration settings
- `init_db.py` - Database initialization script
- `init.sql/` - SQL initialization scripts
- `static/` - Static files (CSS, JavaScript)
- `templates/` - HTML templates
- `Dockerfile` - Docker configuration for the web application
- `docker-compose.yml` - Docker Compose configuration

## Environment Variables

The following environment variables are configured in docker-compose.yml:

- `FLASK_APP` - Flask application entry point
- `FLASK_DEBUG` - Enable/disable debug mode
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Flask secret key
- `CORS_ALLOWED_ORIGINS` - CORS configuration

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

## Troubleshooting

1. If the application is not responding:
```bash
# Check container status
docker ps

# View web application logs
docker logs rps-game-web-1

# View database logs
docker logs rps-game-db-1
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
docker-compose up -d --build
```

3. If you need to rebuild from scratch while preserving data:
```bash
# Stop containers
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## Production Deployment

For production deployment:

1. Create the external volume:
```bash
docker volume create rps_game_data
```

2. Clone and deploy:
```bash
cd /var/www
git clone https://github.com/longisland/multiplayer-rock-paper-scissors-dev.git rps-game
cd rps-game
docker-compose up -d --build
```

3. To update the production deployment:
```bash
cd /var/www/rps-game
git pull origin main
docker-compose down
docker-compose up -d --build
```
