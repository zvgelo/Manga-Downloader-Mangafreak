from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time

from logger import get_logger
from models import Chapter, SearchResult
from settings import DEFAULT_SETTINGS

log = get_logger(__name__)


def search_manga(driver, query, settings=DEFAULT_SETTINGS) -> list[SearchResult]:
    """Search and return fully-materialized results (no live WebElements)."""
    slug = '%20'.join(query.lower().split())
    driver.get(f"{settings.manga_base_url}/Find/{slug}")
    WebDriverWait(driver, settings.page_timeout).until(
        EC.presence_of_element_located((By.LINK_TEXT, "Home"))
    )

    results = []
    for item in driver.find_elements(By.CLASS_NAME, "manga_search_item"):
        try:
            series_url = item.find_element(By.TAG_NAME, "a").get_attribute("href")
        except Exception:
            continue  # no link — not a usable result
        if not series_url:
            continue

        try:
            title = item.find_element(By.TAG_NAME, "h3").text.strip()
        except Exception:
            title = ""
        display_lines = [line for line in item.text.splitlines() if line.strip()]
        if not title:
            title = display_lines[0] if display_lines else series_url

        cover_url = ""
        try:
            cover_url = item.find_element(By.TAG_NAME, "img").get_attribute("src") or ""
        except Exception:
            pass

        results.append(SearchResult(
            title=title, series_url=series_url,
            display_lines=display_lines, cover_url=cover_url,
        ))

    return results


def get_chapters(driver, series_url: str, settings=DEFAULT_SETTINGS) -> list[Chapter]:
    """Navigate to a series page and return its chapters in listing order."""
    driver.get(series_url)
    WebDriverWait(driver, settings.page_timeout).until(
        EC.presence_of_element_located((By.CLASS_NAME, "manga_series_list"))
    )
    rows = driver.execute_script("""
        const rows = document.querySelector('.manga_series_list').querySelectorAll('tr');
        const result = [];
        for (let i = 1; i < rows.length; i++) {
            const td = rows[i].querySelector('td');
            const a = td && td.querySelector('a');
            if (a) result.push({title: td.textContent.trim(), url: a.href});
        }
        return result;
    """)
    return [Chapter(title=row["title"], url=row["url"]) for row in rows]


def get_chapter_images(driver, chapter: Chapter, settings=DEFAULT_SETTINGS) -> list[str]:
    driver.get(chapter.url)
    time.sleep(settings.page_load_wait)

    seen = set()
    image_urls = []
    for img in driver.find_elements(By.TAG_NAME, "img"):
        src = img.get_attribute("src") or ""
        if "mangafreak.me/mangas" in src and src not in seen:
            seen.add(src)
            image_urls.append(src)

    return image_urls
