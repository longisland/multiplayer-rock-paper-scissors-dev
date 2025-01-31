import secrets
from datetime import datetime, UTC, timedelta
import logging
from flask import render_template, request, jsonify, session
from flask_socketio import emit, join_room, leave_room
from ..models.models import db, Player, Match
from ..game.game_logic import get_match, random_move, calculate_winner, handle_match_timeout, match_timers

logger = logging.getLogger(__name__)

def init_routes(app, socketio):
    @app.route('/')
    def index():
        if 'session_id' not in session:
            session_id = secrets.token_hex(8)
            session['session_id'] = session_id
            new_player = Player(session_id=session_id)
            db.session.add(new_player)
            db.session.commit()
            logger.info(f"Created new session: {session_id}")
        return render_template('index.html')

    @app.route('/api/state')
    def get_state():
        try:
            session_id = session.get('session_id')
            if not session_id:
                # Create new session if none exists
                session_id = secrets.token_hex(8)
                session['session_id'] = session_id
                new_player = Player(session_id=session_id)
                db.session.add(new_player)
                db.session.commit()
                logger.info(f"Created new session: {session_id}")
            
            player = Player.query.filter_by(session_id=session_id).first()
            if not player:
                # Reinitialize player if not found
                player = Player(session_id=session_id)
                db.session.add(player)
                db.session.commit()
                logger.info(f"Reinitialized player: {session_id}")
            
            # Update last active timestamp
            player.last_active = datetime.now(UTC)
            db.session.commit()
            
            # Get open matches
            open_matches = []
            available_matches = Match.query.filter_by(status='waiting').all()
            
            for match in available_matches:
                if (match.creator_id != session_id and 
                    match.creator.coins >= match.stake and
                    player.coins >= match.stake):
                    open_matches.append({
                        'id': match.id,
                        'stake': match.stake
                    })
            
            # Get current match details if in a match
            current_match = None
            if player.current_match_id:
                match = get_match(player.current_match_id)
                if match:
                    # Check if match is stale
                    if match.started_at:
                        cutoff_time = datetime.now(UTC) - timedelta(seconds=30)
                        match_time = match.started_at.replace(tzinfo=UTC) if match.started_at.tzinfo is None else match.started_at
                        if match_time < cutoff_time:
                            # Clean up stale match
                            if match.status == 'playing':
                                handle_match_timeout(match.id)
                            else:
                                player.current_match_id = None
                                db.session.delete(match)
                                db.session.commit()
                            match = None
                    
                    if match:
                        current_match = {
                            'id': match.id,
                            'status': match.status,
                            'stake': match.stake,
                            'is_creator': session_id == match.creator_id
                        }
            
            logger.debug(f"State for {session_id}: coins={player.coins}, current_match={current_match}")
            return jsonify({
                'coins': player.coins,
                'stats': {
                    'wins': player.wins,
                    'losses': player.losses,
                    'draws': player.draws,
                    'total_coins_won': player.total_coins_won,
                    'total_coins_lost': player.total_coins_lost
                },
                'open_matches': open_matches,
                'current_match': current_match
            })
        except Exception as e:
            logger.exception("Error getting state")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/create_match', methods=['POST'])
    def create_match():
        try:
            session_id = session.get('session_id')
            player = Player.query.filter_by(session_id=session_id).first()
            if not player:
                logger.error(f"Invalid session: {session_id}")
                return jsonify({'error': 'Invalid session'}), 400
            
            stake = request.json.get('stake', 0)
            if not isinstance(stake, int) or stake <= 0:
                logger.error(f"Invalid stake: {stake}")
                return jsonify({'error': 'Invalid stake'}), 400
            
            if player.coins < stake:
                logger.error(f"Insufficient coins. Has: {player.coins}, Needs: {stake}")
                return jsonify({'error': 'Insufficient coins'}), 400
            
            # Clear any existing match
            if player.current_match_id:
                current_match = get_match(player.current_match_id)
                if current_match:
                    logger.info(f"Cleaning up existing match: {current_match.id}")
                    if current_match.id in match_timers and match_timers[current_match.id]:
                        match_timers[current_match.id].cancel()
                        match_timers.pop(current_match.id)
                    db.session.delete(current_match)
                player.current_match_id = None
            
            match_id = secrets.token_hex(4)
            new_match = Match(
                id=match_id,
                creator_id=session_id,
                stake=stake,
                status='waiting',
                creator_ready=True  # Creator is automatically ready
            )
            
            db.session.add(new_match)
            player.current_match_id = match_id
            db.session.commit()
            
            logger.info(f"Match created: {match_id} by {session_id}")
            logger.info(f"Creator {session_id} ready in match {match_id}")
            return jsonify({'match_id': match_id})
        except Exception as e:
            logger.exception("Error creating match")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/join_match', methods=['POST'])
    def join_match():
        try:
            session_id = session.get('session_id')
            player = Player.query.filter_by(session_id=session_id).first()
            if not player:
                logger.error(f"Invalid session: {session_id}")
                return jsonify({'error': 'Invalid session'}), 400
            
            match_id = request.json.get('match_id')
            match = get_match(match_id)
            if not match:
                logger.error(f"Invalid match: {match_id}")
                return jsonify({'error': 'Invalid match'}), 400
            
            if match.status != 'waiting':
                logger.error(f"Match not available. Status: {match.status}")
                return jsonify({'error': 'Match not available'}), 400
            
            if player.coins < match.stake:
                logger.error(f"Insufficient coins. Has: {player.coins}, Needs: {match.stake}")
                return jsonify({'error': 'Insufficient coins'}), 400
            
            # Clear any existing match for the joining player
            if player.current_match_id and player.current_match_id != match_id:
                current_match = get_match(player.current_match_id)
                if current_match:
                    logger.info(f"Cleaning up existing match: {current_match.id}")
                    if current_match.id in match_timers and match_timers[current_match.id]:
                        match_timers[current_match.id].cancel()
                        match_timers.pop(current_match.id)
                    db.session.delete(current_match)
                player.current_match_id = None
            
            # Update match and player state
            match.joiner_id = session_id
            player.current_match_id = match_id
            db.session.commit()
            
            logger.info(f"Player {session_id} joined match {match_id}")
            return jsonify({'success': True})
        except Exception as e:
            logger.exception("Error joining match")
            return jsonify({'error': 'Internal server error'}), 500

    @app.route('/api/move', methods=['POST'])
    def make_move():
        try:
            session_id = session.get('session_id')
            player = Player.query.filter_by(session_id=session_id).first()
            if not player:
                logger.error(f"Invalid session: {session_id}")
                return jsonify({'error': 'Invalid session'}), 400
            
            move = request.json.get('move')
            if move not in ['rock', 'paper', 'scissors']:
                logger.error(f"Invalid move: {move}")
                return jsonify({'error': 'Invalid move'}), 400
            
            # Lock the player for update to get the latest state
            player = Player.query.filter_by(session_id=session_id).with_for_update().first()
            if not player:
                logger.error(f"Player {session_id} disappeared")
                return jsonify({'error': 'Player not found'}), 400
            
            if not player.current_match_id:
                logger.error(f"No active match for player {session_id}")
                return jsonify({'error': 'No active match'}), 400
            
            # Lock the match for update
            match = Match.query.filter_by(id=player.current_match_id).with_for_update().first()
            if not match:
                logger.error(f"Match {player.current_match_id} not found")
                return jsonify({'error': 'Match not found'}), 400
            
            # Check if match is too old (more than 10 seconds)
            if match.started_at:
                # Convert naive datetime to UTC
                if match.started_at.tzinfo is None:
                    match_start = match.started_at.replace(tzinfo=UTC)
                else:
                    match_start = match.started_at
                
                if match_start < datetime.now(UTC) - timedelta(seconds=10):
                    logger.error(f"Match {match.id} has timed out")
                    handle_match_timeout(match.id)
                    return jsonify({'error': 'Match has timed out. Random moves were assigned.'}), 400
            
            if match.status != 'playing':
                logger.error(f"Match {match.id} not in playing state. Status: {match.status}")
                return jsonify({'error': 'Match not in playing state'}), 400
            
            # Check if player is part of the match
            if session_id not in [match.creator_id, match.joiner_id]:
                logger.error(f"Player {session_id} not part of match {match.id}")
                return jsonify({'error': 'Not part of match'}), 400
            
            # Record the move
            if session_id == match.creator_id:
                if match.creator_move:
                    logger.error(f"Creator {session_id} already made a move in match {match.id}")
                    return jsonify({'error': 'Move already made'}), 400
                match.creator_move = move
                logger.info(f"Creator {session_id} made move {move} in match {match.id}")
                socketio.emit('move_made', {'player': 'creator'}, room=match.id)
            else:
                if match.joiner_move:
                    logger.error(f"Joiner {session_id} already made a move in match {match.id}")
                    return jsonify({'error': 'Move already made'}), 400
                match.joiner_move = move
                logger.info(f"Joiner {session_id} made move {move} in match {match.id}")
                socketio.emit('move_made', {'player': 'joiner'}, room=match.id)
            
            db.session.commit()
            
            # If both moves are made, calculate result
            if match.creator_move and match.joiner_move:
                calculate_and_emit_result(match.id)
            
            return jsonify({'success': True})
        except Exception as e:
            logger.exception("Error making move")
            return jsonify({'error': 'Internal server error'}), 500

    @socketio.on('join')
    def on_join(data):
        try:
            session_id = session.get('session_id')
            if not session_id:
                logger.error("No session ID in join request")
                return
            
            match_id = data.get('match_id')
            if not match_id:
                logger.error("No match ID in join request")
                return
            
            match = get_match(match_id)
            if not match:
                logger.error(f"Match {match_id} not found in join request")
                return
            
            if session_id not in [match.creator_id, match.joiner_id]:
                logger.error(f"Player {session_id} not part of match {match_id}")
                return
            
            join_room(match_id)
            logger.info(f"Player {session_id} joined room for match {match_id}")
            
            # If both players are ready, start the match
            if match.creator_ready and match.joiner_ready and match.status == 'waiting':
                match.status = 'playing'
                match.started_at = datetime.now(UTC)
                db.session.commit()
                
                # Set up match timeout
                if match.id in match_timers and match_timers[match.id]:
                    match_timers[match.id].cancel()
                timer = Timer(10.0, handle_match_timeout, args=[match.id])
                timer.start()
                match_timers[match.id] = timer
                
                emit('match_started', room=match_id)
                logger.info(f"Match {match_id} started")
        except Exception as e:
            logger.exception("Error in join handler")

    @socketio.on('ready')
    def on_ready(data):
        try:
            session_id = session.get('session_id')
            if not session_id:
                logger.error("No session ID in ready request")
                return
            
            match_id = data.get('match_id')
            if not match_id:
                logger.error("No match ID in ready request")
                return
            
            match = get_match(match_id)
            if not match:
                logger.error(f"Match {match_id} not found in ready request")
                return
            
            if session_id == match.creator_id:
                match.creator_ready = True
                logger.info(f"Creator {session_id} ready in match {match_id}")
            elif session_id == match.joiner_id:
                match.joiner_ready = True
                logger.info(f"Joiner {session_id} ready in match {match_id}")
            else:
                logger.error(f"Player {session_id} not part of match {match_id}")
                return
            
            db.session.commit()
            
            # If both players are ready, start the match
            if match.creator_ready and match.joiner_ready and match.status == 'waiting':
                match.status = 'playing'
                match.started_at = datetime.now(UTC)
                db.session.commit()
                
                # Set up match timeout
                if match.id in match_timers and match_timers[match.id]:
                    match_timers[match.id].cancel()
                timer = Timer(10.0, handle_match_timeout, args=[match.id])
                timer.start()
                match_timers[match.id] = timer
                
                emit('match_started', room=match_id)
                logger.info(f"Match {match_id} started")
        except Exception as e:
            logger.exception("Error in ready handler")

    @socketio.on('leave')
    def on_leave(data):
        try:
            session_id = session.get('session_id')
            if not session_id:
                logger.error("No session ID in leave request")
                return
            
            match_id = data.get('match_id')
            if not match_id:
                logger.error("No match ID in leave request")
                return
            
            leave_room(match_id)
            logger.info(f"Player {session_id} left room for match {match_id}")
        except Exception as e:
            logger.exception("Error in leave handler")

    def calculate_and_emit_result(match_id):
        try:
            match = get_match(match_id)
            if not match:
                logger.error(f"Match {match_id} not found in result calculation")
                return
            
            if not match.creator_move or not match.joiner_move:
                logger.error(f"Missing moves in match {match_id}")
                return
            
            # Cancel match timer if it exists
            if match.id in match_timers and match_timers[match.id]:
                match_timers[match.id].cancel()
                match_timers.pop(match.id)
            
            # Calculate winner
            result = calculate_winner(match.creator_move, match.joiner_move)
            
            # Update match status
            match.status = 'finished'
            match.finished_at = datetime.now(UTC)
            
            # Get players
            creator = Player.query.filter_by(session_id=match.creator_id).first()
            joiner = Player.query.filter_by(session_id=match.joiner_id).first()
            
            if not creator or not joiner:
                logger.error(f"Players not found for match {match_id}")
                return
            
            # Update player stats and coins
            if result == 'draw':
                creator.draws += 1
                joiner.draws += 1
                match.winner = None
            elif result == 'player1':  # Creator wins
                creator.wins += 1
                creator.coins += match.stake
                creator.total_coins_won += match.stake
                joiner.losses += 1
                joiner.coins -= match.stake
                joiner.total_coins_lost += match.stake
                match.winner = creator.session_id
            else:  # Joiner wins
                joiner.wins += 1
                joiner.coins += match.stake
                joiner.total_coins_won += match.stake
                creator.losses += 1
                creator.coins -= match.stake
                creator.total_coins_lost += match.stake
                match.winner = joiner.session_id
            
            # Clear current match references
            creator.current_match_id = None
            joiner.current_match_id = None
            
            db.session.commit()
            
            # Emit result to both players
            emit('match_result', {
                'creator_move': match.creator_move,
                'joiner_move': match.joiner_move,
                'winner': match.winner,
                'stake': match.stake
            }, room=match_id)
            
            logger.info(f"Match {match_id} finished. Winner: {match.winner}")
        except Exception as e:
            logger.exception(f"Error calculating result for match {match_id}")
            # Try to clean up the match in case of error
            try:
                match = get_match(match_id)
                if match:
                    match.status = 'finished'
                    match.finished_at = datetime.now(UTC)
                    if match.creator_id:
                        creator = Player.query.filter_by(session_id=match.creator_id).first()
                        if creator:
                            creator.current_match_id = None
                    if match.joiner_id:
                        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
                        if joiner:
                            joiner.current_match_id = None
                    db.session.commit()
            except Exception as cleanup_error:
                logger.exception(f"Error cleaning up match {match_id} after result error")