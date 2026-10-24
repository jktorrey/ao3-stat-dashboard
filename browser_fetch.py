import atexit
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time
import base64
from datetime import datetime, timezone
import requests
from websockets.sync.client import connect


BROWSER_START_TIMEOUT_SECONDS = 20
PAGE_LOAD_TIMEOUT_SECONDS = 30
DEVTOOLS_COMMAND_TIMEOUT_SECONDS = 30
CLOUDFLARE_CHALLENGE_TIMEOUT_SECONDS = 60
BROWSER_FETCH_ATTEMPTS = 2


class BrowserFetchError(
    RuntimeError
):
    pass

class HumanVerificationRequired(
    BrowserFetchError
):
    pass

class BrowserPage:
    def __init__(
        self,
        text,
        url,
        title=None,
    ):
        self.text = text
        self.url = url
        self.title = title
        self.status_code = 200

    def close(self):
        pass


class HeadedChromiumSession:
    def __init__(self):
        self.profile_dir = Path(
            tempfile.mkdtemp(
                prefix="ao3-headed-",
            )
        )

        self.process = None
        self.websocket = None
        self.devtools_port = None
        self.next_command_id = 1

        try:
            self._start()

        except Exception:
            self.close()
            raise

    def _start(self):
        xvfb_run = shutil.which(
            "xvfb-run"
        )

        chromium = (
            shutil.which(
                "chromium"
            )
            or shutil.which(
                "chromium-browser"
            )
        )

        if xvfb_run is None:
            raise BrowserFetchError(
                "xvfb-run is not installed."
            )

        if chromium is None:
            raise BrowserFetchError(
                "Chromium is not installed."
            )

        command = [
            xvfb_run,
            "-a",
            chromium,
            (
                "--user-data-dir="
                f"{self.profile_dir}"
            ),
            (
                "--remote-debugging-address="
                "127.0.0.1"
            ),
            "--remote-debugging-port=0",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ]

        popen_options = {
            "stdout":
                subprocess.DEVNULL,
            "stderr":
                subprocess.DEVNULL,
        }

        if os.name == "posix":
            popen_options[
                "start_new_session"
            ] = True

        self.process = subprocess.Popen(
            command,
            **popen_options,
        )

        devtools_file = (
            self.profile_dir
            / "DevToolsActivePort"
        )

        deadline = (
            time.monotonic()
            + BROWSER_START_TIMEOUT_SECONDS
        )

        while time.monotonic() < deadline:
            if (
                self.process.poll()
                is not None
            ):
                raise BrowserFetchError(
                    "Chromium exited before "
                    "DevTools became available."
                )

            if devtools_file.exists():
                lines = (
                    devtools_file
                    .read_text(
                        encoding="utf-8"
                    )
                    .splitlines()
                )

                if lines:
                    self.devtools_port = int(
                        lines[0]
                    )

                    break

            time.sleep(
                0.2
            )

        if self.devtools_port is None:
            raise BrowserFetchError(
                "Timed out waiting for "
                "Chromium DevTools."
            )

        try:
            targets_response = (
                requests.get(
                    (
                        "http://127.0.0.1:"
                        f"{self.devtools_port}"
                        "/json/list"
                    ),
                    timeout=5,
                )
            )

            targets_response.raise_for_status()

            targets = (
                targets_response.json()
            )

        except Exception as error:
            raise BrowserFetchError(
                "Could not retrieve Chromium "
                "DevTools targets: "
                f"{error}"
            ) from error

        page = next(
            (
                target
                for target in targets
                if target.get(
                    "type"
                )
                == "page"
            ),
            None,
        )

        if page is None:
            raise BrowserFetchError(
                "Chromium did not expose "
                "a page target."
            )

        websocket_url = page.get(
            "webSocketDebuggerUrl"
        )

        if not websocket_url:
            raise BrowserFetchError(
                "Chromium page target did not "
                "provide a DevTools WebSocket."
            )

        try:
            self.websocket = connect(
                websocket_url,
                open_timeout=5,
            )

        except Exception as error:
            raise BrowserFetchError(
                "Could not connect to Chromium "
                "DevTools WebSocket: "
                f"{error}"
            ) from error

        self._command(
            "Page.enable"
        )

    def _command(
        self,
        method,
        params=None,
    ):
        if self.websocket is None:
            raise BrowserFetchError(
                "Chromium DevTools connection "
                "is not available."
            )

        command_id = (
            self.next_command_id
        )

        self.next_command_id += 1

        payload = {
            "id": command_id,
            "method": method,
        }

        if params is not None:
            payload[
                "params"
            ] = params

        try:
            self.websocket.send(
                json.dumps(
                    payload
                )
            )

            while True:
                message = json.loads(
                    self.websocket.recv(
                        timeout=(
                            DEVTOOLS_COMMAND_TIMEOUT_SECONDS
                        )
                    )
                )

                if (
                    message.get(
                        "id"
                    )
                    != command_id
                ):
                    continue

                if "error" in message:
                    raise BrowserFetchError(
                        "Chromium DevTools "
                        "error: "
                        f"{message['error']}"
                    )

                return message.get(
                    "result",
                    {},
                )

        except BrowserFetchError:
            raise

        except Exception as error:
            raise BrowserFetchError(
                "Chromium DevTools command "
                f"{method} failed: "
                f"{error}"
            ) from error

    def _evaluate(
        self,
        expression,
    ):
        result = self._command(
            "Runtime.evaluate",
            {
                "expression":
                    expression,
                "returnByValue":
                    True,
            },
        )

        evaluation = result.get(
            "result",
            {},
        )

        if (
            evaluation.get(
                "subtype"
            )
            == "error"
        ):
            raise BrowserFetchError(
                "Chromium JavaScript "
                "evaluation failed."
            )

        return evaluation.get(
            "value"
        )

    def _get_page_metadata(
        self,
    ):
        metadata_json = self._evaluate(
            """
            JSON.stringify({
                href: window.location.href,
                title: document.title
            })
            """
        )

        if not metadata_json:
            raise BrowserFetchError(
                "Chromium did not return "
                "page metadata."
            )

        try:
            return json.loads(
                metadata_json
            )

        except json.JSONDecodeError as error:
            raise BrowserFetchError(
                "Chromium returned invalid "
                "page metadata."
            ) from error

    def _save_challenge_diagnostics(
        self,
    ):
        project_dir = (
            Path(__file__)
            .resolve()
            .parent
        )

        diagnostic_dir = (
            project_dir
            / "logs"
            / "browser_diagnostics"
        )

        diagnostic_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        timestamp = (
            datetime.now(
                timezone.utc
            )
            .strftime(
                "%Y%m%dT%H%M%S_%fZ"
            )
        )

        filename_prefix = (
            "cloudflare_challenge_"
            f"{timestamp}"
        )

        metadata = (
            self._get_page_metadata()
        )

        html = self._evaluate(
            (
                "document.documentElement."
                "outerHTML"
            )
        )

        if html is None:
            html = ""

        visible_text = self._evaluate(
            """
            document.body
                ? document.body.innerText
                : ""
            """
        )

        if visible_text is None:
            visible_text = ""

        screenshot_result = (
            self._command(
                "Page.captureScreenshot",
                {
                    "format": "png",
                    "captureBeyondViewport":
                        True,
                },
            )
        )

        screenshot_data = (
            screenshot_result.get(
                "data"
            )
        )

        html_path = (
            diagnostic_dir
            / (
                filename_prefix
                + ".html"
            )
        )

        text_path = (
            diagnostic_dir
            / (
                filename_prefix
                + ".txt"
            )
        )

        screenshot_path = (
            diagnostic_dir
            / (
                filename_prefix
                + ".png"
            )
        )

        html_path.write_text(
            html,
            encoding="utf-8",
        )

        report = (
            "Cloudflare challenge "
            "diagnostic\n\n"
            "URL:\n"
            f"{metadata.get('href', '')}\n\n"
            "Title:\n"
            f"{metadata.get('title', '')}\n\n"
            "Visible page text:\n"
            f"{visible_text}\n"
        )

        text_path.write_text(
            report,
            encoding="utf-8",
        )

        if screenshot_data:
            screenshot_path.write_bytes(
                base64.b64decode(
                    screenshot_data
                )
            )

        print(
            "  Saved Cloudflare challenge "
            "diagnostics to:"
        )

        print(
            f"    {diagnostic_dir}"
        )

        return diagnostic_dir

    def fetch(
        self,
        url,
    ):
        navigation = self._command(
            "Page.navigate",
            {
                "url": url,
            },
        )

        error_text = navigation.get(
            "errorText"
        )

        if error_text:
            raise BrowserFetchError(
                "Chromium navigation "
                "failed: "
                f"{error_text}"
            )

        page_deadline = (
            time.monotonic()
            + PAGE_LOAD_TIMEOUT_SECONDS
        )

        time.sleep(
            1
        )

        while (
            time.monotonic()
            < page_deadline
        ):
            state = self._evaluate(
                "document.readyState"
            )

            if state == "complete":
                break

            time.sleep(
                0.25
            )

        else:
            raise BrowserFetchError(
                "Timed out waiting for AO3 "
                "to finish loading in "
                "Chromium."
            )

        challenge_started_at = None
        challenge_deadline = None
        next_progress_message = 10

        while True:
            try:
                metadata = (
                    self._get_page_metadata()
                )

            except BrowserFetchError:
                if (
                    challenge_started_at
                    is not None
                    and time.monotonic()
                    < challenge_deadline
                ):
                    time.sleep(
                        1
                    )

                    continue

                raise

            title = (
                metadata.get(
                    "title",
                    "",
                )
                .strip()
            )

            normalized_title = (
                title.lower()
            )

            is_cloudflare_challenge = (
                "just a moment"
                in normalized_title
            )

            if not is_cloudflare_challenge:
                break

            visible_text = self._evaluate(
                """
                document.body
                    ? document.body.innerText
                    : ""
                """
            )

            if visible_text is None:
                visible_text = ""

            normalized_text = (
                visible_text.lower()
            )

            human_challenge_phrases = (
                "please prove that you are "
                "not a robot",
                "verify you are human",
                "prove that you are human",
            )

            human_verification_required = any(
                phrase in normalized_text
                for phrase
                in human_challenge_phrases
            )

            if human_verification_required:
                diagnostic_dir = None

                try:
                    diagnostic_dir = (
                        self
                        ._save_challenge_diagnostics()
                    )

                except Exception as error:
                    print(
                        "  Could not save "
                        "Cloudflare challenge "
                        "diagnostics: "
                        f"{error}"
                    )

                print(
                    "  Cloudflare requires "
                    "human verification for "
                    "this request."
                )

                message = (
                    "AO3's Cloudflare "
                    "protection requires human "
                    "verification for this "
                    "request. Automated "
                    "collection cannot continue "
                    "for this work. No snapshot "
                    "was saved. A later "
                    "collection may succeed "
                    "normally."
                )

                if diagnostic_dir is not None:
                    message += (
                        " Diagnostics were "
                        "saved under "
                        f"{diagnostic_dir}."
                    )

                raise HumanVerificationRequired(
                    message
                )

            if challenge_started_at is None:
                challenge_started_at = (
                    time.monotonic()
                )

                challenge_deadline = (
                    challenge_started_at
                    + CLOUDFLARE_CHALLENGE_TIMEOUT_SECONDS
                )

                print(
                    "  Cloudflare browser "
                    "challenge detected; "
                    "waiting up to "
                    f"{CLOUDFLARE_CHALLENGE_TIMEOUT_SECONDS} "
                    "seconds for it to clear..."
                )

            elapsed_seconds = int(
                time.monotonic()
                - challenge_started_at
            )

            if (
                elapsed_seconds
                >= next_progress_message
            ):
                print(
                    "  Still waiting for "
                    "Cloudflare challenge... "
                    f"{elapsed_seconds} seconds"
                )

                next_progress_message += 10

            if (
                time.monotonic()
                >= challenge_deadline
            ):
                diagnostic_dir = None

                try:
                    diagnostic_dir = (
                        self
                        ._save_challenge_diagnostics()
                    )

                except Exception as error:
                    print(
                        "  Could not save "
                        "Cloudflare challenge "
                        "diagnostics: "
                        f"{error}"
                    )

                message = (
                    "Cloudflare browser "
                    "challenge did not clear "
                    "within the configured "
                    f"{CLOUDFLARE_CHALLENGE_TIMEOUT_SECONDS}-"
                    "second timeout."
                )

                if diagnostic_dir is not None:
                    message += (
                        " Diagnostics were "
                        "saved under "
                        f"{diagnostic_dir}."
                    )

                raise BrowserFetchError(
                    message
                )

            time.sleep(
                1
            )

        if (
            challenge_started_at
            is not None
        ):
            elapsed_seconds = int(
                time.monotonic()
                - challenge_started_at
            )

            print(
                "  Cloudflare browser "
                "challenge cleared after "
                f"{elapsed_seconds} seconds."
            )

        final_page_deadline = (
            time.monotonic()
            + PAGE_LOAD_TIMEOUT_SECONDS
        )

        while (
            time.monotonic()
            < final_page_deadline
        ):
            state = self._evaluate(
                "document.readyState"
            )

            if state == "complete":
                break

            time.sleep(
                0.25
            )

        else:
            raise BrowserFetchError(
                "Timed out waiting for AO3 "
                "to finish loading after the "
                "Cloudflare challenge."
            )

        time.sleep(
            0.5
        )

        metadata = (
            self._get_page_metadata()
        )

        html = self._evaluate(
            (
                "document.documentElement."
                "outerHTML"
            )
        )

        if not html:
            raise BrowserFetchError(
                "Chromium returned an "
                "empty page."
            )

        title = metadata.get(
            "title",
            "",
        )

        final_url = metadata.get(
            "href",
            url,
        )

        normalized_title = (
            title.lower()
        )

        if (
            "just a moment"
            in normalized_title
        ):
            raise BrowserFetchError(
                "Chromium remained on the "
                "Cloudflare browser challenge "
                "page."
            )

        if (
            "525" in title
            or "526" in title
            or "Error code 525" in html
            or "Error code 526" in html
        ):
            raise BrowserFetchError(
                "Headed Chromium also "
                "received a Cloudflare "
                "525/526 response."
            )

        return BrowserPage(
            text=html,
            url=final_url,
            title=title,
        )

    
    def close(self):
        if self.websocket is not None:
            try:
                self.websocket.close()

            except Exception:
                pass

            self.websocket = None

        if self.process is not None:
            if (
                self.process.poll()
                is None
            ):
                try:
                    if os.name == "posix":
                        os.killpg(
                            os.getpgid(
                                self.process.pid
                            ),
                            signal.SIGTERM,
                        )

                    else:
                        self.process.terminate()

                    self.process.wait(
                        timeout=5
                    )

                except Exception:
                    try:
                        if (
                            self.process.poll()
                            is None
                        ):
                            if os.name == "posix":
                                os.killpg(
                                    os.getpgid(
                                        self.process.pid
                                    ),
                                    signal.SIGKILL,
                                )

                            else:
                                self.process.kill()

                    except Exception:
                        pass

            self.process = None

        shutil.rmtree(
            self.profile_dir,
            ignore_errors=True,
        )


_browser_session = None


def fetch_browser_page(
    url,
):
    global _browser_session

    last_error = None

    for attempt in range(
        1,
        BROWSER_FETCH_ATTEMPTS + 1,
    ):
        try:
            if _browser_session is None:
                if attempt == 1:
                    print(
                        "  Starting headed "
                        "Chromium fallback..."
                    )

                else:
                    print(
                        "  Restarting headed "
                        "Chromium fallback..."
                    )

                _browser_session = (
                    HeadedChromiumSession()
                )

            return _browser_session.fetch(
                url
            )

        except HumanVerificationRequired:
            print(
                "  Human verification "
                "required; not retrying this "
                "work."
            )

            close_browser_session()

            raise

        except Exception as error:
            last_error = error

            print(
                "  Headed Chromium fetch "
                f"attempt {attempt}/"
                f"{BROWSER_FETCH_ATTEMPTS} "
                f"failed: {error}"
            )

            close_browser_session()

            if (
                attempt
                < BROWSER_FETCH_ATTEMPTS
            ):
                print(
                    "  Retrying the same page "
                    "with a fresh Chromium "
                    "session..."
                )

    raise BrowserFetchError(
        "Headed Chromium failed after "
        f"{BROWSER_FETCH_ATTEMPTS} "
        f"attempts for {url}: "
        f"{last_error}"
    ) from last_error


def close_browser_session():
    global _browser_session

    if _browser_session is None:
        return

    _browser_session.close()
    _browser_session = None


atexit.register(
    close_browser_session
)