# Testing Guide

This guide explains how to run and write tests for the Rock Paper Scissors game.

## Running Tests

### Prerequisites
- Python 3.8+
- pytest and dependencies (installed via requirements.txt)

### Running All Tests
```bash
# From project root directory
python -m pytest

# With coverage report
python -m pytest --cov=src

# With detailed output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_game_mechanics.py

# Run specific test case
python -m pytest tests/test_game_mechanics.py::TestGameMechanics::test_rematch_mechanics
```

### Test Coverage Areas

1. Game Mechanics (`test_game_mechanics.py`)
   - Move validation
   - Auto-selection mechanics
   - Match timer handling
   - Rematch functionality
   - Game result calculation

2. Betting Model (`test_betting_model.py`)
   - Stake validation
   - Win reward distribution
   - Draw stake return
   - Rematch stake handling
   - Disconnection stake return

3. Matchmaking (`test_matchmaking.py`)
   - Match creation validation
   - Match joining validation
   - Match cleanup
   - Match timeout handling

4. Game Logic (`test_game_logic.py`)
   - Auto-selection result calculation
   - Draw result handling
   - Match creation stake deduction
   - Match joining stake deduction

## Writing New Tests

### Test Structure
```python
import unittest
from unittest.mock import patch, MagicMock
from src.services.game_service import GameService
from src.services.match_service import MatchService
from src.models.match import Match
from src.models.player import Player
from src.models.database import User, db

class TestNewFeature(unittest.TestCase):
    def setUp(self):
        # Initialize Flask test app
        from flask import Flask
        from src.config import TestConfig
        
        self.app = Flask(__name__)
        self.app.config.from_object(TestConfig)
        db.init_app(self.app)
        
        self.app_context = self.app.app_context()
        self.app_context.push()
        
        db.create_all()
        
        # Initialize services
        self.game_service = GameService()
        self.match_service = MatchService()
        
        # Initialize test data
        self.player1_id = 'test_player1'
        self.player2_id = 'test_player2'
        self.initial_coins = 100
        
        # Create test players
        self.match_service.players[self.player1_id] = Player(self.player1_id, self.initial_coins)
        self.match_service.players[self.player2_id] = Player(self.player2_id, self.initial_coins)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_new_feature(self):
        # Arrange - Set up test data
        match = self.match_service.create_match(self.player1_id, 50)
        
        # Act - Perform the action being tested
        result = self.match_service.some_action(match.id)
        
        # Assert - Verify the results
        self.assertEqual(result.status, 'expected_status')
        self.assertTrue(some_condition)
```

### Test Naming Conventions
- Test files should start with `test_`
- Test classes should start with `Test`
- Test methods should start with `test_`
- Test names should describe what is being tested

### Best Practices
1. Use descriptive test names that explain what is being tested
2. Follow the Arrange-Act-Assert pattern
3. Test both valid and invalid scenarios
4. Test edge cases and boundary conditions
5. Keep tests independent and isolated
6. Clean up test data in tearDown
7. Use meaningful assertions
8. Add comments to explain complex test scenarios

### Common Testing Patterns

1. Testing Exceptions
```python
def test_invalid_stake(self):
    with self.assertRaises(ValueError):
        self.match_service.create_match(self.player1_id, -10)
```

2. Testing State Changes
```python
def test_stake_deduction(self):
    initial_coins = self.match_service.players[self.player1_id].coins
    match = self.match_service.create_match(self.player1_id, 50)
    final_coins = self.match_service.players[self.player1_id].coins
    self.assertEqual(final_coins, initial_coins - 50)
```

3. Testing Asynchronous Operations
```python
def test_match_timeout(self):
    match = self.match_service.create_match(self.player1_id, 50)
    self.match_service.join_match(match.id, self.player2_id)
    match.start_match()
    
    # Wait for timeout
    result_match = self.match_service.handle_match_timeout(match.id)
    self.assertEqual(result_match.status, 'finished')
```

## Continuous Integration

The test suite is automatically run on:
- Pull request creation
- Push to main branch
- Daily scheduled runs

### Test Environment
Tests use a separate test configuration (`TestConfig`) that:
- Uses an in-memory SQLite database
- Disables CSRF protection
- Sets testing mode flags

## Troubleshooting

Common issues and solutions:

1. Database errors
   - Ensure `setUp` creates all required tables
   - Check transaction rollback in `tearDown`
   - Verify test database is clean before each test

2. State leakage between tests
   - Clean up all created objects in `tearDown`
   - Don't rely on global state
   - Reset any modified class variables

3. Timing issues
   - Use appropriate timeouts in async tests
   - Mock time-dependent operations
   - Avoid actual sleeps in tests