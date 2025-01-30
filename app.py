from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import secrets
import os
import random
from datetime import datetime, UTC, timedelta
from threading import Timer
import logging
from models import db, Player, Match
from config import Config

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='/static')
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()
    # Clean up any stale matches
    try:
        stale_matches = Match.query.filter(Match.status.in_(['playing', 'waiting'])).all()
        for match in stale_matches:
            if match.creator_id:
                creator = Player.query.filter_by(session_id=match.creator_id).first()
                if creator:
                    creator.current_match_id = None
            if match.joiner_id:
                joiner = Player.query.filter_by(session_id=match.joiner_id).first()
                if joiner:
                    joiner.current_match_id = None
            db.session.delete(match)
        db.session.commit()
    except Exception as e:
        logger.exception("Error cleaning up stale matches")
        db.session.rollback()

# Configure Flask-SocketIO
socketio = SocketIO(
    app,
    async_mode='gevent',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1000000,
    manage_session=False
)

# Match timers storage
match_timers = {}

def get_match(match_id):
    """Get a match by ID using the new SQLAlchemy API."""
    return db.session.get(Match, match_id)

def random_move():
    return random.choice(['rock', 'paper', 'scissors'])

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

def generate_session_id():
    return secrets.token_hex(8)

@app.route('/')
def index():
    if 'session_id' not in session:
        session_id = generate_session_id()
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
            session_id = generate_session_id()
            session['session_id'] = session_id
            new_player = Player(session_id=session_id)
            db.session.add(new_player)
            db.session.commit()
            logger.info(f"Created new session: {session_id}")
        
        player = Player.query.filter_by(session_id=session_id).first()
        if not player:
            player = Player(session_id=session_id)
            db.session.add(player)
            db.session.commit()
            logger.info(f"Reinitialized player: {session_id}")
        
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
        
        # Get current match details
        current_match = None
        if player.current_match_id:
            match = get_match(player.current_match_id)
            if match:
                current_match = {
                    'id': match.id,
                    'status': match.status,
                    'stake': match.stake,
                    'is_creator': session_id == match.creator_id,
                    'creator_ready': match.creator_ready,
                    'joiner_ready': match.joiner_ready
                }
        
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
            return jsonify({'error': 'Invalid session'}), 400
        
        stake = request.json.get('stake', 0)
        if not isinstance(stake, int) or stake <= 0:
            return jsonify({'error': 'Invalid stake'}), 400
        
        if player.coins < stake:
            return jsonify({'error': 'Insufficient coins'}), 400
        
        # Clear any existing match
        if player.current_match_id:
            current_match = get_match(player.current_match_id)
            if current_match:
                if current_match.id in match_timers:
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
            creator_ready=True
        )
        
        db.session.add(new_match)
        player.current_match_id = match_id
        db.session.commit()
        
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
            return jsonify({'error': 'Invalid session'}), 400
        
        match_id = request.json.get('match_id')
        match = get_match(match_id)
        if not match:
            return jsonify({'error': 'Invalid match'}), 400
        
        if match.status != 'waiting':
            return jsonify({'error': 'Match not available'}), 400
        
        if player.coins < match.stake:
            return jsonify({'error': 'Insufficient coins'}), 400
        
        # Clear any existing match
        if player.current_match_id and player.current_match_id != match_id:
            current_match = get_match(player.current_match_id)
            if current_match:
                if current_match.id in match_timers:
                    match_timers[current_match.id].cancel()
                    match_timers.pop(current_match.id)
                db.session.delete(current_match)
            player.current_match_id = None
        
        match.joiner_id = session_id
        player.current_match_id = match_id
        db.session.commit()
        
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
            return jsonify({'error': 'Invalid session'}), 400
        
        move = request.json.get('move')
        if move not in ['rock', 'paper', 'scissors']:
            return jsonify({'error': 'Invalid move'}), 400
        
        if not player.current_match_id:
            return jsonify({'error': 'No active match'}), 400
        
        match = Match.query.filter_by(id=player.current_match_id).with_for_update().first()
        if not match:
            return jsonify({'error': 'Match not found'}), 400
        
        if match.status != 'playing':
            return jsonify({'error': 'Match not in playing state'}), 400
        
        if session_id not in [match.creator_id, match.joiner_id]:
            return jsonify({'error': 'Not part of match'}), 400
        
        if (session_id == match.creator_id and match.creator_move) or \
           (session_id == match.joiner_id and match.joiner_move):
            return jsonify({'error': 'Already made a move'}), 400
        
        if session_id == match.creator_id:
            match.creator_move = move
            socketio.emit('move_made', {'player': 'creator'}, room=match.id)
        else:
            match.joiner_move = move
            socketio.emit('move_made', {'player': 'joiner'}, room=match.id)
        
        db.session.commit()
        
        if match.creator_move and match.joiner_move:
            calculate_and_emit_result(match.id)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error making move")
        return jsonify({'error': 'Internal server error'}), 500

def calculate_and_emit_result(match_id):
    try:
        match = get_match(match_id)
        if not match or not match.creator_move or not match.joiner_move:
            return
        
        result = calculate_winner(match.creator_move, match.joiner_move)
        
        creator = Player.query.filter_by(session_id=match.creator_id).first()
        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
        
        if not creator or not joiner:
            return
        
        stake = match.stake
        
        match.status = 'finished'
        match.finished_at = datetime.now(UTC)
        match.creator_ready = False
        match.joiner_ready = False
        
        creator.current_match_id = match.id
        joiner.current_match_id = match.id
        
        if result == 'draw':
            creator.draws += 1
            joiner.draws += 1
            creator.coins += stake
            joiner.coins += stake
        elif result == 'player1':
            creator.wins += 1
            joiner.losses += 1
            creator.coins += stake * 2
            creator.total_coins_won += stake
            joiner.total_coins_lost += stake
            match.winner_id = creator.session_id
        else:
            creator.losses += 1
            joiner.wins += 1
            joiner.coins += stake * 2
            creator.total_coins_lost += stake
            joiner.total_coins_won += stake
            match.winner_id = joiner.session_id
        
        db.session.commit()
        
        socketio.emit('match_result', {
            'creator_move': match.creator_move,
            'joiner_move': match.joiner_move,
            'result': result,
            'creator_coins': creator.coins,
            'joiner_coins': joiner.coins,
            'can_rematch': (creator.coins >= stake and joiner.coins >= stake)
        }, room=match.id)
    except Exception as e:
        logger.exception(f"Error calculating result for match {match_id}")

@socketio.on('join_match_room')
def on_join_match_room(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            return
        
        match = get_match(match_id)
        if not match:
            return
        
        if session_id not in [match.creator_id, match.joiner_id]:
            return
        
        join_room(match_id)
        
        if match.status == 'waiting' and match.creator_id and match.joiner_id:
            match.status = 'playing'
            match.started_at = datetime.now(UTC)
            
            creator = Player.query.filter_by(session_id=match.creator_id).first()
            joiner = Player.query.filter_by(session_id=match.joiner_id).first()
            
            if not creator or not joiner:
                return
            
            creator.coins -= match.stake
            joiner.coins -= match.stake
            
            db.session.commit()
            
            if match.id in match_timers:
                match_timers[match.id].cancel()
            match_timers[match.id] = Timer(30, handle_match_timeout, args=[match.id])
            match_timers[match.id].start()
            
            socketio.emit('match_started', {
                'match_id': match.id,
                'stake': match.stake,
                'is_creator': True,
                'creator_coins': creator.coins,
                'joiner_coins': joiner.coins
            }, room=match.creator_id)
            
            socketio.emit('match_started', {
                'match_id': match.id,
                'stake': match.stake,
                'is_creator': False,
                'creator_coins': creator.coins,
                'joiner_coins': joiner.coins
            }, room=match.joiner_id)
    except Exception as e:
        logger.exception("Error in join_match_room handler")

@socketio.on('leave_match_room')
def on_leave_match_room(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            return
        
        leave_room(match_id)
    except Exception as e:
        logger.exception("Error in leave_match_room handler")

def handle_match_timeout(match_id):
    try:
        match = get_match(match_id)
        if not match or match.status != 'playing':
            return
        
        if not match.creator_move:
            match.creator_move = random_move()
            socketio.emit('move_made', {'player': 'creator', 'auto': True}, room=match_id)
        
        if not match.joiner_move:
            match.joiner_move = random_move()
            socketio.emit('move_made', {'player': 'joiner', 'auto': True}, room=match_id)
        
        db.session.commit()
        calculate_and_emit_result(match_id)
    except Exception as e:
        logger.exception(f"Error in match timeout handler for match {match_id}")

@socketio.on('rematch_accepted')
def on_rematch_accepted(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            return
        
        match = get_match(match_id)
        if not match:
            return
        
        creator = Player.query.filter_by(session_id=match.creator_id).first()
        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
        
        if not creator or not joiner:
            return
        
        if creator.coins < match.stake or joiner.coins < match.stake:
            socketio.emit('rematch_declined', {
                'reason': 'insufficient_coins'
            }, room=match_id)
            return
        
        # Update ready state
        if session_id == match.creator_id:
            match.creator_ready = True
            logger.info(f"Creator {session_id} ready for rematch")
        elif session_id == match.joiner_id:
            match.joiner_ready = True
            logger.info(f"Joiner {session_id} ready for rematch")
        
        db.session.commit()
        
        # Notify others about rematch acceptance
        socketio.emit('rematch_accepted_by_player', {
            'player': 'creator' if session_id == match.creator_id else 'joiner',
            'match_id': match_id
        }, room=match_id)
        
        # If both players are ready, start new match
        if match.creator_ready and match.joiner_ready:
            logger.info(f"Both players ready for rematch")
            
            # Deduct stakes
            creator.coins -= match.stake
            joiner.coins -= match.stake
            
            # Reset match state
            match.status = 'playing'
            match.started_at = datetime.now(UTC)
            match.finished_at = None
            match.creator_move = None
            match.joiner_move = None
            match.winner_id = None
            match.creator_ready = False
            match.joiner_ready = False
            
            db.session.commit()
            
            # Start match timer
            if match.id in match_timers:
                match_timers[match.id].cancel()
            match_timers[match.id] = Timer(30, handle_match_timeout, args=[match.id])
            match_timers[match.id].start()
            
            # Notify players about match start
            socketio.emit('match_started', {
                'match_id': match.id,
                'stake': match.stake,
                'is_creator': True,
                'rematch': True,
                'creator_coins': creator.coins,
                'joiner_coins': joiner.coins
            }, room=match.creator_id)
            
            socketio.emit('match_started', {
                'match_id': match.id,
                'stake': match.stake,
                'is_creator': False,
                'rematch': True,
                'creator_coins': creator.coins,
                'joiner_coins': joiner.coins
            }, room=match.joiner_id)
    except Exception as e:
        logger.exception("Error in rematch_accepted handler")

@socketio.on('rematch_declined')
def on_rematch_declined(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            return
        
        match = get_match(match_id)
        if not match:
            return
        
        # Reset ready states
        match.creator_ready = False
        match.joiner_ready = False
        db.session.commit()
        
        socketio.emit('rematch_declined', {}, room=match_id)
    except Exception as e:
        logger.exception("Error in rematch_declined handler")

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)