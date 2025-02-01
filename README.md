# Multiplayer Rock Paper Scissors - Development Version

This is the development version of the Multiplayer Rock Paper Scissors game. For the stable version, please check the main repository at [multiplayer-rock-paper-scissors](https://github.com/longisland/multiplayer-rock-paper-scissors).

## Features

- Multiplayer gameplay with real-time updates
- Player registration and session management
- Match creation and joining
- Player statistics tracking
- Rematch functionality
- Persistent storage with Redis
- Automatic match cleanup on disconnection

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
- Redis server
- Docker and Docker Compose (for containerized deployment)
- Flask and Flask-SocketIO
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

1. SSH into the server:
```bash
sshpass -p "TMPpass99" ssh root@165.227.160.131
```

2. Navigate to the project directory:
```bash
cd /var/www/rps-game
```

3. Pull the latest changes:
```bash
git pull origin feature/project-restructure
```

4. Rebuild and restart the containers:
```bash
docker-compose down
docker-compose up -d --build --force-recreate
```

Note: The `--force-recreate` flag ensures that the containers are recreated with the latest code, avoiding any caching issues.

## Configuration

The application can be configured through environment variables:

- `REDIS_URL`: Redis server URL (default: redis://localhost:6379/0)
- `PORT`: Application port (default: 5000)
- `HOST`: Host to bind to (default: 0.0.0.0)
- `DEBUG`: Enable debug mode (default: True)
- `SECRET_KEY`: Flask secret key (auto-generated if not provided)

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