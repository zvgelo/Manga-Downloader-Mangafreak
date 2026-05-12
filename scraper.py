from selenium.webdriver.common.by import By
import time

BASE_URL = "https://ww2.mangafreak.me"


def search_manga(driver, query):
    slug = '%20'.join(query.lower().split())
    driver.get(f"{BASE_URL}/Find/{slug}")
    while True:
        try:
            driver.find_element(By.LINK_TEXT, "Home")
            break
        except Exception:
            continue
    return driver.find_elements(By.CLASS_NAME, "manga_search_item")


def get_manga_title(result_item):
    return result_item.find_element(By.TAG_NAME, "h3").text.strip()


def get_chapters(driver, result_item):
    """Returns list of dicts: [{title, url}] — extracted before any navigation."""
    result_item.find_element(By.TAG_NAME, "a").click()
    series_list = driver.find_element(By.CLASS_NAME, "manga_series_list")
    rows = series_list.find_elements(By.TAG_NAME, "tr")[1:]  # skip header
    chapters = []
    for row in rows:
        tds = row.find_elements(By.TAG_NAME, "td")
        if not tds:
            continue
        a = tds[0].find_element(By.TAG_NAME, "a")
        chapters.append({"title": tds[0].text.strip(), "url": a.get_attribute("href")})
    return chapters


def get_chapter_images(driver, chapter):
    """chapter is a dict with 'title' and 'url'."""
    driver.get(chapter["url"])
    time.sleep(3)

    seen = set()
    image_urls = []
    for img in driver.find_elements(By.TAG_NAME, "img"):
        src = img.get_attribute("src") or ""
        if "mangafreak.me/mangas" in src and src not in seen:
            seen.add(src)
            image_urls.append(src)

    return image_urls
