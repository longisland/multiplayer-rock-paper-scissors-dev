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

2. Build and start the containers:
```bash
docker-compose up -d --build
```

The application will be available at http://localhost:5000

## Updating the Application

To update the application with the latest code from the repository:

1. Pull the latest changes:
```bash
git pull origin main
```

2. Rebuild and restart the containers:
```bash
docker-compose down
docker-compose up -d --build
```

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

The application uses PostgreSQL as its database. The database is automatically initialized when the containers start up. The database files are persisted in a Docker volume named `postgres_data`.

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

2. To reset the database:
```bash
# Stop containers
docker-compose down

# Remove volume
docker volume rm rps-game_postgres_data

# Restart containers
docker-compose up -d --build
```

3. If you need to rebuild from scratch:
```bash
# Stop and remove everything
docker-compose down -v
docker-compose up -d --build
```
