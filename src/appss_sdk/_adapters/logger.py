"""Logger adapters."""

from __future__ import annotations

import json
import sys
from typing import Any, TextIO


def _format(level: str, message: str, context: dict[str, Any] | None) -> str:
    if context:
        return f"[appss-sdk] {level} {message} {json.dumps(context)}"
    return f"[appss-sdk] {level} {message}"


def _emit(stream: TextIO, level: str, message: str, context: dict[str, Any] | None) -> None:
    print(_format(level, message, context), file=stream)


class StdoutLogger:
    """ILogger implementation that writes to stdout/stderr."""

    def debug(self, message: str, context: dict[str, Any] | None = None) -> None:
        _emit(sys.stdout, "DEBUG", message, context)

    def info(self, message: str, context: dict[str, Any] | None = None) -> None:
        _emit(sys.stdout, "INFO", message, context)

    def warn(self, message: str, context: dict[str, Any] | None = None) -> None:
        _emit(sys.stderr, "WARN", message, context)

    def error(self, message: str, context: dict[str, Any] | None = None) -> None:
        _emit(sys.stderr, "ERROR", message, context)


class NoopLogger:
    """ILogger implementation that discards every message. Used when ``debug=False``."""

    def debug(self, message: str, context: dict[str, Any] | None = None) -> None:
        pass

    def info(self, message: str, context: dict[str, Any] | None = None) -> None:
        pass

    def warn(self, message: str, context: dict[str, Any] | None = None) -> None:
        pass

    def error(self, message: str, context: dict[str, Any] | None = None) -> None:
        pass
