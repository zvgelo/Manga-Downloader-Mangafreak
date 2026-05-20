import config
from selenium.webdriver.common.by import By
import time


def search_manga(driver, query):
    slug = '%20'.join(query.lower().split())
    driver.get(f"{config.MANGA_BASE_URL}/Find/{slug}")
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
    driver.find_element(By.CLASS_NAME, "manga_series_list")  # wait for page load
    return driver.execute_script("""
        const rows = document.querySelector('.manga_series_list').querySelectorAll('tr');
        const result = [];
        for (let i = 1; i < rows.length; i++) {
            const td = rows[i].querySelector('td');
            const a = td && td.querySelector('a');
            if (a) result.push({title: td.textContent.trim(), url: a.href});
        }
        return result;
    """)


def get_chapter_images(driver, chapter):
    """chapter is a dict with 'title' and 'url'."""
    driver.get(chapter["url"])
    time.sleep(config.PAGE_LOAD_WAIT)

    seen = set()
    image_urls = []
    for img in driver.find_elements(By.TAG_NAME, "img"):
        src = img.get_attribute("src") or ""
        if "mangafreak.me/mangas" in src and src not in seen:
            seen.add(src)
            image_urls.append(src)

    return image_urls
