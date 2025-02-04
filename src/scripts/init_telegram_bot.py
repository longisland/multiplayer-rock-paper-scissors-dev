import telebot
from src.config import Config

def init_telegram_bot():
    bot = telebot.TeleBot(Config.BOT_TOKEN)

    # Set up bot commands
    try:
        bot.set_my_commands([
            telebot.types.BotCommand("start", "Start playing Rock Paper Scissors"),
            telebot.types.BotCommand("help", "Show help information"),
            telebot.types.BotCommand("stats", "View your game statistics")
        ])
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 429:  # Too Many Requests
            import time
            time.sleep(e.result_json['parameters']['retry_after'])
            bot.set_my_commands([
                telebot.types.BotCommand("start", "Start playing Rock Paper Scissors"),
                telebot.types.BotCommand("help", "Show help information"),
                telebot.types.BotCommand("stats", "View your game statistics")
            ])

    # Set up webhook
    webhook_url = f"{Config.BASE_URL}/telegram/webhook"
    try:
        bot.delete_webhook()
        bot.set_webhook(url=webhook_url)
    except telebot.apihelper.ApiTelegramException as e:
        if e.error_code == 429:  # Too Many Requests
            import time
            time.sleep(e.result_json['parameters']['retry_after'])
            bot.delete_webhook()
            bot.set_webhook(url=webhook_url)

    # Set up bot handlers
    @bot.message_handler(commands=['start'])
    def start(message):
        web_app_url = f"{Config.BASE_URL}/"
        keyboard = telebot.types.InlineKeyboardMarkup()
        keyboard.add(telebot.types.InlineKeyboardButton(
            text="Play Rock Paper Scissors",
            web_app=telebot.types.WebAppInfo(url=web_app_url)
        ))
        bot.reply_to(message, 
                    "Welcome to Rock Paper Scissors! Click the button below to start playing:",
                    reply_markup=keyboard)

    @bot.message_handler(commands=['help'])
    def help(message):
        help_text = """
🎮 Rock Paper Scissors Game Help

How to play:
1. Click the "Play" button to open the game
2. Create a new match or join an existing one
3. Choose your stake amount
4. Make your move: Rock, Paper, or Scissors
5. Wait for your opponent's move
6. See the result and collect your winnings!

Commands:
/start - Start playing
/help - Show this help message
/stats - View your game statistics

Need more help? Visit our website: https://rockpaperscissors.fun
"""
        bot.reply_to(message, help_text)

    @bot.message_handler(commands=['stats'])
    def stats(message):
        # Get user stats from database
        from src.models.database import User
        user = User.query.filter_by(telegram_id=message.from_user.id).first()
        if user:
            stats_text = f"""
🏆 Your Game Statistics:

Total Games: {user.total_games}
Wins: {user.wins}
Losses: {user.losses}
Draws: {user.draws}

💰 Coins: {user.coins}
Total Won: {user.total_coins_won}
Total Lost: {user.total_coins_lost}
"""
        else:
            stats_text = "You haven't played any games yet. Start playing to see your stats!"
        
        bot.reply_to(message, stats_text)

    return bot

if __name__ == '__main__':
    init_telegram_bot()