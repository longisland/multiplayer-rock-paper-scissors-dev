import pytest
from src.app import app
from src.models.database import db as _db
from src.services.match_service import MatchService

@pytest.fixture
def app():
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
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
    return MatchService()

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