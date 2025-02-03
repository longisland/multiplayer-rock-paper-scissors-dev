import sys
import os
import time
import random
import requests
import socketio
from threading import Thread, Event

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestPlayer:
    def __init__(self, port):
        self.base_url = f'http://localhost:{port}'
        self.sio = socketio.Client()
        self.session = requests.Session()
        self.match_started = Event()
        self.match_result = Event()
        self.match_id = None
        self.is_creator = False
        self.result_data = None
        self.setup_socket_handlers()

    def setup_socket_handlers(self):
        @self.sio.on('match_started')
        def on_match_started(data):
            self.match_id = data['match_id']
            self.match_started.set()

        @self.sio.on('match_result')
        def on_match_result(data):
            self.result_data = data
            self.match_result.set()

    def connect(self):
        self.sio.connect(self.base_url)
        # Get initial state to establish session
        self.session.get(f'{self.base_url}/api/state')

    def disconnect(self):
        self.sio.disconnect()
        self.session.close()

    def create_match(self, stake):
        response = self.session.post(f'{self.base_url}/api/create_match', json={'stake': stake})
        if response.ok:
            self.match_id = response.json()['match_id']
            self.is_creator = True
            self.sio.emit('join_match_room', {'match_id': self.match_id})
            self.sio.emit('ready_for_match', {'match_id': self.match_id})
            return True
        return False

    def join_match(self, match_id):
        response = self.session.post(f'{self.base_url}/api/join_match', json={'match_id': match_id})
        if response.ok:
            self.match_id = match_id
            self.is_creator = False
            self.sio.emit('join_match_room', {'match_id': match_id})
            self.sio.emit('ready_for_match', {'match_id': match_id})
            return True
        return False

    def make_move(self, move):
        response = self.session.post(f'{self.base_url}/api/move', json={'move': move})
        return response.ok

    def get_state(self):
        response = self.session.get(f'{self.base_url}/api/state')
        if response.ok:
            return response.json()
        return None

    def accept_rematch(self):
        self.match_started.clear()
        self.match_result.clear()
        self.sio.emit('rematch_accepted', {'match_id': self.match_id})

def run_test(port):
    print("Starting test...")
    
    # Create two players
    player1 = TestPlayer(port)
    player2 = TestPlayer(port)

    try:
        # Connect players
        player1.connect()
        player2.connect()

        # Get initial states
        state1 = player1.get_state()
        state2 = player2.get_state()
        print(f"Initial coins - Player1: {state1['coins']}, Player2: {state2['coins']}")

        # Create and join match
        stake = 10
        player1.create_match(stake)
        time.sleep(1)  # Wait for match to be created
        
        state2 = player2.get_state()
        match_id = state2['open_matches'][0]['id']
        player2.join_match(match_id)

        # Wait for match to start
        player1.match_started.wait(timeout=5)
        player2.match_started.wait(timeout=5)
        print("Match started")

        # Make moves
        player1.make_move('rock')
        player2.make_move('scissors')

        # Wait for result
        player1.match_result.wait(timeout=5)
        player2.match_result.wait(timeout=5)
        print("First match completed")

        # Check results
        state1 = player1.get_state()
        state2 = player2.get_state()
        print(f"After first match - Player1: {state1['coins']}, Player2: {state2['coins']}")

        # Test rematch
        player1.accept_rematch()
        player2.accept_rematch()

        # Wait for rematch to start
        player1.match_started.wait(timeout=5)
        player2.match_started.wait(timeout=5)
        print("Rematch started")

        # Make moves in rematch
        player1.make_move('paper')
        player2.make_move('rock')

        # Wait for result
        player1.match_result.wait(timeout=5)
        player2.match_result.wait(timeout=5)
        print("Rematch completed")

        # Check final results
        state1 = player1.get_state()
        state2 = player2.get_state()
        print(f"Final coins - Player1: {state1['coins']}, Player2: {state2['coins']}")

        # Test stats
        print(f"Player1 stats: {state1['stats']}")
        print(f"Player2 stats: {state2['stats']}")

        return True

    except Exception as e:
        print(f"Test failed: {e}")
        return False

    finally:
        # Cleanup
        player1.disconnect()
        player2.disconnect()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python test_match_betting.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    success = run_test(port)
    sys.exit(0 if success else 1)