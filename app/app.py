from flask import Flask, jsonify
from flask_socketio import SocketIO
import logging
from .models.models import db
from .config.config import Config
from .routes.routes import init_routes
from .version import get_version_info

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__, static_url_path='/static')
    app.config.from_object(Config)

    # Initialize database
    db.init_app(app)

    # Create tables
    with app.app_context():
        db.create_all()

    # Configure Flask-SocketIO
    socketio = SocketIO(
        app,
        async_mode='gevent',  # Use gevent for WebSocket support
        cors_allowed_origins='*',  # Allow all origins in development
        logger=True,
        engineio_logger=True,
        ping_timeout=60,
        ping_interval=25,
        max_http_buffer_size=1000000,
        manage_session=False  # Let Flask manage the sessions
    )

    # Initialize routes
    init_routes(app, socketio)

    # Add version endpoint
    @app.route('/api/version')
    def version():
        return jsonify(get_version_info())

    return app, socketio

app, socketio = create_app()

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)