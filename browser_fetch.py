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


class BrowserFetchError(RuntimeError):
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
            shutil.which("chromium")
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

        options = {
            "stdout":
                subprocess.DEVNULL,
            "stderr":
                subprocess.DEVNULL,
        }

        if os.name == "posix":
            options[
                "start_new_session"
            ] = True

        self.process = subprocess.Popen(
            command,
            **options,
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

            time.sleep(0.2)

        if self.devtools_port is None:
            raise BrowserFetchError(
                "Timed out waiting for "
                "Chromium DevTools."
            )

        targets = requests.get(
            (
                "http://127.0.0.1:"
                f"{self.devtools_port}"
                "/json/list"
            ),
            timeout=5,
        ).json()

        page = next(
            (
                target
                for target in targets
                if target.get("type")
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

        self.websocket = connect(
            websocket_url,
            open_timeout=5,
        )

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
            payload["params"] = params

        self.websocket.send(
            json.dumps(payload)
        )

        while True:
            message = json.loads(
                self.websocket.recv(
                    timeout=10
                )
            )

            if (
                message.get("id")
                != command_id
            ):
                continue

            if "error" in message:
                raise BrowserFetchError(
                    "Chromium DevTools error: "
                    f"{message['error']}"
                )

            return message.get(
                "result",
                {},
            )

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
            evaluation.get("subtype")
            == "error"
        ):
            raise BrowserFetchError(
                "Chromium JavaScript "
                "evaluation failed."
            )

        return evaluation.get(
            "value"
        )

    def fetch(self, url):
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
                "Chromium navigation failed: "
                f"{error_text}"
            )

        deadline = (
            time.monotonic()
            + PAGE_LOAD_TIMEOUT_SECONDS
        )

        time.sleep(1)

        while time.monotonic() < deadline:
            state = self._evaluate(
                "document.readyState"
            )

            if state == "complete":
                break

            time.sleep(0.25)

        else:
            raise BrowserFetchError(
                "Timed out waiting for AO3 "
                "to finish loading in Chromium."
            )

        time.sleep(0.5)

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

        metadata = json.loads(
            metadata_json
        )

        html = self._evaluate(
            (
                "document.documentElement."
                "outerHTML"
            )
        )

        if not html:
            raise BrowserFetchError(
                "Chromium returned an empty "
                "page."
            )

        title = metadata.get(
            "title",
            "",
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
            url=metadata.get(
                "href",
                url,
            ),
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
                        self.process.kill()
                    except Exception:
                        pass

            self.process = None

        shutil.rmtree(
            self.profile_dir,
            ignore_errors=True,
        )


_browser_session = None


def fetch_browser_page(url):
    global _browser_session

    if _browser_session is None:
        print(
            "  Starting headed Chromium "
            "fallback..."
        )

        _browser_session = (
            HeadedChromiumSession()
        )

    return _browser_session.fetch(
        url
    )


def close_browser_session():
    global _browser_session

    if _browser_session is None:
        return

    _browser_session.close()
    _browser_session = None


atexit.register(
    close_browser_session
)