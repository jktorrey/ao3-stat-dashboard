import time
from datetime import date
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "ao3-stat-dashboard/0.1 "
        "(personal stats tracker)"
    )
}

REQUEST_DELAY_SECONDS = 2

CONNECT_TIMEOUT_SECONDS = 10
READ_TIMEOUT_SECONDS = 15

MAX_ATTEMPTS = 2

SSL_ERROR_STATUSES = {
    525,
    526,
}

SSL_CIRCUIT_THRESHOLD = 3

RETRY_DELAYS = {
    408: 30,
    429: 60,
    500: 30,
    502: 60,
    503: 60,
    504: 120,
    520: 60,
    521: 120,
    522: 120,
    523: 120,
    524: 120,
}

RETRYABLE_STATUSES = set(
    RETRY_DELAYS.keys()
)


_consecutive_ssl_failures = 0
_ssl_circuit_open = False


class AO3TransportUnavailable(
    RuntimeError
):
    pass


class AO3CircuitOpen(
    AO3TransportUnavailable
):
    pass


def reset_ao3_transport_state():
    global _consecutive_ssl_failures
    global _ssl_circuit_open

    _consecutive_ssl_failures = 0
    _ssl_circuit_open = False


def record_ssl_failure(
    status_code,
    response,
):
    global _consecutive_ssl_failures
    global _ssl_circuit_open

    _consecutive_ssl_failures += 1

    cf_ray = response.headers.get(
        "CF-Ray"
    )

    if (
        _consecutive_ssl_failures
        >= SSL_CIRCUIT_THRESHOLD
    ):
        _ssl_circuit_open = True

    message = (
        f"AO3 returned HTTP "
        f"{status_code}"
    )

    if cf_ray:
        message += (
            f" (Cloudflare Ray "
            f"{cf_ray})"
        )

    message += (
        ". Cloudflare could not complete "
        "the TLS connection to AO3's "
        "origin server."
    )

    if _ssl_circuit_open:
        message += (
            " The AO3 transport circuit "
            "has been opened after "
            f"{_consecutive_ssl_failures} "
            "consecutive 525/526 responses."
        )

    return message


def reset_ssl_failure_count():
    global _consecutive_ssl_failures

    _consecutive_ssl_failures = 0


def get_retry_delay(
    response,
    status_code,
):
    retry_after = (
        response.headers.get(
            "Retry-After"
        )
    )

    if (
        retry_after
        and retry_after.isdigit()
    ):
        return int(
            retry_after
        )

    return RETRY_DELAYS.get(
        status_code,
        30,
    )


def fetch_ao3_page(
    url,
    params=None,
    connect_timeout=None,
    read_timeout=None,
    max_attempts=None,
):
    if _ssl_circuit_open:
        raise AO3CircuitOpen(
            "AO3 request skipped because "
            "the transport circuit is open "
            "after repeated HTTP 525/526 "
            "responses."
        )

    if connect_timeout is None:
        connect_timeout = (
            CONNECT_TIMEOUT_SECONDS
        )

    if read_timeout is None:
        read_timeout = (
            READ_TIMEOUT_SECONDS
        )

    if max_attempts is None:
        max_attempts = (
            MAX_ATTEMPTS
        )

    last_error = None

    for attempt in range(
        1,
        max_attempts + 1,
    ):
        time.sleep(
            REQUEST_DELAY_SECONDS
        )

        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=(
                    connect_timeout,
                    read_timeout,
                ),
            )

        except (
            requests.Timeout,
            requests.ConnectionError,
        ) as error:
            last_error = error

            if attempt < max_attempts:
                print(
                    "  AO3 connection problem; "
                    "retrying after 30 seconds..."
                )

                time.sleep(30)

                continue

            raise RuntimeError(
                f"AO3 request failed for "
                f"{url}: {error}"
            ) from error

        except requests.RequestException as error:
            raise RuntimeError(
                f"AO3 request failed for "
                f"{url}: {error}"
            ) from error

        status_code = (
            response.status_code
        )

        if (
            status_code
            in SSL_ERROR_STATUSES
        ):
            message = (
                record_ssl_failure(
                    status_code,
                    response,
                )
            )

            response.close()

            # 525/526 are deliberately not
            # retried immediately. Cloudflare
            # categorizes them as origin TLS
            # failures rather than transient
            # HTTP failures.
            raise AO3TransportUnavailable(
                message
            )

        # Any response other than 525/526
        # proves that Cloudflare successfully
        # completed the TLS path to AO3.
        reset_ssl_failure_count()

        if (
            status_code
            in RETRYABLE_STATUSES
        ):
            last_error = (
                f"HTTP {status_code}"
            )

            if attempt < max_attempts:
                retry_delay = (
                    get_retry_delay(
                        response,
                        status_code,
                    )
                )

                print(
                    "  AO3 returned "
                    f"{status_code}; "
                    f"retrying after "
                    f"{retry_delay} seconds..."
                )

                response.close()

                time.sleep(
                    retry_delay
                )

                continue

            response.close()

            raise RuntimeError(
                "AO3 returned "
                f"{status_code} after "
                f"{max_attempts} attempts "
                f"for {url}."
            )

        try:
            response.raise_for_status()

        except requests.RequestException as error:
            response.close()

            raise RuntimeError(
                f"AO3 request failed for "
                f"{url}: {error}"
            ) from error

        return response

    raise RuntimeError(
        f"AO3 request failed for "
        f"{url}: {last_error}"
    )


def fetch_work_stats(url):
    separator = (
        "&"
        if "?" in url
        else "?"
    )

    request_url = (
        f"{url}"
        f"{separator}"
        f"view_adult=true"
    )

    response = fetch_ao3_page(
        request_url
    )

    try:
        return parse_work_stats(
            response.text
        )

    finally:
        response.close()


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

    hits = parse_integer(
        "dd.hits"
    )

    if hits is not None:
        stats["hits"] = hits

    kudos = parse_integer(
        "dd.kudos"
    )

    if kudos is not None:
        stats["kudos"] = kudos

    comments = parse_integer(
        "dd.comments"
    )

    if comments is not None:
        stats["comments"] = (
            comments
        )

    bookmarks = parse_integer(
        "dd.bookmarks"
    )

    if bookmarks is not None:
        stats[
            "public_bookmarks"
        ] = bookmarks

    stats["word_count"] = (
        parse_integer(
            "dd.words"
        )
    )

    chapters = soup.select_one(
        "dd.chapters"
    )

    if chapters is not None:
        chapter_text = (
            chapters.get_text(
                strip=True
            )
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
        stats[
            "published_date"
        ] = parse_ao3_date(
            published_element.get_text(
                strip=True
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

        if (
            status_label
            == "updated"
        ):
            stats[
                "updated_date"
            ] = status_date

        elif (
            status_label
            == "completed"
        ):
            stats[
                "completed_date"
            ] = status_date

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
        rf"^/works/"
        rf"{ao3_work_id}"
        rf"/chapters/\d+$"
    )

    chapter_links = soup.find_all(
        "a",
        href=chapter_pattern,
    )

    seen_urls = set()
    chapters = []

    for chapter_link in chapter_links:
        chapter_url = (
            chapter_link.get(
                "href"
            )
        )

        if chapter_url in seen_urls:
            continue

        seen_urls.add(
            chapter_url
        )

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

        title = (
            chapter_link.get_text(
                " ",
                strip=True,
            )
        )

        title = re.sub(
            r"^\d+\.\s*",
            "",
            title,
        )

        container = (
            chapter_link.find_parent(
                "li"
            )
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
                date_element
                .get_text(
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


def fetch_chapter_metadata(url):
    base_url = (
        url.split(
            "?",
            1,
        )[0]
        .rstrip("/")
    )

    work_id_match = re.search(
        r"/works/(\d+)$",
        base_url,
    )

    if work_id_match is None:
        raise ValueError(
            "Could not determine AO3 "
            f"work ID from URL: {url}"
        )

    ao3_work_id = (
        work_id_match.group(1)
    )

    navigate_url = (
        f"{base_url}"
        f"/navigate"
        f"?view_adult=true"
    )

    response = fetch_ao3_page(
        navigate_url
    )

    try:
        return parse_chapter_metadata(
            response.text,
            ao3_work_id,
        )

    finally:
        response.close()


def parse_user_works_page(html):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    works = []

    for work_blurb in soup.select(
        "li.work.blurb"
    ):
        work_link = (
            work_blurb.select_one(
                'h4.heading '
                'a[href^="/works/"]'
            )
        )

        if work_link is None:
            continue

        href = work_link.get(
            "href"
        )

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

        title = (
            work_link.get_text(
                " ",
                strip=True,
            )
        )

        works.append({
            "ao3_work_id":
                ao3_work_id,
            "title":
                title,
            "url":
                (
                    "https://"
                    "archiveofourown.org"
                    f"/works/"
                    f"{ao3_work_id}"
                ),
        })

    next_link = soup.select_one(
        "ol.pagination.actions "
        "li.next a"
    )

    if next_link is None:
        next_link = (
            soup.select_one(
                'a[rel="next"]'
            )
        )

    if next_link is not None:
        next_page = (
            next_link.get(
                "href"
            )
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
        "work_search[creators]":
            username,
        "work_search[sort_column]":
            "revised_at",
        "work_search[sort_direction]":
            "desc",
    }

    next_url = search_url

    all_works = []
    seen_work_ids = set()
    seen_pages = set()

    page_number = 1
    first_page = True

    while next_url:
        print(
            f"  Fetching search page "
            f"{page_number}..."
        )

        params = (
            search_params
            if first_page
            else None
        )

        response = fetch_ao3_page(
            next_url,
            params=params,
            connect_timeout=15,
            read_timeout=60,
            max_attempts=2,
        )

        first_page = False

        try:
            actual_url = (
                response.url
            )

            if (
                actual_url
                in seen_pages
            ):
                raise RuntimeError(
                    "AO3 pagination "
                    "loop detected."
                )

            seen_pages.add(
                actual_url
            )

            print(
                f"  Search page "
                f"{page_number} received."
            )

            (
                page_works,
                next_page,
            ) = parse_user_works_page(
                response.text
            )

        finally:
            response.close()

        print(
            f"  Works found on page "
            f"{page_number}: "
            f"{len(page_works)}"
        )

        for work in page_works:
            ao3_work_id = (
                work[
                    "ao3_work_id"
                ]
            )

            if (
                ao3_work_id
                in seen_work_ids
            ):
                continue

            seen_work_ids.add(
                ao3_work_id
            )

            all_works.append(
                work
            )

        if next_page:
            next_url = urljoin(
                actual_url,
                next_page,
            )

            page_number += 1

        else:
            next_url = None

    return all_works