import telebot
import hmac
import hashlib
import json
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from src.config import Config

class TelegramService:
    def __init__(self, bot_token: str):
        self.bot = telebot.TeleBot(bot_token)
        self.bot.set_webhook(url=f"{Config.BASE_URL}/telegram/webhook")

    def verify_web_app_data(self, init_data: str) -> Optional[Dict[str, Any]]:
        """
        Verify Telegram Web App init data
        Returns user data if verification is successful, None otherwise
        """
        try:
            parsed_data = dict(param.split('=') for param in init_data.split('&'))
            
            # Extract hash and data to check
            received_hash = parsed_data.pop('hash')
            data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
            
            # Calculate secret key
            secret_key = hmac.new(
                "WebAppData".encode(),
                Config.BOT_TOKEN.encode(),
                hashlib.sha256
            ).digest()
            
            # Calculate hash
            calculated_hash = hmac.new(
                secret_key,
                data_check_string.encode(),
                hashlib.sha256
            ).hexdigest()
            
            # Verify hash
            if calculated_hash != received_hash:
                return None
            
            # Parse user data
            user = json.loads(parsed_data.get('user', '{}'))
            return {
                'id': user.get('id'),
                'username': user.get('username'),
                'first_name': user.get('first_name'),
                'last_name': user.get('last_name')
            }
        except Exception:
            return None

    def send_game_invite(self, user_id: int, match_id: str, stake: int):
        """Send game invitation to a user"""
        message = f"You've been invited to a game!\nStake: {stake} coins\nClick to join: {Config.BASE_URL}?match={match_id}"
        self.bot.send_message(user_id, message)

    def send_game_result(self, user_id: int, result: str, coins_change: int):
        """Send game result to a user"""
        emoji = "🎉" if coins_change > 0 else "😔" if coins_change < 0 else "🤝"
        message = f"{emoji} Game Result: {result}\nCoins change: {coins_change:+}"
        self.bot.send_message(user_id, message)

    def handle_webhook(self, request_data: Dict[str, Any]):
        """Handle Telegram webhook updates"""
        update = telebot.types.Update.de_json(request_data)
        self.bot.process_new_updates([update])