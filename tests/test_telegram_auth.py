import pytest
from src.app import app
from src.models.database import db, User
from src.services.telegram_service import TelegramService
from datetime import datetime

@pytest.fixture
def mock_telegram_data():
    return {
        'id': 123456789,
        'username': 'test_user',
        'first_name': 'Test',
        'last_name': 'User'
    }

def test_telegram_auth_new_user(client, mock_telegram_data):
    # Mock TelegramService.verify_web_app_data to return test data
    def mock_verify(init_data):
        return mock_telegram_data
    TelegramService.verify_web_app_data = mock_verify

    # Test authentication with new user
    response = client.get('/?tgWebAppData=mock_data')
    assert response.status_code == 200

    # Check if user was created
    user = User.query.filter_by(telegram_id=mock_telegram_data['id']).first()
    assert user is not None
    assert user.username == mock_telegram_data['username']
    assert user.telegram_first_name == mock_telegram_data['first_name']
    assert user.telegram_last_name == mock_telegram_data['last_name']

def test_telegram_auth_existing_user(client, mock_telegram_data):
    # Create existing user
    user = User(
        username=mock_telegram_data['username'],
        telegram_id=mock_telegram_data['id'],
        telegram_username=mock_telegram_data['username'],
        telegram_first_name=mock_telegram_data['first_name'],
        telegram_last_name=mock_telegram_data['last_name'],
        telegram_auth_date=datetime.utcnow()
    )
    db.session.add(user)
    db.session.commit()

    # Mock TelegramService.verify_web_app_data
    def mock_verify(init_data):
        return mock_telegram_data
    TelegramService.verify_web_app_data = mock_verify

    # Test authentication with existing user
    response = client.get('/?tgWebAppData=mock_data')
    assert response.status_code == 200

    # Check that no new user was created
    users = User.query.filter_by(telegram_id=mock_telegram_data['id']).all()
    assert len(users) == 1

def test_telegram_auth_invalid_data(client):
    # Mock TelegramService.verify_web_app_data to return None (invalid data)
    def mock_verify(init_data):
        return None
    TelegramService.verify_web_app_data = mock_verify

    # Test authentication with invalid data
    response = client.get('/?tgWebAppData=invalid_data')
    assert response.status_code == 400
    assert b'Invalid Telegram authentication' in response.data

def test_telegram_webhook(client, mock_telegram_data):
    # Test webhook with valid token
    response = client.post('/telegram/webhook',
                          headers={'X-Telegram-Bot-Api-Secret-Token': app.config['BOT_TOKEN']},
                          json={'update_id': 1})
    assert response.status_code == 200

    # Test webhook with invalid token
    response = client.post('/telegram/webhook',
                          headers={'X-Telegram-Bot-Api-Secret-Token': 'invalid_token'},
                          json={'update_id': 1})
    assert response.status_code == 401