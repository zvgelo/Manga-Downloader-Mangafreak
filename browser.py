from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


def create_driver(headless=True):
    chrome_options = webdriver.ChromeOptions()
    if headless:
        chrome_options.add_argument('--headless')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)
