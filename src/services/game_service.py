import random
from ..models.database import db, User, GameHistory
from datetime import datetime

class GameService:
    @staticmethod
    def calculate_winner(move1, move2):
        if move1 == move2:
            return 'draw'
        if (
            (move1 == 'rock' and move2 == 'scissors') or
            (move1 == 'paper' and move2 == 'rock') or
            (move1 == 'scissors' and move2 == 'paper')
        ):
            return 'player1'
        return 'player2'

    @staticmethod
    def random_move():
        return random.choice(['rock', 'paper', 'scissors'])

    @staticmethod
    def calculate_match_result(match, players):
        from ..utils.logger import setup_logger
        logger = setup_logger()

        creator_move = match.moves[match.creator]
        joiner_move = match.moves[match.joiner]
        result = GameService.calculate_winner(creator_move, joiner_move)

        # Get users from database
        creator_user = User.query.filter_by(username=match.creator).first()
        joiner_user = User.query.filter_by(username=match.joiner).first()

        # Log initial state
        logger.info(f"Before result - Creator coins: {creator_user.coins}, Joiner coins: {joiner_user.coins}, Stake: {match.stake}")
        
        # Create game history record
        game_history = GameHistory(
            player1_id=creator_user.id,
            player2_id=joiner_user.id,
            player1_choice=creator_move,
            player2_choice=joiner_move,
            bet_amount=match.stake
        )
        
        if result == 'draw':
            # In case of draw, return stakes to both players
            logger.info("Match result: Draw")
            match.stats.draws += 1
            players[match.creator].record_draw()
            players[match.joiner].record_draw()
            
            # Return stakes
            creator_user.coins += match.stake
            joiner_user.coins += match.stake
            
            # Update stats
            creator_user.draws += 1
            creator_user.total_games += 1
            joiner_user.draws += 1
            joiner_user.total_games += 1

        elif result == 'player1':
            # Creator wins
            logger.info("Match result: Creator wins")
            match.stats.creator_wins += 1
            players[match.creator].record_win()
            players[match.joiner].record_loss()
            
            # Winner gets both stakes
            creator_user.coins += (match.stake * 2)
            creator_user.total_coins_won += match.stake
            joiner_user.total_coins_lost += match.stake
            
            # Update stats
            creator_user.wins += 1
            creator_user.total_games += 1
            joiner_user.losses += 1
            joiner_user.total_games += 1
            
            game_history.winner_id = creator_user.id

        else:
            # Joiner wins
            logger.info("Match result: Joiner wins")
            match.stats.joiner_wins += 1
            players[match.joiner].record_win()
            players[match.creator].record_loss()
            
            # Winner gets both stakes
            joiner_user.coins += (match.stake * 2)
            joiner_user.total_coins_won += match.stake
            creator_user.total_coins_lost += match.stake
            
            # Update stats
            joiner_user.wins += 1
            joiner_user.total_games += 1
            creator_user.losses += 1
            creator_user.total_games += 1
            
            game_history.winner_id = joiner_user.id

        # Sync in-memory state
        players[match.creator].coins = creator_user.coins
        players[match.joiner].coins = joiner_user.coins

        # Log final state
        logger.info(f"After result - Creator coins: {creator_user.coins}, Joiner coins: {joiner_user.coins}")
            
        # Prepare result data
        result_data = {
            'winner': result,
            'creator_move': creator_move,
            'joiner_move': joiner_move,
            'match_stats': match.stats.to_dict(),
            'creator_stats': players[match.creator].stats.to_dict(),
            'joiner_stats': players[match.joiner].stats.to_dict(),
            'stake': match.stake,
            'can_rematch': (players[match.creator].has_enough_coins(match.stake) and 
                          players[match.joiner].has_enough_coins(match.stake))
        }

        # Only save if this is the first time processing the result
        if match.set_result(result_data):
            # Save changes to database
            db.session.add(game_history)
            db.session.commit()
            logger.info("Match result saved to database")
        else:
            logger.info("Match result already processed, skipping database update")

        return result_data