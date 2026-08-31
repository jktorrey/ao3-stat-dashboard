import time

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "ao3-stat-dashboard/0.1 (personal stats tracker)"
}

REQUEST_DELAY_SECONDS = 2
RETRY_DELAY_SECONDS = 5

CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 15

MAX_ATTEMPTS = 2


def fetch_work_stats(url):
    last_error = None

    for attempt in range(1, MAX_ATTEMPTS + 1):
        time.sleep(REQUEST_DELAY_SECONDS)

        try:
            response = requests.get(
                f"{url}?view_adult=true",
                headers=HEADERS,
                timeout=(
                    CONNECT_TIMEOUT_SECONDS,
                    READ_TIMEOUT_SECONDS,
                ),
            )

            response.raise_for_status()

            return parse_work_stats(response.text)

        except requests.exceptions.Timeout as error:
            last_error = error

            if attempt < MAX_ATTEMPTS:
                print(
                    f"  AO3 timed out. Retrying in "
                    f"{RETRY_DELAY_SECONDS} seconds..."
                )
                time.sleep(RETRY_DELAY_SECONDS)

        except requests.exceptions.RequestException as error:
            raise RuntimeError(
                f"AO3 request failed for {url}: {error}"
            ) from error

    raise RuntimeError(
        f"AO3 timed out while fetching {url} "
        f"after {MAX_ATTEMPTS} attempts"
    ) from last_error


def parse_work_stats(html):
    soup = BeautifulSoup(html, "html.parser")

    stats = {
        "hits": 0,
        "kudos": 0,
        "comments": 0,
        "public_bookmarks": 0,
    }

    fields = {
        "hits": "hits",
        "kudos": "kudos",
        "comments": "comments",
        "bookmarks": "public_bookmarks",
        "words": "word_count",
    }

    for ao3_class, field_name in fields.items():
        element = soup.select_one(f"dd.{ao3_class}")

        if element:
            value = element.get_text(
                strip=True
            ).replace(",", "")

            stats[field_name] = int(value)

    chapters = soup.select_one("dd.chapters")

    if chapters:
        chapter_text = chapters.get_text(strip=True)
        published, total = chapter_text.split("/")

        stats["chapters_published"] = int(published)

        if total != "?":
            stats["chapters_total"] = int(total)
        else:
            stats["chapters_total"] = None

    return stats