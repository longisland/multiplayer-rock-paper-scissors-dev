# Multiplayer Rock Paper Scissors - Development Version

This is the development version of the Multiplayer Rock Paper Scissors game. For the stable version, please check [multiplayer-rock-paper-scissors](https://github.com/longisland/multiplayer-rock-paper-scissors).

## Development Status

This repository contains the latest development version of the game. Features here may be unstable or incomplete. For production use, please use the stable version.

## Features in Development

- Enhanced session management
- Improved match handling
- Better error handling
- Real-time game state updates
- Performance optimizations
- Additional game statistics
- UI/UX improvements

## Requirements

- Python 3.8+
- Redis server
- Flask and Flask-SocketIO
- Eventlet

## Installation for Development

1. Clone the repository:
```bash
git clone https://github.com/longisland/multiplayer-rock-paper-scissors-dev.git
cd multiplayer-rock-paper-scissors-dev
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

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Testing

Before submitting a pull request, please ensure:
1. All existing tests pass
2. New tests are added for new features
3. Code follows the existing style
4. Documentation is updated

## License

MIT License