from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

db = SQLAlchemy()
socketio = SocketIO()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:postgres@db/rps_game'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Enable CORS for all routes and WebSocket
    CORS(app, resources={r"/*": {"origins": "*"}})

    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")

    from .routes.match import match_bp, register_socket_events
    app.register_blueprint(match_bp)
    register_socket_events(socketio)

    from .game.game_logic import socketio as game_socketio
    game_socketio.init_app(app, cors_allowed_origins="*")

    return app
