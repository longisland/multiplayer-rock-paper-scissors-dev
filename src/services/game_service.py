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

            # Check if either move was auto-selected
            creator_auto = match.creator in (match.auto_selected or set())
            joiner_auto = match.joiner in (match.auto_selected or set())

            # Log auto-selection status
            logger.info(f"Auto-selection status - Creator: {creator_auto}, Joiner: {joiner_auto}")

            # Create game history record with original moves
            game_history = GameHistory(
                player1_id=creator_user.id,
                player2_id=joiner_user.id,
                player1_choice=creator_move,
                player2_choice=joiner_move,
                bet_amount=match.stake,
                auto_selected=True if creator_auto or joiner_auto else False
            )
            
            # Log initial state
            logger.info(f"Processing result - Creator coins: {creator_user.coins}, Joiner coins: {joiner_user.coins}, Stake: {match.stake}")

            if result == 'draw':
                logger.info("Match result: Draw")
                match.stats.draws += 1
                game_history.is_draw = True
                
                # Handle draw based on auto-selection
                if not creator_auto and not joiner_auto:
                    # Manual vs Manual: both get stakes back
                    creator_user.coins += match.stake
                    joiner_user.coins += match.stake
                    logger.info("Manual draw: returning stakes to both players")
                else:
                    # Any auto-selection: neither gets stake back
                    logger.info("Auto-selection draw: stakes are lost")
                
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
                    # Auto win: no stake back
                    logger.info("Creator auto-win: stake is lost")
                elif joiner_auto:
                    # Manual win vs auto: get stake back
                    creator_user.coins += match.stake
                    logger.info("Creator manual win vs auto: returning stake only")
                else:
                    # Manual vs manual: get both stakes
                    creator_user.coins += 2 * match.stake
                    creator_user.total_coins_won += match.stake
                    joiner_user.total_coins_lost += match.stake
                    logger.info("Creator manual win vs manual: awarding double stake")
                
                # Update stats
                creator_user.wins += 1
                creator_user.total_games += 1
                joiner_user.losses += 1
                joiner_user.total_games += 1
                
                # Log state after win
                logger.info(f"After creator win - Creator coins: {creator_user.coins}, Joiner coins: {joiner_user.coins}")

            else:
                logger.info("Match result: Joiner wins")
                match.stats.joiner_wins += 1
                game_history.winner_id = joiner_user.id
                
                if joiner_auto:
                    # Auto win: no stake back
                    logger.info("Joiner auto-win: stake is lost")
                elif creator_auto:
                    # Manual win vs auto: get stake back
                    joiner_user.coins += match.stake
                    logger.info("Joiner manual win vs auto: returning stake only")
                else:
                    # Manual vs manual: get both stakes
                    joiner_user.coins += 2 * match.stake
                    joiner_user.total_coins_won += match.stake
                    creator_user.total_coins_lost += match.stake
                    logger.info("Joiner manual win vs manual: awarding double stake")
                
                # Update stats
                joiner_user.wins += 1
                joiner_user.total_games += 1
                creator_user.losses += 1
                creator_user.total_games += 1
                
                # Log state after win
                logger.info(f"After joiner win - Creator coins: {creator_user.coins}, Joiner coins: {joiner_user.coins}")

            # Sync in-memory state
            players[match.creator].coins = creator_user.coins
            players[match.joiner].coins = joiner_user.coins
            
            # Prepare result data
            result_data = {
                'winner': result,
                'creator_move': creator_move,
                'joiner_move': joiner_move,
                'match_stats': match.stats.to_dict(),
                'stake': match.stake,
                'can_rematch': (creator_user.coins >= match.stake and 
                              joiner_user.coins >= match.stake)
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