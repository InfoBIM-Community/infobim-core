"""Local HTTP command transport and SSE output for the offline viewer."""

import json
from queue import Empty
from pathlib import Path
from secrets import compare_digest
from threading import Event, Lock
from typing import ClassVar, Dict, Optional
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .terminal_session import TerminalSession


class TerminalEventServer(ThreadingHTTPServer):
    HOST: ClassVar[str] = "127.0.0.1"
    PORT: ClassVar[int] = 8765
    daemon_threads: bool = True

    def __init__(self) -> None:
        self.stopping: Event = Event()
        self.sessions: Dict[str, TerminalSession] = {}
        self.sessions_lock: Lock = Lock()
        self.directory: Path = Path.cwd()
        super().__init__((self.HOST, self.PORT), TerminalEventHandler)

    def server_close(self) -> None:
        self.stopping.set()
        with self.sessions_lock:
            for session in self.sessions.values():
                session.close()
        super().server_close()


class TerminalEventHandler(BaseHTTPRequestHandler):
    server: TerminalEventServer

    def _allowed(self) -> bool:
        if self.headers.get("Host") != "127.0.0.1:8765":
            self.send_error(403, "Invalid local server host")
            return False
        origin: Optional[str] = self.headers.get("Origin")
        if origin is not None and origin not in ("null", "http://127.0.0.1:8765"):
            self.send_error(403, "Origin is not allowed")
            return False
        return True

    def _cors(self) -> None:
        origin: Optional[str] = self.headers.get("Origin")
        if origin is not None:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def do_OPTIONS(self) -> None:
        if not self._allowed():
            return
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        if not self._allowed():
            return
        if self.path != "/command":
            self.send_error(404, "Unknown endpoint")
            return
        authorization: Optional[str] = self.headers.get("Authorization")
        session: Optional[TerminalSession] = None
        if authorization is not None:
            with self.server.sessions_lock:
                for candidate in self.server.sessions.values():
                    if compare_digest(authorization, f"Bearer {candidate.token}"):
                        session = candidate
                        break
        if session is None:
            self.send_error(403, "An active terminal session is required")
            return
        try:
            length_header: Optional[str] = self.headers.get("Content-Length")
            if length_header is None:
                raise ValueError("Content-Length is required")
            length: int = int(length_header)
            if not 0 < length <= 65536:
                raise ValueError("Invalid command size")
            self.connection.settimeout(10)
            payload: object = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("Expected a command object")
            command: object = payload.get("command")
            if not isinstance(command, str) or not command.strip() or "\x00" in command:
                raise ValueError("A non-empty command is required")
        except (ValueError, OSError) as error:
            self.send_error(400, str(error))
            return
        with session.lock:
            if session.closed or session.busy:
                self.send_error(409, "Terminal is closed or busy")
                return
            session.busy = True
            # The request thread runs this command; the SSE thread streams its output.
            self.send_response(202)
            self._cors()
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.wfile.flush()
        session.execute(command)

    def do_GET(self) -> None:
        if not self._allowed():
            return
        if self.path != "/events":
            self.send_error(404, "Unknown endpoint")
            return
        session: TerminalSession = TerminalSession(self.server.directory)
        with self.server.sessions_lock:
            self.server.sessions[session.token] = session
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self._cors()
        self.end_headers()
        try:
            self.wfile.write(f"retry: 2000\nevent: session\ndata: {session.token}\n\n".encode())
            self.wfile.flush()
            while not self.server.stopping.is_set():
                try:
                    event: str
                    data: str
                    event, data = session.events.get(timeout=1)
                    self.wfile.write(f"event: {event}\ndata: {data}\n\n".encode())
                except Empty:
                    self.wfile.write(b": heartbeat\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        finally:
            session.close()
            with self.server.sessions_lock:
                del self.server.sessions[session.token]

    def log_message(self, format: str, *args: object) -> None:
        return


class TerminalConnection:
    @staticmethod
    def serve(language: str | None) -> None:
        portuguese: bool = language is not None and language.lower().startswith("pt")
        try:
            server: TerminalEventServer = TerminalEventServer()
        except OSError as error:
            message: str = (
                "Não foi possível iniciar o servidor em 127.0.0.1:8765"
                if portuguese else
                "Could not start the server at 127.0.0.1:8765"
            )
            raise RuntimeError(f"{message}: {error}") from error
        with server:
            print(
                "Servidor SSE ativo em http://127.0.0.1:8765/events. Ctrl+C para parar."
                if portuguese else
                "SSE server running at http://127.0.0.1:8765/events. Press Ctrl+C to stop.",
                flush=True,
            )
            try:
                server.serve_forever(poll_interval=0.25)
            except KeyboardInterrupt:
                server.stopping.set()
