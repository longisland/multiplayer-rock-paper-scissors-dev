# Multiplayer Rock Paper Scissors - Development Version

This is the development version of the Multiplayer Rock Paper Scissors game. For the stable version, please check the main repository at [multiplayer-rock-paper-scissors](https://github.com/longisland/multiplayer-rock-paper-scissors).

## Features

- Multiplayer gameplay with real-time updates
- Player registration and session management
- Match creation and joining
- Player statistics tracking
- Rematch functionality
- Persistent user data and game history with PostgreSQL
- Real-time game state with Redis
- Automatic match cleanup on disconnection
- Transaction support for game results

## Project Structure

```
.
├── Dockerfile
├── docker-compose.yml
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── app.py              # Main application entry point
│   ├── config.py           # Configuration settings
│   ├── models/             # Data models
│   ├── services/           # Business logic
│   ├── static/             # Static files (CSS, JS)
│   ├── templates/          # HTML templates
│   └── utils/              # Utility functions
└── tests/                  # Test files
```

## Requirements

- Python 3.8+
- PostgreSQL 15+ (for persistent storage)
- Redis server (for real-time features)
- Docker and Docker Compose (for containerized deployment)
- Flask and Flask-SocketIO
- SQLAlchemy and Flask-SQLAlchemy
- Eventlet

## Local Development

1. Clone the repository:
```bash
git clone https://github.com/longisland/multiplayer-rock-paper-scissors-dev.git
cd multiplayer-rock-paper-scissors-dev
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python -m src.app
```

## Docker Deployment

1. Build and start the containers:
```bash
docker-compose up -d --build
```

2. View logs:
```bash
docker-compose logs -f
```

3. Stop the containers:
```bash
docker-compose down
```

## Server Deployment

### Initial Deployment

1. SSH into the server:
```bash
sshpass -p "TMPpass99" ssh root@165.227.160.131
```

2. Navigate to the project directory:
```bash
cd /var/www/rps-game
```

3. Create required directories:
```bash
mkdir -p postgres/backup
```

4. Pull the latest changes:
```bash
git pull origin main
```

5. Build and start the containers:
```bash
docker-compose up -d --build
```

### Redeployment with Data Preservation

1. SSH into the server:
```bash
sshpass -p "TMPpass99" ssh root@165.227.160.131
```

2. Navigate to the project directory:
```bash
cd /var/www/rps-game
```

3. Create a backup of the current database:
```bash
docker-compose exec postgres pg_dump -U rps_user rps_db > postgres/backup/pre_deploy_backup.sql
```

4. Pull the latest changes:
```bash
git pull origin main
```

5. Rebuild and restart the containers:
```bash
docker-compose down
docker-compose up -d --build --force-recreate
```

6. Wait for PostgreSQL to be ready (about 30 seconds), then restore data if needed:
```bash
docker-compose exec postgres psql -U rps_user -d rps_db < postgres/backup/pre_deploy_backup.sql
```

Note: The `--force-recreate` flag ensures that the containers are recreated with the latest code, avoiding any caching issues.

### Data Persistence

The application uses Docker volumes to persist data across deployments:

- `postgres_data`: Stores PostgreSQL database files
- `redis_data`: Stores Redis data
- `postgres/backup`: Stores database backups

Automatic backups are configured through:
- PostgreSQL archiving (continuous)
- Backup script (daily)
- Pre-deployment backups

To manually create a backup:
```bash
docker-compose exec postgres /backup/backup.sh
```

To restore from the latest backup:
```bash
docker-compose exec postgres /backup/restore.sh
```

## Configuration

The application can be configured through environment variables:

### Database Configuration
- `DATABASE_URL`: PostgreSQL database URL (default: postgresql://rps_user:rps_password@localhost:5432/rps_db)
- `SQLALCHEMY_DATABASE_URI`: Same as DATABASE_URL, used by Flask-SQLAlchemy
- `POSTGRES_USER`: PostgreSQL user (default: rps_user)
- `POSTGRES_PASSWORD`: PostgreSQL password (default: rps_password)
- `POSTGRES_DB`: PostgreSQL database name (default: rps_db)

### Redis Configuration
- `REDIS_URL`: Redis server URL (default: redis://localhost:6379/0)

### Application Configuration
- `PORT`: Application port (default: 5000)
- `HOST`: Host to bind to (default: 0.0.0.0)
- `DEBUG`: Enable debug mode (default: True)
- `SECRET_KEY`: Flask secret key (auto-generated if not provided)
- `SQLALCHEMY_TRACK_MODIFICATIONS`: SQLAlchemy event system (default: False)

## Contributing

1. Create a new branch for your feature:
```bash
git checkout -b feature/your-feature-name
```

2. Make your changes and commit them:
```bash
git add .
git commit -m "Description of changes"
```

3. Push to your branch:
```bash
git push origin feature/your-feature-name
```

4. Create a Pull Request on GitHub.

## License

MIT License