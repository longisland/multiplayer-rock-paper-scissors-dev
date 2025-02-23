# Multiplayer Rock Paper Scissors - Development Version

This is the development version of the Multiplayer Rock Paper Scissors game. For the stable version, please check the main repository at [multiplayer-rock-paper-scissors](https://github.com/longisland/multiplayer-rock-paper-scissors).

## Features

- Multiplayer gameplay with real-time updates
- Player registration and session management
- Match creation and joining with betting system
- Enhanced betting animations and visual feedback
- Player statistics tracking with coin management
- Rematch functionality with stake preservation
- Persistent user data and game history with PostgreSQL
- Real-time game state with Redis
- Automatic match cleanup on disconnection
- Transaction support for game results and betting
- Explicit visual feedback for all game actions

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

2. Switch to the main branch:
```bash
git checkout main
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
cd src
python app.py
```

Note: The application uses relative imports and must be run from the src directory.

## Docker Deployment

1. Switch to the main branch:
```bash
git checkout main
```

2. Create required directories and set permissions:
```bash
mkdir -p postgres/backup
chmod 777 postgres/backup
```

3. Create external volumes for data persistence:
```bash
docker volume create --name=rps-game_postgres_data
docker volume create --name=rps-game_redis_data
```

4. Build and start the containers:
```bash
docker-compose up -d --build
```

5. View logs:
```bash
docker-compose logs -f
```

6. Stop the containers (preserves data in volumes):
```bash
docker-compose down
```

Note: 
- The Docker deployment uses external volumes to ensure data persistence across deployments
- The backup directory permissions are important for PostgreSQL archiving
- The application uses relative imports and sets the correct PYTHONPATH

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

3. Create required directories with proper permissions:
```bash
mkdir -p postgres/backup
chmod 777 postgres/backup
```

4. Install Certbot and obtain SSL certificate:
```bash
snap install --classic certbot
ln -s /snap/bin/certbot /usr/bin/certbot
certbot --nginx -d rockpaperscissors.fun --non-interactive --agree-tos --email openhands@all-hands.dev
```

5. Configure nginx:
```bash
cp nginx/rockpaperscissors.fun.conf /etc/nginx/sites-available/
ln -sf /etc/nginx/sites-available/rockpaperscissors.fun.conf /etc/nginx/sites-enabled/
nginx -t && systemctl restart nginx
```

Note: SSL certificate will be automatically renewed by Certbot's scheduled task.

6. Create external volumes for data persistence:
```bash
docker volume create --name=rps-game_postgres_data
docker volume create --name=rps-game_redis_data
```

7. Configure DNS:
- Add A record for rockpaperscissors.fun pointing to 165.227.160.131
- Add A record for www.rockpaperscissors.fun pointing to 165.227.160.131

8. Switch to main branch and pull the latest changes:
```bash
git checkout main
git pull origin main
```

9. Build and start the containers:
```bash
docker-compose up -d --build
```

Note: The application will be available at https://rockpaperscissors.fun

Note: 
- The backup directory permissions are important for PostgreSQL archiving
- External volumes ensure data persistence across deployments

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

4. Switch to main branch and pull the latest changes:
```bash
git checkout main
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

Note: 
- The `--force-recreate` flag ensures that the containers are recreated with the latest code
- External volumes preserve data even when containers are recreated
- Database backups provide additional data safety

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
- `PYTHONPATH`: Python path for imports (set to /app/src in Docker)
- `FLASK_APP`: Flask application module (set to src.app in Docker)

### Game Configuration
- `INITIAL_COINS`: Starting coins for new players (default: 100)
- `MATCH_TIMEOUT`: Time limit for each match in seconds (default: 30)
- `MIN_BET`: Minimum bet amount (default: 1)
- `MAX_BET`: Maximum bet amount (default: player's current coins)

## Testing

The project includes a comprehensive test suite covering game mechanics, mathematical models, and UI automation. Tests are written using pytest and Selenium, and can be run both locally and in Docker.

### Test Coverage

The test suite covers:

1. Game Mechanics
   - Match creation and joining
   - Move making and result calculation
   - Match timeout handling
   - Rematch functionality
   - Draw handling
   - Match cancellation
   - Auto-selection for timeouts

2. Mathematical Model
   - Betting distribution for wins
   - Betting distribution for draws
   - Betting limits
   - Consecutive matches betting
   - Rematch betting

3. UI Automation
   - Full game flow testing
   - Match creation and joining
   - Player moves and interactions
   - Rematch system
   - Visual feedback
   - Timer functionality

### Running Tests

#### Automated Test Suite
```bash
# Run all tests (unit tests and UI automation)
./run_tests.sh
```

#### Local Testing
```bash
# Install test dependencies
pip install -r requirements.txt

# Run unit tests with coverage
pytest tests/test_match_mechanics.py tests/test_game_service.py -v --cov=src

# Run UI automation tests (requires Chrome/ChromeDriver)
python tests/test_ui_automation.py
```

#### Docker Testing
```bash
# Build and run tests in Docker
docker-compose build
docker-compose run web ./run_tests.sh

# Run specific test file
docker-compose exec web pytest tests/test_match_mechanics.py -v

# Run UI tests in Docker
docker-compose exec web python tests/test_ui_automation.py
```

### Test Configuration

The test suite uses:
- SQLite in-memory database for unit tests
- Chrome in headless mode for UI tests
- Pytest fixtures for dependency injection
- Coverage reporting for code quality
- Parallel test execution support

Test configuration is managed through:
- `conftest.py`: Test fixtures and database setup
- `test_ui_automation.py`: Selenium test configuration
- `run_tests.sh`: Test execution orchestration

### Writing Tests

When adding new features or fixing bugs:
1. Add unit tests in `tests/` directory
2. Add UI tests if the feature has visual components
3. Use fixtures from `conftest.py`
4. Ensure all tests pass locally and in Docker
5. Maintain test coverage above 80%

Example test structure:
```python
def test_feature_name(match_service, db):
    # Setup
    creator_id = "player1"
    
    # Execute
    result = match_service.some_action(creator_id)
    
    # Assert
    assert result is not None
    assert result.some_property == expected_value
```

Example UI test:
```python
def test_ui_feature(driver):
    # Navigate and interact
    driver.get(app_url)
    element = driver.find_element(By.ID, 'feature-button')
    element.click()
    
    # Wait for response
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CLASS_NAME, 'result'))
    )
    
    # Verify
    assert element.text == 'Expected Result'
```

## Contributing

1. Create a new branch from the main branch:
```bash
git checkout main
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

4. Create a Pull Request on GitHub targeting the main branch.

Note: 
- All new features should be based on the main branch
- Ensure your changes maintain data persistence with external volumes
- Test your changes with both new and existing databases

## License

MIT License