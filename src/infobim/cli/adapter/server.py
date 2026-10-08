import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.metadata import version as distribution_version
from typing import Any, ClassVar, Dict, Tuple, Type


class InfoBIMRequestHandler(BaseHTTPRequestHandler):
    """
    Answers the one thing the local server is asked: whether it is alive.
    """

    PING_PATH: ClassVar[str] = "/ping"
    APPLICATION: ClassVar[str] = "infobim"
    DISTRIBUTION: ClassVar[str] = "infobim"

    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] != self.PING_PATH:
            self._respond(404, {"status": "not_found"})
            return

        self._respond(
            200,
            {
                "status": "ok",
                "app": self.APPLICATION,
                "version": distribution_version(self.DISTRIBUTION),
            },
        )

    def _respond(self, status: int, payload: Dict[str, Any]) -> None:
        body: bytes = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        return


class InfoBIMServer:
    """
    The local InfoBIM server, reachable from this machine only.
    """

    HOST: ClassVar[str] = "127.0.0.1"
    PORT: ClassVar[int] = 8765

    @classmethod
    def make(
        cls,
        port: int = PORT,
        handler: Type[BaseHTTPRequestHandler] = InfoBIMRequestHandler,
    ) -> ThreadingHTTPServer:
        address: Tuple[str, int] = (cls.HOST, port)
        return ThreadingHTTPServer(address, handler)
