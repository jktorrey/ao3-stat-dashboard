import re

import requests
from bs4 import BeautifulSoup


WORK_ID = "84721456"

WORK_URL = (
    f"https://archiveofourown.org/works/{WORK_ID}"
    "/navigate"
    "?view_adult=true"
)

HEADERS = {
    "User-Agent":
        "ao3-stat-dashboard/0.1 "
        "(personal stats tracker)"
}


response = requests.get(
    WORK_URL,
    headers=HEADERS,
    timeout=(10, 15),
)

response.raise_for_status()

soup = BeautifulSoup(
    response.text,
    "html.parser",
)


chapter_pattern = re.compile(
    rf"^/works/{WORK_ID}/chapters/\d+$"
)

chapter_links = soup.find_all(
    "a",
    href=chapter_pattern,
)


seen_urls = set()
chapters = []

for chapter_link in chapter_links:
    chapter_url = chapter_link.get("href")

    if chapter_url in seen_urls:
        continue

    seen_urls.add(chapter_url)

    date_element = chapter_link.find_next(
        "span",
        class_="datetime",
    )

    if date_element is not None:
        chapter_date = (
            date_element.get_text(
                " ",
                strip=True,
            )
        )

    else:
        chapter_date = None

    chapters.append(
        (
            chapter_link,
            chapter_url,
            chapter_date,
        )
    )


print(
    f"Unique chapter links found: "
    f"{len(chapters)}"
)
print()


for index, (
    chapter_link,
    chapter_url,
    chapter_date,
) in enumerate(
    chapters,
    start=1,
):
    title = chapter_link.get_text(
        " ",
        strip=True,
    )

    print(f"Chapter {index}")
    print(f"  Title: {title}")
    print(f"  URL: {chapter_url}")
    print(f"  Date: {chapter_date}")
    print()