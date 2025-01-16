# Rock Paper Scissors Game Tests

This directory contains automated tests for the Rock Paper Scissors multiplayer game.

## Test Coverage

The tests cover the following functionality:

1. Auto-registration and session management
2. Match creation and cancellation
3. Match visibility rules
4. Full match gameplay including rematch
5. Auto-cancellation of matches when creator leaves

## Requirements

- Python 3.8+
- Chrome browser
- Required Python packages (install using `pip install -r requirements.txt`)

## Running the Tests

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the tests:
   ```bash
   python -m pytest test_game.py -v
   ```

## Test Details

### test_01_auto_registration
Tests that players are automatically registered and receive unique session IDs.

### test_02_create_and_cancel_match
Tests match creation and cancellation functionality.

### test_03_match_visibility
Tests that matches are properly visible/hidden according to game rules.

### test_04_play_full_match
Tests a complete match including the rematch functionality.

### test_05_match_auto_cancel
Tests that matches are automatically cancelled when the creator leaves.