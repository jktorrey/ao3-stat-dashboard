import atexit
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

import requests
from websockets.sync.client import connect


BROWSER_START_TIMEOUT_SECONDS = 20
PAGE_LOAD_TIMEOUT_SECONDS = 30
DEVTOOLS_COMMAND_TIMEOUT_SECONDS = 30

BROWSER_FETCH_ATTEMPTS = 2


class BrowserFetchError(
    RuntimeError
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

        deadline = (
            time.monotonic()
            + PAGE_LOAD_TIMEOUT_SECONDS
        )

        time.sleep(
            1
        )

        while time.monotonic() < deadline:
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

        # Give AO3 and Chromium a short
        # settling period after readyState
        # reaches complete.
        time.sleep(
            0.5
        )

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
            metadata = json.loads(
                metadata_json
            )

        except json.JSONDecodeError as error:
            raise BrowserFetchError(
                "Chromium returned invalid "
                "page metadata."
            ) from error

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