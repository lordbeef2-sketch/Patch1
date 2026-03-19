from __future__ import annotations

import asyncio
import logging
import sys
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Set
from typing import TextIO


@dataclass
class ConsoleStream:
    max_buffer_lines: int = 2000
    subscriber_queue_size: int = 500

    _buffer: Deque[str] = field(default_factory=lambda: deque(maxlen=2000))
    _subscribers: Set[asyncio.Queue[str]] = field(default_factory=set)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def subscribe(self) -> asyncio.Queue[str]:
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=self.subscriber_queue_size)
        async with self._lock:
            self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    def get_buffer_snapshot(self) -> list[str]:
        return list(self._buffer)

    async def publish(self, line: str) -> None:
        if not line:
            return

        # Normalize to single line without trailing newline.
        normalized = line.rstrip("\r\n")
        if not normalized:
            return

        self._buffer.append(normalized)

        async with self._lock:
            subscribers = list(self._subscribers)

        for queue in subscribers:
            try:
                queue.put_nowait(normalized)
            except asyncio.QueueFull:
                # Drop if client can't keep up.
                pass

    async def reset(self, reason: str = "reset") -> None:
        async with self._lock:
            self._buffer.clear()
            subscribers = list(self._subscribers)

        marker = f"[system] OWUI console stream {reason} requested"
        self._buffer.append(marker)

        for queue in subscribers:
            try:
                queue.put_nowait(marker)
            except asyncio.QueueFull:
                pass


class _ConsoleStreamLogHandler(logging.Handler):
    def __init__(self, stream: ConsoleStream, loop: asyncio.AbstractEventLoop | None) -> None:
        super().__init__()
        self._stream = stream
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
        except Exception:
            msg = record.getMessage()

        # Prefer publishing on the main server loop (works even when logging from worker threads).
        if self._loop is not None and self._loop.is_running():
            try:
                self._loop.call_soon_threadsafe(
                    self._loop.create_task, self._stream.publish(msg)
                )
                return
            except Exception:
                pass

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._stream.publish(msg))
        except RuntimeError:
            # No running loop (e.g., during early import) -> best effort buffer only.
            self._stream._buffer.append(msg.rstrip("\r\n"))


_console_stream_singleton: ConsoleStream | None = None
_handler_installed = False
_console_loop: asyncio.AbstractEventLoop | None = None


def get_console_stream() -> ConsoleStream:
    global _console_stream_singleton
    if _console_stream_singleton is None:
        _console_stream_singleton = ConsoleStream()
    return _console_stream_singleton


def attach_console_stream_handler() -> None:
    """Attach a logging handler that broadcasts log lines for SSE clients.

    Safe to call multiple times.
    """

    global _handler_installed
    if _handler_installed:
        return

    global _console_loop
    if _console_loop is None:
        try:
            _console_loop = asyncio.get_running_loop()
        except RuntimeError:
            _console_loop = None

    stream = get_console_stream()
    handler = _ConsoleStreamLogHandler(stream, _console_loop)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Attach to root and common uvicorn loggers.
    logging.getLogger().addHandler(handler)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addHandler(handler)

    _handler_installed = True


class _TeeTextIO:
    """A minimal text IO wrapper that tees writes to the admin console stream.

    - Preserves the original stream output.
    - Buffers partial lines and only publishes full lines.
    """

    def __init__(self, original: TextIO, stream: ConsoleStream, label: str) -> None:
        self._original = original
        self._stream = stream
        self._label = label
        self._partial = ""

    def write(self, s: str) -> int:
        # Always forward to the original stream.
        written = self._original.write(s)

        if not s:
            return written

        # Normalize carriage returns for better readability in the browser.
        s = s.replace("\r\n", "\n").replace("\r", "\n")

        # Accumulate and publish full lines.
        self._partial += s
        while "\n" in self._partial:
            line, self._partial = self._partial.split("\n", 1)
            if line:
                # Avoid calling logging from inside stdio (can recurse).
                msg = f"[{self._label}] {line}"
                if _console_loop is not None and _console_loop.is_running():
                    try:
                        _console_loop.call_soon_threadsafe(
                            _console_loop.create_task, self._stream.publish(msg)
                        )
                        continue
                    except Exception:
                        pass

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._stream.publish(msg))
                except RuntimeError:
                    self._stream._buffer.append(msg)

        return written

    def flush(self) -> None:
        # Publish any remaining partial content on flush.
        if self._partial.strip():
            line = self._partial.rstrip("\r\n")
            self._partial = ""
            msg = f"[{self._label}] {line}"
            if _console_loop is not None and _console_loop.is_running():
                try:
                    _console_loop.call_soon_threadsafe(
                        _console_loop.create_task, self._stream.publish(msg)
                    )
                except Exception:
                    self._stream._buffer.append(msg)
            else:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._stream.publish(msg))
                except RuntimeError:
                    self._stream._buffer.append(msg)

        self._original.flush()

    def isatty(self) -> bool:
        return bool(getattr(self._original, "isatty", lambda: False)())

    def fileno(self) -> int:
        return int(getattr(self._original, "fileno")())

    @property
    def encoding(self):
        return getattr(self._original, "encoding", None)

    @property
    def errors(self):
        return getattr(self._original, "errors", None)


_stdio_installed = False


def attach_console_stream_stdio() -> None:
    """Tee stdout/stderr into the console stream.

    Safe to call multiple times.
    """

    global _stdio_installed
    if _stdio_installed:
        return

    global _console_loop
    if _console_loop is None:
        try:
            _console_loop = asyncio.get_running_loop()
        except RuntimeError:
            _console_loop = None

    stream = get_console_stream()

    # Only wrap if they're real text streams.
    if hasattr(sys.stdout, "write"):
        sys.stdout = _TeeTextIO(sys.stdout, stream, "stdout")  # type: ignore[assignment]
    if hasattr(sys.stderr, "write"):
        sys.stderr = _TeeTextIO(sys.stderr, stream, "stderr")  # type: ignore[assignment]

    _stdio_installed = True
