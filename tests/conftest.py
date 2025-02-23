import pytest
from src.app import app, db, socketio
from src.services.match_service import MatchService
from src.services.game_service import GameService

@pytest.fixture
def test_app():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SECRET_KEY'] = 'test_key'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

@pytest.fixture
def socket_client(test_app):
    return socketio.test_client(app)

@pytest.fixture
def match_service():
    return MatchService()

@pytest.fixture
def game_service():
    return GameService()

@pytest.fixture
def db_session():
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.remove()
        db.drop_all()