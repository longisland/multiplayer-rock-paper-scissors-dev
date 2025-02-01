# Multiplayer Rock Paper Scissors - Stable Version

This is the stable version of the Multiplayer Rock Paper Scissors game. For development and latest features, please check the development repository at [multiplayer-rock-paper-scissors-dev](https://github.com/longisland/multiplayer-rock-paper-scissors-dev).

## Features

- Multiplayer gameplay with real-time updates
- Player registration and session management
- Match creation and joining
- Player statistics tracking
- Rematch functionality
- Persistent storage with Redis
- Automatic match cleanup on disconnection

## Requirements

- Python 3.8+
- Redis server
- Flask and Flask-SocketIO
- Eventlet

## Installation

1. Clone the repository:
```bash
git clone https://github.com/longisland/multiplayer-rock-paper-scissors.git
cd multiplayer-rock-paper-scissors
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Make sure Redis server is running:
```bash
systemctl start redis-server
```

4. Run the application:
```bash
python app.py
```

## Configuration

The application can be configured through environment variables:

- `REDIS_URL`: Redis server URL (default: redis://localhost:6379/0)
- `PORT`: Application port (default: 3001)

## Contributing

For contributions, please use the development repository at [multiplayer-rock-paper-scissors-dev](https://github.com/longisland/multiplayer-rock-paper-scissors-dev).

## License

MIT License