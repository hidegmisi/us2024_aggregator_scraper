import logging
import json
import base64
import os
from turtle import update
import numpy as np
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import pickle
import pandas as pd
import pytz
from datetime import datetime

# Load configuration from config.json
with open('config.json', 'r') as f:
    CONFIG = json.load(f)

# Set up logging
logging.basicConfig(level=CONFIG['logging']['level'],
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

# Function to get current Hungarian time
def get_hungarian_time(date: pd.Timestamp = None) -> pd.Timestamp:
    hungary_tz = pytz.timezone('Europe/Budapest')
    if date:
        return date.tz_convert(hungary_tz)
    else:
        return datetime.now(hungary_tz)

# Context manager for Selenium WebDriver
class WebDriverContext:
    def __init__(self):
        self.driver = None
    
    def __enter__(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        self.driver = webdriver.Chrome(options=options)
        return self.driver
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.driver:
            self.driver.quit()

# Centralized error handling
def handle_error(e):
    logging.error(f"An error occurred: {e}")

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
    try:
        encoded_cookies = os.getenv(f"{cookies}")
        if not encoded_cookies:
            raise ValueError(f"{cookies} environment variable not set.")
        
        cookies = base64.b64decode(encoded_cookies)
        cookies = pickle.loads(cookies)

        for cookie in cookies:
            driver.add_cookie(cookie)
    except Exception as e:
        handle_error(e)

def convert_to_float_dict(data):
    return { item.split()[0]: round(float(item.split()[1].replace('%', '')) / 100, 3) for item in data }

def scrape_fivethirtyeight(url):
    try:
        with WebDriverContext() as driver:
            driver.get(url)

            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".label-group")))
            date_el = driver.find_element(By.CSS_SELECTOR, ".hover-date-fg")
            update_date = " ".join(date_el.text.strip().split(' ')[:-1])
            items = driver.find_element(By.CSS_SELECTOR, ".label-group").find_elements(By.TAG_NAME, "text")
            results = [item.text for item in items[:2]]
            results = {'date': pd.Timestamp(update_date), 'values': convert_to_float_dict(results)}

            return results if validate_data(results['values']) else None
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
            update_date = '2024/' + tds[1].text.split(' - ')[1]
            results = [f'Harris {tds[4].text}%', f'Trump {tds[5].text}%']
            results = {'date': pd.Timestamp(update_date), 'values': convert_to_float_dict(results)}

            return results if validate_data(results['values']) else None
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
            
            WebDriverWait(driver, 30).until(
                lambda driver:
                    len(driver.find_elements(By.CSS_SELECTOR, "#summaryharris .primary-matchup .g-endlabel-inner .g-value")) == 2 and
                    all([len(item.text.strip()) for item in driver.find_elements(By.CSS_SELECTOR, "#summaryharris .primary-matchup .g-endlabel-inner .g-value")])
            )

            date_el = driver.find_element(By.CSS_SELECTOR, "#summaryharris .timeseries-marker-label")
            update_date = '2024 ' + date_el.text.strip()
            
            items = driver.find_elements(By.CSS_SELECTOR, "#summaryharris .primary-matchup .g-endlabel-inner")
            results = [clean_text(item.text) for item in items]
            results = {'date': pd.Timestamp(update_date), 'values': convert_to_float_dict(results)}

            return results if validate_data(results['values']) else None
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
            
            results = {'date': pd.Timestamp(), 'values': convert_to_float_dict(results)} # This is always up to date
            return results if validate_data(results['values']) else None
    except Exception as e:
        handle_error(e)
        return None
    
def scrape_economist(url):
    try:
        with WebDriverContext() as driver:
            driver.get(url)

            load_cookies(driver, "ECONOMIST_COOKIES_BASE64")
            driver.refresh()
            driver.get(url)

            WebDriverWait(driver, 30).until(
                lambda driver: all([el.text for el in driver.find_elements(By.CSS_SELECTOR, "text.svelte-onujtp.median")])
            )
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, ".headerContent .date")))
            
            date_el = driver.find_element(By.CSS_SELECTOR, ".headerContent .date")
            update_date = date_el.text.strip().replace('Last updated on ', '')

            items = driver.find_elements(By.CSS_SELECTOR, "text.svelte-onujtp.median")
            results = []
            results.append(f'Harris {items[0].text}%')
            results.append(f'Trump {items[1].text}%')
            results = {'date': pd.Timestamp(update_date), 'values': convert_to_float_dict(results)} # This is always up to date

            return results if validate_data(results['values']) else None
    except Exception as e:
        handle_error(e)
        return None
    
def main():
    urls = CONFIG['urls']

    AGGREGATOR_MAP = {
        '538': scrape_fivethirtyeight,
        'RCP': scrape_realclearpolling,
        'NYT': scrape_nyt,
        'NS': scrape_natesilver,
        'Economist': scrape_economist,
    }

    for aggregator, scraper in AGGREGATOR_MAP.items():
        url = urls.get(aggregator)
        error_text = np.nan
        data = None

        try:
            for i in range(10):
                data = scraper(url)
                if data:
                    if i > 0:
                        error_text = f"Success after {i} retries"
                    break
        except Exception as e:
            handle_error(e)
            error_text = f"Failed to scrape {aggregator} after 10 retries"

        if data:
            update_date = data['date']
            for candidate, value in data['values'].items():
                candidate, value
                df = pd.DataFrame({
                    'date': update_date.strftime('%Y-%m-%d'),
                    'aggregator': aggregator,
                    'candidate': candidate,
                    'value': value,
                    'date_added': get_hungarian_time().strftime('%Y-%m-%d %H:%M:%S'),
                    'error': error_text
                }, index=[0])
                df.to_csv('scrape_history.csv', mode='a', header=False, index=False)
        else:
            for candidate in ['Harris', 'Trump']:
                df = pd.DataFrame({
                    'date': update_date.strftime('%Y-%m-%d'),
                    'aggregator': aggregator,
                    'candidate': candidate,
                    'value': np.nan,
                    'date_added': get_hungarian_time().strftime('%Y-%m-%d %H:%M:%S'),
                    'error': error_text
                }, index=[0])
                df.to_csv('scrape_history.csv', mode='a', header=False, index=False)
            logging.warning(f"Failed to scrape data from {aggregator}")

if __name__ == '__main__':
    main()
