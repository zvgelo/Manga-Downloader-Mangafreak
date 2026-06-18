from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Cache the resolved chromedriver path: ChromeDriverManager().install() hits the
# network / disk on every call, which is wasteful when building a browser pool.
_driver_path = None


def _chromedriver_path() -> str:
    global _driver_path
    if _driver_path is None:
        _driver_path = ChromeDriverManager().install()
    return _driver_path


def create_driver(headless=True):
    chrome_options = webdriver.ChromeOptions()
    if headless:
        chrome_options.add_argument('--headless')
    service = Service(_chromedriver_path())
    return webdriver.Chrome(service=service, options=chrome_options)
