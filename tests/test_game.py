import unittest
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

class RPSGameTest(unittest.TestCase):
    BASE_URL = "http://165.227.160.131:3001"
    
    @classmethod
    def setUpClass(cls):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        cls.driver1 = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        cls.driver2 = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        
        cls.wait1 = WebDriverWait(cls.driver1, 10)
        cls.wait2 = WebDriverWait(cls.driver2, 10)

    @classmethod
    def tearDownClass(cls):
        cls.driver1.quit()
        cls.driver2.quit()

    def setUp(self):
        self.driver1.get(self.BASE_URL)
        self.driver2.get(self.BASE_URL)
        time.sleep(2)  # Allow for initial load

    def test_01_auto_registration(self):
        """Test that players are automatically registered and get a session"""
        # Check if both players get unique IDs
        player1_id = self.wait1.until(EC.presence_of_element_located((By.ID, "player-id"))).text
        player2_id = self.wait2.until(EC.presence_of_element_located((By.ID, "player-id"))).text
        
        self.assertNotEqual(player1_id, player2_id)
        self.assertTrue(player1_id.startswith("Player"))
        self.assertTrue(player2_id.startswith("Player"))

    def test_02_create_and_cancel_match(self):
        """Test match creation and cancellation"""
        # Player 1 creates a match
        create_button = self.wait1.until(EC.element_to_be_clickable((By.ID, "create-game")))
        create_button.click()
        
        # Verify player 1 is in waiting state
        self.wait1.until(EC.presence_of_element_located((By.ID, "waiting-message")))
        
        # Verify match appears in player 2's list
        open_matches = self.wait2.until(EC.presence_of_element_located((By.ID, "open-matches")))
        self.assertIn("Join", open_matches.text)
        
        # Player 1 cancels the match
        cancel_button = self.wait1.until(EC.element_to_be_clickable((By.ID, "cancel-game")))
        cancel_button.click()
        
        # Verify match disappears from player 2's list
        time.sleep(2)  # Wait for update
        open_matches = self.driver2.find_element(By.ID, "open-matches")
        self.assertNotIn("Join", open_matches.text)

    def test_03_match_visibility(self):
        """Test that matches are properly visible/hidden"""
        # Player 1 creates a match
        create_button = self.wait1.until(EC.element_to_be_clickable((By.ID, "create-game")))
        create_button.click()
        
        # Verify player 1 doesn't see their own match
        player1_matches = self.wait1.until(EC.presence_of_element_located((By.ID, "open-matches")))
        self.assertNotIn("Join", player1_matches.text)
        
        # Player 2 should see the match
        player2_matches = self.wait2.until(EC.presence_of_element_located((By.ID, "open-matches")))
        self.assertIn("Join", player2_matches.text)

    def test_04_play_full_match(self):
        """Test playing a full match including rematch"""
        # Player 1 creates a match
        create_button = self.wait1.until(EC.element_to_be_clickable((By.ID, "create-game")))
        create_button.click()
        
        # Player 2 joins the match
        join_button = self.wait2.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".join-game")))
        join_button.click()
        
        # Both players make their choices
        choice1 = self.wait1.until(EC.element_to_be_clickable((By.ID, "rock")))
        choice2 = self.wait2.until(EC.element_to_be_clickable((By.ID, "paper")))
        
        choice1.click()
        choice2.click()
        
        # Wait for result
        self.wait1.until(EC.presence_of_element_located((By.CLASS_NAME, "game-result")))
        self.wait2.until(EC.presence_of_element_located((By.CLASS_NAME, "game-result")))
        
        # Test rematch functionality
        rematch_button = self.wait1.until(EC.element_to_be_clickable((By.ID, "rematch")))
        rematch_button.click()
        
        # Wait for rematch confirmation from player 2
        rematch_button2 = self.wait2.until(EC.element_to_be_clickable((By.ID, "rematch")))
        rematch_button2.click()
        
        # Verify both players are back in game state
        self.wait1.until(EC.presence_of_element_located((By.ID, "rock")))
        self.wait2.until(EC.presence_of_element_located((By.ID, "rock")))

    def test_05_match_auto_cancel(self):
        """Test that match is cancelled when creator leaves"""
        # Player 1 creates a match
        create_button = self.wait1.until(EC.element_to_be_clickable((By.ID, "create-game")))
        create_button.click()
        
        # Verify match appears for player 2
        player2_matches = self.wait2.until(EC.presence_of_element_located((By.ID, "open-matches")))
        self.assertIn("Join", player2_matches.text)
        
        # Simulate player 1 leaving
        self.driver1.get("about:blank")
        
        # Verify match disappears for player 2
        time.sleep(2)  # Wait for server to process disconnect
        player2_matches = self.driver2.find_element(By.ID, "open-matches")
        self.assertNotIn("Join", player2_matches.text)

if __name__ == '__main__':
    unittest.main()