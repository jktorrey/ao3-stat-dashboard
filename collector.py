import time
from datetime import date
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin


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



def parse_chapter_metadata(
    html,
    ao3_work_id,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    chapter_pattern = re.compile(
        rf"^/works/{ao3_work_id}/chapters/\d+$"
    )

    chapter_links = soup.find_all(
        "a",
        href=chapter_pattern,
    )

    seen_urls = set()
    chapters = []

    for chapter_link in chapter_links:
        chapter_url = chapter_link.get(
            "href"
        )

        if chapter_url in seen_urls:
            continue

        seen_urls.add(chapter_url)

        chapter_match = re.search(
            r"/chapters/(\d+)$",
            chapter_url,
        )

        if chapter_match:
            chapter_id = int(
                chapter_match.group(1)
            )
        else:
            chapter_id = None

        title = chapter_link.get_text(
            " ",
            strip=True,
        )

        title = re.sub(
            r"^\d+\.\s*",
            "",
            title,
        )

        container = (
            chapter_link.find_parent("li")
        )

        date_element = None

        if container is not None:
            date_element = (
                container.select_one(
                    "span.datetime"
                )
            )

        published_date = None

        if date_element is not None:
            raw_date = (
                date_element.get_text(
                    " ",
                    strip=True,
                )
                .strip("()")
            )

            published_date = (
                parse_ao3_date(
                    raw_date
                )
            )

        chapters.append({
            "chapter_number":
                len(chapters) + 1,
            "chapter_id":
                chapter_id,
            "title":
                title,
            "published_date":
                published_date,
        })

    return chapters


def fetch_chapter_metadata(
    url,
):
    base_url = (
        url.split("?", 1)[0]
        .rstrip("/")
    )

    work_id_match = re.search(
        r"/works/(\d+)$",
        base_url,
    )

    if work_id_match is None:
        raise ValueError(
            f"Could not determine AO3 work ID "
            f"from URL: {url}"
        )

    ao3_work_id = (
        work_id_match.group(1)
    )

    navigate_url = (
        f"{base_url}/navigate"
        f"?view_adult=true"
    )

    for attempt in range(
        1,
        MAX_ATTEMPTS + 1,
    ):
        time.sleep(
            REQUEST_DELAY_SECONDS
        )

        try:
            response = requests.get(
                navigate_url,
                headers=HEADERS,
                timeout=(
                    CONNECT_TIMEOUT_SECONDS,
                    READ_TIMEOUT_SECONDS,
                ),
            )

            response.raise_for_status()

            return parse_chapter_metadata(
                response.text,
                ao3_work_id,
            )

        except requests.Timeout:
            if attempt < MAX_ATTEMPTS:
                time.sleep(
                    RETRY_DELAY_SECONDS
                )
                continue

            raise RuntimeError(
                f"AO3 timed out while fetching "
                f"chapter metadata for "
                f"{base_url}."
            )

        except requests.RequestException as error:
            raise RuntimeError(
                f"Could not fetch AO3 chapter "
                f"metadata for {base_url}: "
                f"{error}"
            )


def parse_user_works_page(html):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    works = []

    for work_blurb in soup.select(
        "li.work.blurb"
    ):
        work_link = work_blurb.select_one(
            'h4.heading a[href^="/works/"]'
        )

        if work_link is None:
            continue

        href = work_link.get("href")

        if not href:
            continue

        work_match = re.match(
            r"^/works/(\d+)",
            href,
        )

        if work_match is None:
            continue

        ao3_work_id = int(
            work_match.group(1)
        )

        title = work_link.get_text(
            " ",
            strip=True,
        )

        works.append({
            "ao3_work_id": ao3_work_id,
            "title": title,
            "url": (
                "https://archiveofourown.org"
                f"/works/{ao3_work_id}"
            ),
        })

    next_link = soup.select_one(
        "ol.pagination.actions "
        "li.next a"
    )

    if next_link is None:
        next_link = soup.select_one(
            'a[rel="next"]'
        )

    if next_link is not None:
        next_page = next_link.get(
            "href"
        )
    else:
        next_page = None

    return works, next_page

def fetch_user_works(username):
    search_url = (
        "https://archiveofourown.org"
        "/works/search"
    )

    search_params = {
        "work_search[creators]": username,
        "work_search[sort_column]":
            "revised_at",
        "work_search[sort_direction]":
            "desc",
    }

    next_url = search_url

    all_works = []
    seen_work_ids = set()
    seen_pages = set()

    discovery_connect_timeout = 15
    discovery_read_timeout = 60
    discovery_max_attempts = 3

    page_number = 1
    first_page = True

    while next_url:
        response = None

        for attempt in range(
            1,
            discovery_max_attempts + 1,
        ):
            print(
                f"  Fetching search page "
                f"{page_number} "
                f"(attempt {attempt}/"
                f"{discovery_max_attempts})..."
            )

            time.sleep(
                REQUEST_DELAY_SECONDS
            )

            try:
                if first_page:
                    response = requests.get(
                        next_url,
                        params=search_params,
                        headers=HEADERS,
                        timeout=(
                            discovery_connect_timeout,
                            discovery_read_timeout,
                        ),
                    )

                else:
                    response = requests.get(
                        next_url,
                        headers=HEADERS,
                        timeout=(
                            discovery_connect_timeout,
                            discovery_read_timeout,
                        ),
                    )

                if (
                    500
                    <= response.status_code
                    <= 599
                ):
                    print(
                        "  AO3 returned server "
                        f"error "
                        f"{response.status_code}."
                    )

                    if (
                        attempt
                        < discovery_max_attempts
                    ):
                        print(
                            "  Treating it as "
                            "temporary and retrying..."
                        )

                        time.sleep(
                            RETRY_DELAY_SECONDS
                        )

                        continue

                    raise RuntimeError(
                        "AO3 returned server "
                        f"error "
                        f"{response.status_code} "
                        "on every attempt."
                    )

                if response.status_code == 429:
                    print(
                        "  AO3 asked us to "
                        "slow down."
                    )

                    if (
                        attempt
                        < discovery_max_attempts
                    ):
                        time.sleep(
                            RETRY_DELAY_SECONDS
                            * 2
                        )

                        continue

                    raise RuntimeError(
                        "AO3 rate-limited the "
                        "discovery request."
                    )

                response.raise_for_status()

                break

            except requests.Timeout:
                if (
                    attempt
                    < discovery_max_attempts
                ):
                    print(
                        "  AO3 timed out; "
                        "retrying..."
                    )

                    time.sleep(
                        RETRY_DELAY_SECONDS
                    )

                    continue

                raise RuntimeError(
                    "AO3 timed out while "
                    "searching for the user's "
                    "works."
                )

            except requests.RequestException as error:
                raise RuntimeError(
                    "Could not search AO3 "
                    f"works: {error}"
                )

        first_page = False

        actual_url = response.url

        if actual_url in seen_pages:
            raise RuntimeError(
                "AO3 pagination loop detected."
            )

        seen_pages.add(actual_url)

        print(
            f"  Search page {page_number} "
            f"received."
        )

        page_works, next_page = (
            parse_user_works_page(
                response.text
            )
        )

        print(
            f"  Works found on page "
            f"{page_number}: "
            f"{len(page_works)}"
        )

        for work in page_works:
            ao3_work_id = work[
                "ao3_work_id"
            ]

            if ao3_work_id in seen_work_ids:
                continue

            seen_work_ids.add(
                ao3_work_id
            )

            all_works.append(work)

        if next_page:
            next_url = urljoin(
                response.url,
                next_page,
            )

            page_number += 1

        else:
            next_url = None

    return all_works