import pytest
from flask import Flask
from src.models.database import db as _db
from src.services.match_service import MatchService
from src.config import Config

@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'test_key'
    app.config['INITIAL_COINS'] = Config.INITIAL_COINS
    app.config['MATCH_TIMEOUT'] = Config.MATCH_TIMEOUT
    _db.init_app(app)
    return app

@pytest.fixture
def db(app):
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()

@pytest.fixture
def match_service(db):
    service = MatchService()
    # Initialize players with initial coins
    service.get_player("player1")
    service.get_player("player2")
    return service

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def session(db):
    connection = db.engine.connect()
    transaction = connection.begin()
    session = db.create_scoped_session()
    yield session
    session.close()
    transaction.rollback()
    connection.close()