# RPS-Web: Rock Paper Scissors Web App

A simple multiplayer Rock Paper Scissors web application with virtual coins.

## Features

- Anonymous multiplayer gameplay
- Virtual coin system (100 coins on start)
- Create and join matches with custom stakes
- Mobile-friendly interface
- Real-time updates using WebSocket

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser and visit: `http://localhost:5000`

## How to Play

1. When you first visit the site, you'll get 100 virtual coins
2. Create a match by setting a stake amount
3. Other players can join your match
4. Choose Rock, Paper, or Scissors when the game starts
5. Winner gets the stake from the loser
6. In case of a draw, both players keep their coins

## Technical Details

- Backend: Flask + Flask-SocketIO
- Frontend: HTML5, CSS3, Vanilla JavaScript
- Storage: In-memory (no database required)
- WebSocket for real-time updates