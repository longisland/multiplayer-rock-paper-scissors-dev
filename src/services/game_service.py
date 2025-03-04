import random
from src.models.database import db, User, GameHistory
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
    def handle_timeout(match, players):
        """Handle match timeout by making random moves for players who haven't moved"""
        import random
        
        # Make random moves for players who haven't moved
        if match.creator not in match.moves or match.moves[match.creator] is None:
            match.moves[match.creator] = random.choice(['rock', 'paper', 'scissors'])
        
        if match.joiner not in match.moves or match.moves[match.joiner] is None:
            match.moves[match.joiner] = random.choice(['rock', 'paper', 'scissors'])
        
        # Calculate and return the result
        return GameService.calculate_match_result(match, players)

    @staticmethod
    def calculate_match_result(match, players):
        from ..utils.logger import setup_logger
        logger = setup_logger()

        # Check if result was already processed
        if match.result is not None:
            logger.info("Match result already processed, returning existing result")
            return match.result

        creator_move = match.moves[match.creator]
        joiner_move = match.moves[match.joiner]
        result = GameService.calculate_winner(creator_move, joiner_move)

        try:
            # Start transaction
            db.session.begin_nested()

            # Get users from database with row locking
            creator_user = User.query.filter_by(session_id=match.creator).with_for_update().first()
            joiner_user = User.query.filter_by(session_id=match.joiner).with_for_update().first()

            if not creator_user or not joiner_user:
                logger.error("Users not found in database")
                db.session.rollback()
                return None

            # Create game history record
            game_history = GameHistory(
                player1_id=creator_user.id,
                player2_id=joiner_user.id,
                player1_choice=creator_move,
                player2_choice=joiner_move,
                bet_amount=match.stake
            )
            
            if result == 'draw':
                logger.info("Match result: Draw")
                match.stats.draws += 1
                game_history.is_draw = True
                
                # Return stakes to both players
                creator_user.coins += match.stake
                joiner_user.coins += match.stake
                
                # Update stats
                creator_user.draws += 1
                creator_user.total_games += 1
                players[match.creator].stats.draws += 1
                players[match.creator].stats.total_games += 1
                joiner_user.draws += 1
                joiner_user.total_games += 1
                players[match.joiner].stats.draws += 1
                players[match.joiner].stats.total_games += 1

            elif result == 'player1':
                logger.info("Match result: Creator wins")
                match.stats.creator_wins += 1
                game_history.winner_id = creator_user.id
                
                # Winner gets both stakes
                creator_user.coins += 2 * match.stake
                
                # Update stats
                creator_user.wins += 1
                creator_user.total_games += 1
                creator_user.total_coins_won += match.stake
                players[match.creator].stats.wins += 1
                players[match.creator].stats.total_games += 1
                players[match.creator].stats.total_coins_won += match.stake
                joiner_user.losses += 1
                joiner_user.total_games += 1
                joiner_user.total_coins_lost += match.stake
                players[match.joiner].stats.losses += 1
                players[match.joiner].stats.total_games += 1
                players[match.joiner].stats.total_coins_lost += match.stake

            else:
                logger.info("Match result: Joiner wins")
                match.stats.joiner_wins += 1
                game_history.winner_id = joiner_user.id
                
                # Winner gets both stakes
                joiner_user.coins += 2 * match.stake
                
                # Update stats
                joiner_user.wins += 1
                joiner_user.total_games += 1
                joiner_user.total_coins_won += match.stake
                players[match.joiner].stats.wins += 1
                players[match.joiner].stats.total_games += 1
                players[match.joiner].stats.total_coins_won += match.stake
                creator_user.losses += 1
                creator_user.total_games += 1
                creator_user.total_coins_lost += match.stake
                players[match.creator].stats.losses += 1
                players[match.creator].stats.total_games += 1
                players[match.creator].stats.total_coins_lost += match.stake

            # Sync in-memory state
            players[match.creator].coins = creator_user.coins
            players[match.creator].stats.wins = creator_user.wins
            players[match.creator].stats.losses = creator_user.losses
            players[match.creator].stats.draws = creator_user.draws
            players[match.creator].stats.total_games = creator_user.total_games
            players[match.creator].stats.total_coins_won = creator_user.total_coins_won
            players[match.creator].stats.total_coins_lost = creator_user.total_coins_lost
            players[match.joiner].coins = joiner_user.coins
            players[match.joiner].stats.wins = joiner_user.wins
            players[match.joiner].stats.losses = joiner_user.losses
            players[match.joiner].stats.draws = joiner_user.draws
            players[match.joiner].stats.total_games = joiner_user.total_games
            players[match.joiner].stats.total_coins_won = joiner_user.total_coins_won
            players[match.joiner].stats.total_coins_lost = joiner_user.total_coins_lost

            # Update player stats in database
            db.session.commit()

            # Log stats update
            logger.info(f"Updated stats for {match.creator}: wins={creator_user.wins}, losses={creator_user.losses}, draws={creator_user.draws}, total_games={creator_user.total_games}, total_coins_won={creator_user.total_coins_won}, total_coins_lost={creator_user.total_coins_lost}")
            logger.info(f"Updated stats for {match.joiner}: wins={joiner_user.wins}, losses={joiner_user.losses}, draws={joiner_user.draws}, total_games={joiner_user.total_games}, total_coins_won={joiner_user.total_coins_won}, total_coins_lost={joiner_user.total_coins_lost}")
            
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

            # Set result and save to database
            if match.set_result(result_data):
                db.session.add(game_history)
                db.session.commit()
                logger.info("Match result saved to database")
                return result_data
            else:
                logger.info("Match result already processed, rolling back")
                db.session.rollback()
                return match.result

        except Exception as e:
            logger.exception("Error processing match result")
            db.session.rollback()
            return None