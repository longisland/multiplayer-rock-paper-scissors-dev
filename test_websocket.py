import socketio
import time
import requests

# Create two SocketIO clients
sio1 = socketio.Client()
sio2 = socketio.Client()

# Register event handlers
sio1.on('match_started', lambda data: print(f'Player 1: Match started: {data}'))
sio1.on('match_result', lambda data: print(f'Player 1: Match result: {data}'))
sio1.on('rematch_accepted_by_player', lambda data: print(f'Player 1: Rematch accepted by player: {data}'))
sio1.on('rematch_started', lambda data: print(f'Player 1: Rematch started: {data}'))

sio2.on('match_started', lambda data: print(f'Player 2: Match started: {data}'))
sio2.on('match_result', lambda data: print(f'Player 2: Match result: {data}'))
sio2.on('rematch_accepted_by_player', lambda data: print(f'Player 2: Rematch accepted by player: {data}'))
sio2.on('rematch_started', lambda data: print(f'Player 2: Rematch started: {data}'))

# Get session cookies for both players
session1 = requests.Session()
session2 = requests.Session()

# Connect to the server
session1.get('http://165.227.160.131:5000/')
session2.get('http://165.227.160.131:5000/')

# Create a match with player 1
response = session1.post('http://165.227.160.131:5000/api/create_match', json={'stake': 10})
match_id = response.json()['match_id']
print(f'Created match: {match_id}')

# Join the match with player 2
response = session2.post('http://165.227.160.131:5000/api/join_match', json={'match_id': match_id})
print(f'Joined match: {response.json()}')

# Connect both players to WebSocket
sio1.connect('http://165.227.160.131:5000', headers={'Cookie': '; '.join([f'{c.name}={c.value}' for c in session1.cookies])})
sio2.connect('http://165.227.160.131:5000', headers={'Cookie': '; '.join([f'{c.name}={c.value}' for c in session2.cookies])})

# Join match room
sio1.emit('join_match_room', {'match_id': match_id})
sio2.emit('join_match_room', {'match_id': match_id})

# Signal ready
sio1.emit('ready_for_match', {'match_id': match_id})
sio2.emit('ready_for_match', {'match_id': match_id})

# Make moves
time.sleep(1)  # Wait for match to start
response = session1.post('http://165.227.160.131:5000/api/move', json={'move': 'rock'})
print(f'Player 1 move: {response.json()}')
response = session2.post('http://165.227.160.131:5000/api/move', json={'move': 'scissors'})
print(f'Player 2 move: {response.json()}')

# Wait for match result
time.sleep(1)

# Accept rematch with both players
print('Player 1 accepting rematch...')
sio1.emit('rematch_accepted', {'match_id': match_id})
time.sleep(0.5)  # Wait for first player's rematch to be processed
print('Player 2 accepting rematch...')
sio2.emit('rematch_accepted', {'match_id': match_id})

# Wait for rematch to start
time.sleep(2)

# Get current match ID from state
print('Getting current match state...')
response = session1.get('http://165.227.160.131:5000/api/state')
data = response.json()
print(f'Current state: {data}')

if data['current_match']:
    new_match_id = data['current_match']['id']
    print(f'New match ID: {new_match_id}')

    # Join match room
    print('Joining match room...')
    sio1.emit('join_match_room', {'match_id': new_match_id})
    sio2.emit('join_match_room', {'match_id': new_match_id})

    # Signal ready
    print('Signaling ready...')
    sio1.emit('ready_for_match', {'match_id': new_match_id})
    sio2.emit('ready_for_match', {'match_id': new_match_id})

    # Wait for match to start
    time.sleep(1)

    # Make moves in rematch
    print('Making moves in rematch...')
    response = session1.post('http://165.227.160.131:5000/api/move', json={'move': 'paper'})
    print(f'Player 1 rematch move: {response.json()}')
    response = session2.post('http://165.227.160.131:5000/api/move', json={'move': 'rock'})
    print(f'Player 2 rematch move: {response.json()}')

# Wait for match result
time.sleep(1)

# Cleanup
sio1.disconnect()
sio2.disconnect()