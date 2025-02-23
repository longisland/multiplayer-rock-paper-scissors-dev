import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options

def setup_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=chrome_options)

def test_full_game_flow():
    # Start two browser instances for two players
    driver1 = setup_driver()
    driver2 = setup_driver()
    
    try:
        # Get the application URL from environment or use default
        app_url = os.getenv('APP_URL', 'http://localhost:53283')
        
        # Open the game in both browsers
        driver1.get(app_url)
        driver2.get(app_url)
        
        # Wait for the game to load
        wait1 = WebDriverWait(driver1, 10)
        wait2 = WebDriverWait(driver2, 10)
        
        # Test match creation
        create_match_btn = wait1.until(
            EC.element_to_be_clickable((By.ID, 'create-match-btn'))
        )
        create_match_btn.click()
        
        # Set stake amount
        stake_input = wait1.until(
            EC.presence_of_element_located((By.ID, 'stake-amount'))
        )
        stake_input.clear()
        stake_input.send_keys('10')
        
        # Confirm match creation
        confirm_btn = wait1.until(
            EC.element_to_be_clickable((By.ID, 'confirm-stake-btn'))
        )
        confirm_btn.click()
        
        # Wait for match to appear in open matches list
        wait2.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'open-match'))
        )
        
        # Player 2 joins the match
        join_btn = wait2.until(
            EC.element_to_be_clickable((By.CLASS_NAME, 'join-match-btn'))
        )
        join_btn.click()
        
        # Both players ready up
        ready_btn1 = wait1.until(
            EC.element_to_be_clickable((By.ID, 'ready-btn'))
        )
        ready_btn2 = wait2.until(
            EC.element_to_be_clickable((By.ID, 'ready-btn'))
        )
        ready_btn1.click()
        ready_btn2.click()
        
        # Make moves
        rock_btn1 = wait1.until(
            EC.element_to_be_clickable((By.ID, 'rock-btn'))
        )
        scissors_btn2 = wait2.until(
            EC.element_to_be_clickable((By.ID, 'scissors-btn'))
        )
        rock_btn1.click()
        scissors_btn2.click()
        
        # Wait for result
        wait1.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'match-result'))
        )
        wait2.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'match-result'))
        )
        
        # Test rematch
        rematch_btn1 = wait1.until(
            EC.element_to_be_clickable((By.ID, 'rematch-btn'))
        )
        rematch_btn2 = wait2.until(
            EC.element_to_be_clickable((By.ID, 'rematch-btn'))
        )
        rematch_btn1.click()
        rematch_btn2.click()
        
        # Verify rematch started
        wait1.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'game-controls'))
        )
        wait2.until(
            EC.presence_of_element_located((By.CLASS_NAME, 'game-controls'))
        )
        
        print("UI automation test completed successfully!")
        
    finally:
        driver1.quit()
        driver2.quit()

if __name__ == '__main__':
    test_full_game_flow()