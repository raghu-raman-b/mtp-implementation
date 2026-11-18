"""Persistent HTTP connections (keep-alive) to the model server and the embedder, for qa's streamed rounds.

    from scripts.llm.http_pool import POOL
    with POOL.request("POST", url + "/v1/chat/completions", body, headers, timeout=600) as r:
        for line in r: ...                 # r is an http.client.HTTPResponse
    POOL.keep_warm(base_url)               # optional: ping /health every few seconds so a connection stays open

Why: the demo reaches the model through an SSH port forward (ssh -L). Every new TCP connection to the forwarded port
is a new SSH channel, and ssh sends nothing on it until the server side confirms the channel: one round trip
(100-250 ms from a laptop to a cloud instance) before the request even leaves. urllib opens a new connection per
request; this pool keeps one open per server and reuses it for the next request (a question's rounds follow each
other within a second or two).

Servers close idle connections: llama-server after 5 s (and after 100 requests), vLLM after
VLLM_HTTP_TIMEOUT_KEEP_ALIVE (default 5 s). llama-server also closes the connection after every streamed answer
(measured on the PC's build, 2026-11-17). A request on a connection the server has closed fails before any response
arrives; it is then sent once more on a new connection (safe: the server never saw it), and a server seen closing
after a stream gets no such connection back again. keep_warm(base) keeps a spare connection to that server open and
tested: GET /health on it every PING_S seconds, and a new spare opened (and pinged) as soon as a request takes the
one there was, so the next round of a question finds its connection ready (a new SSH channel costs a round trip;
here it is paid while the model is still answering the round before). A dead tunnel is noticed between questions.

Standard library only; thread-safe (a connection is used by one request at a time).
"""
from __future__ import annotations

import http.client
import socket
import threading
import time
from urllib.parse import urlsplit

PING_S = 3.0          # under the servers' 5 s idle timeout
STALE_S = 4.5         # an idle connection older than this is closed when another one comes back


class PooledResponse:
    """The response of one request; closing it (or leaving the with-block) gives the connection back to the pool when
    the body was read to its end, and closes it otherwise."""

    def __init__(self, pool: "Pool", key, conn: http.client.HTTPConnection, resp: http.client.HTTPResponse):
        self.pool, self.key, self.conn, self.resp = pool, key, conn, resp
        self.status = resp.status
        self.stream = "event-stream" in (resp.getheader("Content-Type") or "")

    def __iter__(self):
        return iter(self.resp)

    def read(self, *a) -> bytes:
        return self.resp.read(*a)

    def getheader(self, name, default=None):
        return self.resp.getheader(name, default)

    def close(self):
        if self.conn is None:
            return
        reusable = False
        try:
            if not self.resp.isclosed():
                # the caller stopped at "data: [DONE]": the chunked body's end follows at once
                if self.conn.sock is not None:
                    self.conn.sock.settimeout(2)
                self.resp.read()
            reusable = not self.resp.will_close and not (self.stream and self.key in self.pool._stream_closes)
        except (OSError, http.client.HTTPException):
            reusable = False
        if reusable:
            self.conn._pool_after_stream = self.stream
            self.pool._put(self.key, self.conn)
        else:
            self.conn.close()
        self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if exc[0] is not None and self.conn is not None:      # an error mid-body: the connection is in an unknown state
            self.conn.close()
            self.conn = None
        self.close()


class Pool:
    def __init__(self):
        self._idle: dict[tuple, list[tuple[http.client.HTTPConnection, float]]] = {}
        self._lock = threading.Lock()
        self._warm: dict[tuple, str] = {}            # key -> health path
        self._pinger: threading.Thread | None = None
        self._wake = threading.Event()                # a spare was taken: open the next one now
        self._stream_closes: set = set()              # servers that close the connection after a streamed answer
        self.opened = 0                               # connections opened (for tests and timing notes)

    @staticmethod
    def _key(url: str) -> tuple:
        u = urlsplit(url)
        return (u.scheme or "http", u.hostname or "127.0.0.1", u.port or (443 if u.scheme == "https" else 80))

    def _new(self, key, timeout) -> http.client.HTTPConnection:
        cls = http.client.HTTPSConnection if key[0] == "https" else http.client.HTTPConnection
        conn = cls(key[1], key[2], timeout=timeout)
        conn.connect()
        try:                                            # small writes (a request, a ping) leave at once
            conn.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError:
            pass
        with self._lock:
            self.opened += 1
        return conn

    def _get(self, key) -> http.client.HTTPConnection | None:
        with self._lock:
            idle = self._idle.get(key) or []
            while idle:
                conn, _ = idle.pop()
                if conn.sock is not None:
                    return conn
        return None

    def _put(self, key, conn):
        if conn.sock is None:
            return
        now = time.monotonic()
        with self._lock:
            idle = self._idle.setdefault(key, [])
            for old in [x for x in idle if now - x[1] > STALE_S]:     # the server has closed these by now
                old[0].close()
                idle.remove(old)
            idle.append((conn, now))

    def request(self, method: str, url: str, body: bytes | None = None, headers: dict | None = None,
                timeout: float = 60) -> PooledResponse:
        """Send one request on an open connection to that server (or a new one) and return its response once the
        status line and headers are in. Raises OSError (ConnectionError, TimeoutError) or http.client.HTTPException
        when the server cannot be reached."""
        key = self._key(url)
        u = urlsplit(url)
        path = (u.path or "/") + (f"?{u.query}" if u.query else "")
        for attempt in range(2):
            conn = self._get(key) if attempt == 0 else None
            fresh = conn is None
            if fresh:
                conn = self._new(key, timeout)
            else:
                conn.timeout = timeout
                if conn.sock is not None:
                    conn.sock.settimeout(timeout)
            if key in self._warm:
                self._wake.set()                        # the keep-warm thread opens the next spare meanwhile
            try:
                conn.request(method, path, body=body, headers=headers or {})
                resp = conn.getresponse()
                return PooledResponse(self, key, conn, resp)
            except (OSError, http.client.HTTPException):
                conn.close()
                if fresh:
                    raise
                if getattr(conn, "_pool_after_stream", False):
                    self._stream_closes.add(key)       # this server closes after a stream: never keep those
                # a kept connection the server had closed while idle: the request never reached it; send it again
        raise ConnectionError("unreachable")                    # not reached

    # ------------------------------------------------------------ keep warm
    def keep_warm(self, base_url: str, path: str = "/health", on_body=None):
        """Keep a connection to this server open (GET path every PING_S seconds on an idle one); opens it now.
        on_body(bytes): called with each 200 answer (qa reads llama.cpp's /slots this way: which slots are busy)."""
        key = self._key(base_url)
        with self._lock:
            self._warm[key] = (path, on_body)
            start = self._pinger is None
            if start:
                self._pinger = threading.Thread(target=self._ping_loop, name="http-keep-warm", daemon=True)
        self._ping(key, (path, on_body))
        if start:
            self._pinger.start()

    def _ping(self, key, what):
        path, on_body = what
        url = f"{key[0]}://{key[1]}:{key[2]}{path}"
        try:
            with self.request("GET", url, timeout=10) as r:
                body = r.read()
                if r.status == 200 and on_body:
                    on_body(body)
        except (OSError, http.client.HTTPException):
            pass                                                # down: tried again at the next tick
        except Exception:                                       # noqa: BLE001  a callback's error must not stop pings
            pass

    def _ping_loop(self):
        while True:
            self._wake.wait(PING_S / 3)
            self._wake.clear()
            now = time.monotonic()
            with self._lock:
                todo = []
                for key, what in self._warm.items():
                    idle = self._idle.get(key) or []
                    newest = max((t for _, t in idle), default=None)
                    if newest is None or now - newest >= PING_S:
                        todo.append((key, what))
            for key, what in todo:
                self._ping(key, what)


POOL = Pool()
