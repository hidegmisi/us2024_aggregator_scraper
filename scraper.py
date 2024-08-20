import logging
import json
import os
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
import pickle
import pandas as pd
import subprocess

# Load configuration from config.json
with open('config.json', 'r') as f:
    CONFIG = json.load(f)

# Set up logging
logging.basicConfig(level=CONFIG['logging']['level'],
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler(CONFIG['logging']['file']), logging.StreamHandler()])

# Context manager for Selenium WebDriver
class WebDriverContext:
    def __init__(self):
        self.driver = None
    
    def __enter__(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        self.driver = webdriver.Chrome(options=options)
        return self.driver
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()

# Centralized error handling
def handle_error(e):
    error_message = logging.error(f"An error occurred: {e}")
    print(error_message)

# Data validation function
def validate_data(data):
    for value in data.values():
        try:
            if type(value) not in [int, float]:
                raise ValueError(f"Invalid data type: {type(value)}")
            
            if not 0 <= value <= 1:
                raise ValueError(f"Invalid percentage value: {value}")
        except ValueError as e:
            logging.warning(f"Validation error: {e}")
            return False
    return True

def load_cookies(driver, cookies):
    for cookie in cookies:
        driver.add_cookie(cookie)

def convert_to_float_dict(data):
    return { item.split()[0]: round(float(item.split()[1].replace('%', '')) / 100, 3) for item in data }

def scrape_fivethirtyeight(url):
    try:
        with WebDriverContext() as driver:
            driver.get(url)

            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".label-group")))
            items = driver.find_element(By.CSS_SELECTOR, ".label-group").find_elements(By.TAG_NAME, "text")
            results = [item.text for item in items[:2]]
            results = convert_to_float_dict(results)

            return results if validate_data(results) else None
    except Exception as e:
        handle_error(e)
        return None

def scrape_realclearpolling(url):
    try:
        with WebDriverContext() as driver:
            driver.get(url)
            
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "table")) and
                (lambda d: len(d.find_elements(By.TAG_NAME, "td")) > 5)
            )
            tds = driver.find_elements(By.TAG_NAME, "td")
            results = [f'Harris {tds[4].text}%', f'Trump {tds[5].text}%']
            results = convert_to_float_dict(results)

            return results if validate_data(results) else None
    except Exception as e:
        handle_error(e)
        return None

def scrape_nyt(url):
    def clean_text(text):
        parts = text.split('\n')
        return " ".join([parts[1], parts[0]])
    
    try:
        with WebDriverContext() as driver:
            driver.get(url)

            with open('nyt_cookies.pkl', "rb") as f:
                cookies = pickle.load(f)

            load_cookies(driver, cookies)
            driver.refresh()
            driver.get(url)

            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#summaryharris .multi-buttons")))

            actions = ActionChains(driver)
            button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#summaryharris .multi-buttons button:nth-child(2)")))
            
            actions.move_to_element(button)
            actions.click()
            actions.perform()
            
            WebDriverWait(driver, 30).until(
                lambda driver:
                    len(driver.find_elements(By.CSS_SELECTOR, "#summaryharris .primary-matchup .g-endlabel-inner .g-value")) == 3 and
                    all([len(item.text.strip()) for item in driver.find_elements(By.CSS_SELECTOR, "#summaryharris .primary-matchup .g-endlabel-inner .g-value")])
            )
            
            items = driver.find_elements(By.CSS_SELECTOR, "#summaryharris .primary-matchup .g-endlabel-inner")
            results = [clean_text(item.text) for item in items if 'Kennedy' not in item.text]
            results = convert_to_float_dict(results)

            return results if validate_data(results) else None
    except Exception as e:
        handle_error(e)
        return None
    
def scrape_natesilver(url = "https://www.natesilver.net/p/nate-silver-2024-president-election-polls-model"):
    try:
        with WebDriverContext() as driver:
            driver.get(url)
            
            driver.switch_to.frame(driver.find_element(By.CSS_SELECTOR, "#iframe-datawrapper"))
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".d3l-line-labels")))
            items = driver.find_element(By.CSS_SELECTOR, ".d3l-line-labels").find_elements(By.CSS_SELECTOR, ".d3l-line-label")
            results = []
            for item in items:
                if "Kennedy" in item.text:
                    continue
                clean_text = item.text.split(' ')[-1].replace("\n", " ")
                results.append(clean_text)
            
            results = convert_to_float_dict(results)
            return results if validate_data(results) else None
    except Exception as e:
        handle_error(e)
        return None
    
def main():
    urls = CONFIG['urls']

    AGGREGATOR_MAP = {
        'fivethirtyeight': scrape_fivethirtyeight,
        'realclearpolling': scrape_realclearpolling,
        'nyt': scrape_nyt,
        'natesilver': scrape_natesilver,
    }

    averages = {}
    for aggregator, scraper in AGGREGATOR_MAP.items():
        url = urls.get(aggregator)
        data = scraper(url)
        if data:
            averages[aggregator] = data
        else:
            logging.warning(f"Failed to scrape data from {aggregator}")

    df = pd.DataFrame(averages)

    df['date'] = pd.Timestamp.now().strftime('%Y-%m-%d')
    df['candidate'] = df.index
    df = df.set_index('date')
    df = df[['candidate', 'fivethirtyeight', 'realclearpolling', 'nyt', 'natesilver']]
    df['created_time'] = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    df.to_csv('polls.csv', mode='a', header=False)

if __name__ == '__main__':
    main()
