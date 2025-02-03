import random
from ..models.database import db, User, GameHistory
from datetime import datetime

class GameService:
    @staticmethod
    def calculate_winner(move1, move2):
        # Handle auto moves by converting them to random moves
        if move1 == 'auto':
            move1 = random.choice(['rock', 'paper', 'scissors'])
        if move2 == 'auto':
            move2 = random.choice(['rock', 'paper', 'scissors'])

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

        # Check if result was already processed
        if match.result is not None:
            logger.info("Match result already processed, returning existing result")
            return match.result

        creator_move = match.moves[match.creator]
        joiner_move = match.moves[match.joiner]
        
        # Store original moves for history
        original_creator_move = creator_move
        original_joiner_move = joiner_move
        
        # Check if moves were auto-selected
        creator_auto = creator_move == 'auto'
        joiner_auto = joiner_move == 'auto'
        
        # Convert auto moves to random moves for winner calculation
        if creator_auto:
            creator_move = GameService.random_move()
        if joiner_auto:
            joiner_move = GameService.random_move()
        
        result = GameService.calculate_winner(creator_move, joiner_move)

        try:
            # Start transaction
            db.session.begin_nested()

            # Get users from database with row locking
            creator_user = User.query.filter_by(username=match.creator).with_for_update().first()
            joiner_user = User.query.filter_by(username=match.joiner).with_for_update().first()

            if not creator_user or not joiner_user:
                logger.error("Users not found in database")
                db.session.rollback()
                return None

            # Create game history record with original moves
            game_history = GameHistory(
                player1_id=creator_user.id,
                player2_id=joiner_user.id,
                player1_choice=original_creator_move,
                player2_choice=original_joiner_move,
                bet_amount=match.stake
            )
            
            if result == 'draw':
                logger.info("Match result: Draw")
                match.stats.draws += 1
                game_history.is_draw = True
                
                # In draw, both players get their stakes back regardless of auto/manual
                creator_user.coins += match.stake
                joiner_user.coins += match.stake
                
                # Update stats
                creator_user.draws += 1
                creator_user.total_games += 1
                joiner_user.draws += 1
                joiner_user.total_games += 1

            elif result == 'player1':
                logger.info("Match result: Creator wins")
                match.stats.creator_wins += 1
                game_history.winner_id = creator_user.id
                
                if creator_auto:
                    # Auto-win: only get stake back
                    creator_user.coins += match.stake
                    logger.info("Creator auto-win: returning stake only")
                else:
                    # Manual win: get both stakes
                    creator_user.coins += 2 * match.stake
                    creator_user.total_coins_won += match.stake
                    joiner_user.total_coins_lost += match.stake
                    logger.info("Creator manual win: awarding double stake")
                
                # Update stats
                creator_user.wins += 1
                creator_user.total_games += 1
                joiner_user.losses += 1
                joiner_user.total_games += 1

            else:
                logger.info("Match result: Joiner wins")
                match.stats.joiner_wins += 1
                game_history.winner_id = joiner_user.id
                
                if joiner_auto:
                    # Auto-win: only get stake back
                    joiner_user.coins += match.stake
                    logger.info("Joiner auto-win: returning stake only")
                else:
                    # Manual win: get both stakes
                    joiner_user.coins += 2 * match.stake
                    joiner_user.total_coins_won += match.stake
                    creator_user.total_coins_lost += match.stake
                    logger.info("Joiner manual win: awarding double stake")
                
                # Update stats
                joiner_user.wins += 1
                joiner_user.total_games += 1
                creator_user.losses += 1
                creator_user.total_games += 1

            # Sync in-memory state
            players[match.creator].coins = creator_user.coins
            players[match.joiner].coins = joiner_user.coins
            
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