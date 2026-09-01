import time
from datetime import date
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
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    stats = {
        "hits": 0,
        "kudos": 0,
        "comments": 0,
        "public_bookmarks": 0,
        "word_count": None,
        "chapters_published": None,
        "chapters_total": None,

        "published_date": None,
        "updated_date": None,
        "completed_date": None,
    }

    def parse_integer(selector):
        element = soup.select_one(
            selector
        )

        if element is None:
            return None

        text = (
            element.get_text(
                strip=True
            )
            .replace(",", "")
        )

        try:
            return int(text)

        except ValueError:
            return None

    hits = parse_integer("dd.hits")

    if hits is not None:
        stats["hits"] = hits

    kudos = parse_integer("dd.kudos")

    if kudos is not None:
        stats["kudos"] = kudos

    comments = parse_integer(
        "dd.comments"
    )

    if comments is not None:
        stats["comments"] = comments

    bookmarks = parse_integer(
        "dd.bookmarks"
    )

    if bookmarks is not None:
        stats["public_bookmarks"] = (
            bookmarks
        )

    stats["word_count"] = (
        parse_integer("dd.words")
    )

    chapters = soup.select_one(
        "dd.chapters"
    )

    if chapters is not None:
        chapter_text = chapters.get_text(
            strip=True
        )

        if "/" in chapter_text:
            published, total = (
                chapter_text.split(
                    "/",
                    1,
                )
            )

            try:
                stats[
                    "chapters_published"
                ] = int(
                    published.strip()
                )

            except ValueError:
                stats[
                    "chapters_published"
                ] = None

            total = total.strip()

            if total == "?":
                stats[
                    "chapters_total"
                ] = None

            else:
                try:
                    stats[
                        "chapters_total"
                    ] = int(total)

                except ValueError:
                    stats[
                        "chapters_total"
                    ] = None

    published_element = (
        soup.select_one(
            "dd.published"
        )
    )

    if published_element is not None:
        stats["published_date"] = (
            parse_ao3_date(
                published_element.get_text(
                    strip=True
                )
            )
        )

    status_label_element = (
        soup.select_one(
            "dt.status"
        )
    )

    status_date_element = (
        soup.select_one(
            "dd.status"
        )
    )

    if (
        status_label_element
        is not None
        and status_date_element
        is not None
    ):
        status_label = (
            status_label_element
            .get_text(
                " ",
                strip=True,
            )
            .rstrip(":")
            .lower()
        )

        status_date = (
            parse_ao3_date(
                status_date_element
                .get_text(
                    strip=True
                )
            )
        )

        if status_label == "updated":
            stats["updated_date"] = (
                status_date
            )

        elif status_label == "completed":
            stats["completed_date"] = (
                status_date
            )

    return stats


def parse_ao3_date(value):
    if not value:
        return None

    value = value.strip()

    try:
        return date.fromisoformat(
            value
        ).isoformat()

    except ValueError:
        return None