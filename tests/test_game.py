import unittest
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO)

class RPSGameTest(unittest.TestCase):
    BASE_URL = "http://165.227.160.131:3001"
    
    @classmethod
    def setUpClass(cls):
        chrome_options = Options()
        chrome_options.add_argument('--headless=new')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--remote-debugging-port=9222')
        
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
        
    def log_page_source(self, driver, name):
        logging.info(f"Page source for {name}:")
        logging.info(driver.page_source)

    def test_01_auto_registration(self):
        """Test that players are automatically registered and get a session"""
        logging.info("Starting test_01_auto_registration")
        
        try:
            # Check if both players get unique balances
            logging.info("Waiting for player 1 balance")
            player1_balance = self.wait1.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), '🪙')]/following-sibling::div"))).text
            logging.info(f"Player 1 balance: {player1_balance}")
            
            logging.info("Waiting for player 2 balance")
            player2_balance = self.wait2.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), '🪙')]/following-sibling::div"))).text
            logging.info(f"Player 2 balance: {player2_balance}")
            
            self.assertEqual(player1_balance, "100")
            self.assertEqual(player2_balance, "100")
        except:
            self.log_page_source(self.driver1, "Player 1")
            self.log_page_source(self.driver2, "Player 2")
            raise

    def test_02_create_and_cancel_match(self):
        """Test match creation and cancellation"""
        # Player 1 creates a match
        create_button = self.wait1.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'CREATE MATCH')]")))
        create_button.click()
        
        # Verify player 1 is in waiting state
        self.wait1.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Looking for worthy opponents')]")))
        
        # Verify match appears in player 2's list
        open_matches = self.wait2.until(EC.presence_of_element_located((By.XPATH, "//h2[text()='Open Matches']/following-sibling::div")))
        self.assertTrue(len(open_matches.find_elements(By.TAG_NAME, "button")) > 0)
        
        # Player 1 cancels the match by going back to lobby
        back_button = self.wait1.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Back to Lobby')]")))
        back_button.click()
        
        # Verify match disappears from player 2's list
        time.sleep(2)  # Wait for update
        open_matches = self.driver2.find_element(By.XPATH, "//h2[text()='Open Matches']/following-sibling::div")
        self.assertEqual(len(open_matches.find_elements(By.TAG_NAME, "button")), 0)

    def test_03_match_visibility(self):
        """Test that matches are properly visible/hidden"""
        # Player 1 creates a match
        create_button = self.wait1.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'CREATE MATCH')]")))
        create_button.click()
        
        # Verify player 1 is in waiting state and doesn't see their own match
        self.wait1.until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Looking for worthy opponents')]")))
        
        # Player 2 should see the match
        player2_matches = self.wait2.until(EC.presence_of_element_located((By.XPATH, "//h2[text()='Open Matches']/following-sibling::div")))
        self.assertTrue(len(player2_matches.find_elements(By.TAG_NAME, "button")) > 0)

    def test_04_play_full_match(self):
        """Test playing a full match including rematch"""
        # Player 1 creates a match
        create_button = self.wait1.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'CREATE MATCH')]")))
        create_button.click()
        
        # Player 2 joins the match
        join_button = self.wait2.until(EC.element_to_be_clickable((By.XPATH, "//h2[text()='Open Matches']/following-sibling::div//button")))
        join_button.click()
        
        # Both players make their choices
        choice1 = self.wait1.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Rock')]")))
        choice2 = self.wait2.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Paper')]")))
        
        choice1.click()
        choice2.click()
        
        # Wait for result
        self.wait1.until(EC.presence_of_element_located((By.XPATH, "//h2[text()='Match Result']")))
        self.wait2.until(EC.presence_of_element_located((By.XPATH, "//h2[text()='Match Result']")))
        
        # Test rematch functionality
        rematch_button = self.wait1.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Rematch')]")))
        rematch_button.click()
        
        # Wait for rematch confirmation from player 2
        rematch_button2 = self.wait2.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Rematch')]")))
        rematch_button2.click()
        
        # Verify both players are back in game state
        self.wait1.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Rock')]")))
        self.wait2.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Rock')]")))

    def test_05_match_auto_cancel(self):
        """Test that match is cancelled when creator leaves"""
        # Player 1 creates a match
        create_button = self.wait1.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'CREATE MATCH')]")))
        create_button.click()
        
        # Verify match appears for player 2
        player2_matches = self.wait2.until(EC.presence_of_element_located((By.XPATH, "//h2[text()='Open Matches']/following-sibling::div")))
        self.assertTrue(len(player2_matches.find_elements(By.TAG_NAME, "button")) > 0)
        
        # Simulate player 1 leaving
        self.driver1.get("about:blank")
        
        # Verify match disappears for player 2
        time.sleep(2)  # Wait for server to process disconnect
        player2_matches = self.driver2.find_element(By.XPATH, "//h2[text()='Open Matches']/following-sibling::div")
        self.assertEqual(len(player2_matches.find_elements(By.TAG_NAME, "button")), 0)

if __name__ == '__main__':
    unittest.main()