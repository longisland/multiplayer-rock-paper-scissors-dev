import os
import secrets

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(16))
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 443))
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://rps_user:rps_password@localhost:5432/rps_db')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    INITIAL_COINS = 100
    MATCH_TIMEOUT = 30.0  # seconds
    SSL_CERT = os.getenv('SSL_CERT')
    SSL_KEY = os.getenv('SSL_KEY')

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = False