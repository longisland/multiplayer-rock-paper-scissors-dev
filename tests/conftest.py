import os
import pytest
from app import app as flask_app
from models import db, Player, Match

@pytest.fixture
def app():
    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'postgresql://postgres:postgres@localhost:5432/test_rps_game',
        'SECRET_KEY': 'test_key'
    })
    
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def runner(app):
    return app.test_cli_runner()

@pytest.fixture
def db_session(app):
    with app.app_context():
        yield db.session