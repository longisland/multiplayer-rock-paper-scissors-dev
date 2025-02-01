from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import secrets
import os
import random
import time
from datetime import datetime
from threading import Timer
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='/static')
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['DEBUG'] = True

# Configure Flask-SocketIO
socketio = SocketIO(
    app,
    async_mode='threading',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1000000,
    manage_session=False  # Let Flask manage the sessions
)

# In-memory storage
players = {}  # session_id -> {coins, current_match, stats}
matches = {}  # match_id -> {creator, joiner, stake, moves, status, timer, start_time, stats}

def create_player_stats():
    return {
        'wins': 0,
        'losses': 0,
        'draws': 0,
        'total_coins_won': 0,
        'total_coins_lost': 0
    }

def random_move():
    return random.choice(['rock', 'paper', 'scissors'])

def handle_match_timeout(match_id):
    try:
        if match_id not in matches:
            logger.error(f"Match {match_id} not found in timeout handler")
            return
        
        match = matches[match_id]
        if match['status'] != 'playing':
            logger.error(f"Match {match_id} not in playing state in timeout handler")
            return
        
        logger.info(f"Match {match_id} timed out. Processing...")
        
        # Assign random moves to players who haven't made a move
        if match['creator'] not in match['moves']:
            move = random_move()
            match['moves'][match['creator']] = move
            logger.info(f"Assigned random move {move} to creator in match {match_id}")
            socketio.emit('move_made', {'player': 'creator', 'auto': True}, room=match_id)
        
        if match['joiner'] not in match['moves']:
            move = random_move()
            match['moves'][match['joiner']] = move
            logger.info(f"Assigned random move {move} to joiner in match {match_id}")
            socketio.emit('move_made', {'player': 'joiner', 'auto': True}, room=match_id)
        
        # Calculate and emit result
        calculate_and_emit_result(match_id)
    except Exception as e:
        logger.exception(f"Error in match timeout handler for match {match_id}")

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
        players[session_id] = {
            'coins': 100,
            'current_match': None,
            'stats': create_player_stats()
        }
        logger.info(f"Created new session: {session_id}")
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    try:
        session_id = session.get('session_id')
        if not session_id:
            # Create new session if none exists
            session_id = generate_session_id()
            session['session_id'] = session_id
            players[session_id] = {
                'coins': 100,
                'current_match': None,
                'stats': create_player_stats()
            }
            logger.info(f"Created new session: {session_id}")
        
        if session_id not in players:
            # Reinitialize player if not found
            players[session_id] = {
                'coins': 100,
                'current_match': None,
                'stats': create_player_stats()
            }
            logger.info(f"Reinitialized player: {session_id}")
        
        player = players[session_id]
        
        # Get open matches that:
        # 1. Are in waiting state
        # 2. Are not created by current player
        # 3. Have a creator with enough coins
        # 4. Current player has enough coins to join
        open_matches = []
        for mid, m in matches.items():
            if (m['status'] == 'waiting' and 
                m['creator'] != session_id and 
                players[m['creator']]['coins'] >= m['stake'] and
                player['coins'] >= m['stake']):
                open_matches.append({
                    'id': mid,
                    'stake': m['stake']
                })
        
        # Get current match details if in a match
        current_match = None
        if player['current_match'] and player['current_match'] in matches:
            match = matches[player['current_match']]
            current_match = {
                'id': player['current_match'],
                'status': match['status'],
                'stake': match['stake'],
                'is_creator': session_id == match['creator']
            }
        
        logger.debug(f"State for {session_id}: coins={player['coins']}, current_match={current_match}")
        return jsonify({
            'coins': player['coins'],
            'stats': player['stats'],
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
        if not session_id or session_id not in players:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400
        
        stake = request.json.get('stake', 0)
        if not isinstance(stake, int) or stake <= 0:
            logger.error(f"Invalid stake: {stake}")
            return jsonify({'error': 'Invalid stake'}), 400
        
        if players[session_id]['coins'] < stake:
            logger.error(f"Insufficient coins. Has: {players[session_id]['coins']}, Needs: {stake}")
            return jsonify({'error': 'Insufficient coins'}), 400
        
        # Clear any existing match
        current_match = players[session_id]['current_match']
        if current_match:
            if current_match in matches:
                logger.info(f"Cleaning up existing match: {current_match}")
                if matches[current_match]['timer']:
                    matches[current_match]['timer'].cancel()
                del matches[current_match]
            players[session_id]['current_match'] = None
        
        match_id = secrets.token_hex(4)
        matches[match_id] = {
            'creator': session_id,
            'joiner': None,
            'stake': stake,
            'moves': {},
            'status': 'waiting',
            'timer': None,
            'start_time': None,
            'creator_ready': True,  # Creator is automatically ready
            'joiner_ready': False,
            'stats': {
                'rounds': 0,
                'creator_wins': 0,
                'joiner_wins': 0,
                'draws': 0
            }
        }
        
        players[session_id]['current_match'] = match_id
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
        if not session_id or session_id not in players:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400
        
        match_id = request.json.get('match_id')
        if not match_id or match_id not in matches:
            logger.error(f"Invalid match: {match_id}")
            return jsonify({'error': 'Invalid match'}), 400
        
        match = matches[match_id]
        if match['status'] != 'waiting':
            logger.error(f"Match not available. Status: {match['status']}")
            return jsonify({'error': 'Match not available'}), 400
        
        if players[session_id]['coins'] < match['stake']:
            logger.error(f"Insufficient coins. Has: {players[session_id]['coins']}, Needs: {match['stake']}")
            return jsonify({'error': 'Insufficient coins'}), 400
        
        # Clear any existing match for the joining player
        current_match = players[session_id]['current_match']
        if current_match and current_match != match_id:
            if current_match in matches:
                logger.info(f"Cleaning up existing match: {current_match}")
                if matches[current_match]['timer']:
                    matches[current_match]['timer'].cancel()
                del matches[current_match]
            players[session_id]['current_match'] = None
        
        # Update match and player state
        match['joiner'] = session_id
        players[session_id]['current_match'] = match_id
        
        logger.info(f"Player {session_id} joined match {match_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error joining match")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/move', methods=['POST'])
def make_move():
    try:
        session_id = session.get('session_id')
        if not session_id or session_id not in players:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400
        
        move = request.json.get('move')
        if move not in ['rock', 'paper', 'scissors']:
            logger.error(f"Invalid move: {move}")
            return jsonify({'error': 'Invalid move'}), 400
        
        match_id = players[session_id]['current_match']
        if not match_id or match_id not in matches:
            logger.error(f"No active match for player {session_id}")
            return jsonify({'error': 'No active match'}), 400
        
        match = matches[match_id]
        if match['status'] != 'playing':
            logger.error(f"Match {match_id} not in playing state. Status: {match['status']}")
            return jsonify({'error': 'Match not in playing state'}), 400
        
        if session_id in match['moves']:
            logger.error(f"Player {session_id} already made a move in match {match_id}")
            return jsonify({'error': 'Move already made'}), 400
        
        match['moves'][session_id] = move
        logger.info(f"Player {session_id} made move {move} in match {match_id}")
        
        # Notify others that a move was made (without revealing the move)
        socketio.emit('move_made', {
            'player': 'creator' if session_id == match['creator'] else 'joiner',
            'auto': False
        }, room=match_id)
        
        if len(match['moves']) == 2:
            calculate_and_emit_result(match_id)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error making move")
        return jsonify({'error': 'Internal server error'}), 500

def calculate_and_emit_result(match_id):
    match = matches[match_id]
    creator_move = match['moves'][match['creator']]
    joiner_move = match['moves'][match['joiner']]
    result = calculate_winner(creator_move, joiner_move)
    
    # Cancel timer if it exists
    if match['timer']:
        match['timer'].cancel()
        match['timer'] = None
        
    # Store stake for potential rematch
    stake = match['stake']
    
    # Update match stats
    match['stats']['rounds'] += 1
    if result == 'draw':
        match['stats']['draws'] += 1
    elif result == 'player1':
        match['stats']['creator_wins'] += 1
    else:
        match['stats']['joiner_wins'] += 1
    
    # Update player stats and coins
    if result == 'draw':
        players[match['creator']]['stats']['draws'] += 1
        players[match['joiner']]['stats']['draws'] += 1
    elif result == 'player1':
        players[match['creator']]['stats']['wins'] += 1
        players[match['creator']]['stats']['total_coins_won'] += match['stake']
        players[match['joiner']]['stats']['losses'] += 1
        players[match['joiner']]['stats']['total_coins_lost'] += match['stake']
        players[match['creator']]['coins'] += match['stake']
        players[match['joiner']]['coins'] -= match['stake']
    else:
        players[match['joiner']]['stats']['wins'] += 1
        players[match['joiner']]['stats']['total_coins_won'] += match['stake']
        players[match['creator']]['stats']['losses'] += 1
        players[match['creator']]['stats']['total_coins_lost'] += match['stake']
        players[match['creator']]['coins'] -= match['stake']
        players[match['joiner']]['coins'] += match['stake']
    
    match['status'] = 'finished'
    match['result'] = {
        'winner': result,
        'creator_move': creator_move,
        'joiner_move': joiner_move,
        'match_stats': match['stats'],
        'creator_stats': players[match['creator']]['stats'],
        'joiner_stats': players[match['joiner']]['stats'],
        'stake': stake,
        'can_rematch': (players[match['creator']]['coins'] >= stake and 
                       players[match['joiner']]['coins'] >= stake)
    }
    
    # Notify both players
    socketio.emit('match_result', match['result'], room=match_id)
    
    # Clear current match
    players[match['creator']]['current_match'] = None
    players[match['joiner']]['current_match'] = None

@socketio.on('connect')
def handle_connect():
    try:
        session_id = session.get('session_id')
        if session_id:
            join_room(session_id)
            logger.info(f"Socket connected for session {session_id}")
            
            # If player is in a match, join that room too
            if session_id in players and players[session_id]['current_match']:
                match_id = players[session_id]['current_match']
                if match_id in matches:
                    join_room(match_id)
                    logger.info(f"Player {session_id} joined match room {match_id}")
    except Exception as e:
        logger.exception("Error in socket connect handler")

@socketio.on('join_match_room')
def on_join_match_room(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in join_match_room: {session_id}, {match_id}")
            return
        
        if match_id not in matches:
            logger.error(f"Match {match_id} not found")
            return
        
        match = matches[match_id]
        if match['status'] != 'waiting':
            logger.error(f"Match {match_id} not in waiting state. Status: {match['status']}")
            return
        
        join_room(match_id)
        logger.info(f"Player {session_id} joined match room {match_id} via socket")
    except Exception as e:
        logger.exception("Error in join_match_room handler")

@socketio.on('ready_for_match')
def on_ready_for_match(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id or match_id not in matches:
            logger.error(f"Invalid session or match ID in ready_for_match: {session_id}, {match_id}")
            return
        
        match = matches[match_id]
        if match['status'] != 'waiting':
            logger.error(f"Match {match_id} not in waiting state. Status: {match['status']}")
            return
        
        # Mark player as ready
        if session_id == match['creator']:
            match['creator_ready'] = True
            logger.info(f"Creator {session_id} ready in match {match_id}")
        elif session_id == match['joiner']:
            match['joiner_ready'] = True
            logger.info(f"Joiner {session_id} ready in match {match_id}")
        else:
            logger.error(f"Player {session_id} not part of match {match_id}")
            return
        
        # Start the match if both players are ready and both are in the match
        if (match.get('creator_ready') and match.get('joiner_ready') and 
            match['creator'] and match['joiner'] and match['status'] == 'waiting'):
            
            # Double check both players have enough coins
            if (players[match['creator']]['coins'] >= match['stake'] and 
                players[match['joiner']]['coins'] >= match['stake']):
                
                match['status'] = 'playing'
                match['start_time'] = time.time()
                match['moves'] = {}  # Reset moves
                
                # Start the timer
                if match['timer']:
                    match['timer'].cancel()
                match['timer'] = Timer(10.0, handle_match_timeout, args=[match_id])
                match['timer'].start()
                
                # Notify both players
                socketio.emit('match_started', {
                    'match_id': match_id,
                    'start_time': match['start_time']
                }, room=match_id)
                
                logger.info(f"Match {match_id} started for both players")
            else:
                logger.error(f"Insufficient coins for match {match_id}")
                socketio.emit('match_error', {
                    'error': 'Insufficient coins'
                }, room=match_id)
    except Exception as e:
        logger.exception("Error in ready_for_match handler")

@socketio.on('rematch_accepted')
def on_rematch_accepted(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id or match_id not in matches:
            logger.error(f"Invalid session or match ID in rematch_accepted: {session_id}, {match_id}")
            return
        
        match = matches[match_id]
        stake = match['stake']
        
        # Check if both players have enough coins
        if (players[match['creator']]['coins'] < stake or 
            players[match['joiner']]['coins'] < stake):
            logger.error(f"Insufficient coins for rematch in match {match_id}")
            socketio.emit('rematch_declined', {
                'error': 'Insufficient coins'
            }, room=match_id)
            return
        
        # Initialize rematch_ready if not exists
        if 'rematch_ready' not in match:
            match['rematch_ready'] = set()
        
        # Add this player to ready set
        match['rematch_ready'].add(session_id)
        
        # Notify other player
        socketio.emit('rematch_accepted_by_player', {
            'player': 'creator' if session_id == match['creator'] else 'joiner'
        }, room=match_id)
        
        # Only proceed if both players have accepted
        if len(match['rematch_ready']) == 2:
            # Create new match with same stake but random creator
            new_creator = random.choice([match['creator'], match['joiner']])
            new_joiner = match['joiner'] if new_creator == match['creator'] else match['creator']
        
        new_match_id = secrets.token_hex(4)
        matches[new_match_id] = {
            'creator': new_creator,
            'joiner': new_joiner,
            'stake': stake,
            'moves': {},
            'status': 'waiting',
            'timer': None,
            'start_time': None,
            'creator_ready': False,
            'joiner_ready': False,
            'stats': {
                'rounds': 0,
                'creator_wins': 0,
                'joiner_wins': 0,
                'draws': 0
            }
        }
        
        # Update player states
        players[new_creator]['current_match'] = new_match_id
        players[new_joiner]['current_match'] = new_match_id
        
        # Notify both players
        socketio.emit('rematch_started', {
            'match_id': new_match_id,
            'is_creator': True,
            'stake': stake
        }, room=new_creator)
        
        socketio.emit('rematch_started', {
            'match_id': new_match_id,
            'is_creator': False,
            'stake': stake
        }, room=new_joiner)
        
        logger.info(f"Rematch started: {new_match_id} (original: {match_id})")
    except Exception as e:
        logger.exception("Error in rematch_accepted handler")

@socketio.on('rematch_declined')
def on_rematch_declined(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id or match_id not in matches:
            logger.error(f"Invalid session or match ID in rematch_declined: {session_id}, {match_id}")
            return
        
        match = matches[match_id]
        socketio.emit('rematch_declined', {}, room=match_id)
        logger.info(f"Rematch declined for match {match_id} by {session_id}")
    except Exception as e:
        logger.exception("Error in rematch_declined handler")

if __name__ == '__main__':
    socketio.run(app, 
                host='0.0.0.0', 
                port=5000, 
                allow_unsafe_werkzeug=True,  # Allow WebSocket connections
                log_output=True,  # Enable logging
                debug=True)