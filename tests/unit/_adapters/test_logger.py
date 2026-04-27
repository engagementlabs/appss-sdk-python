"""Tests for StdoutLogger and NoopLogger."""

from __future__ import annotations

from appss_sdk._adapters.logger import NoopLogger, StdoutLogger


def test_debug_writes_to_stdout(capsys):
    StdoutLogger().debug("dbg")
    captured = capsys.readouterr()
    assert "[appss-sdk] DEBUG dbg" in captured.out
    assert captured.err == ""


def test_info_writes_to_stdout_with_context(capsys):
    StdoutLogger().info("hello", {"k": "v"})
    captured = capsys.readouterr()
    assert "[appss-sdk]" in captured.out
    assert "INFO" in captured.out
    assert "hello" in captured.out
    assert '"k": "v"' in captured.out
    assert captured.err == ""


def test_warn_writes_to_stderr(capsys):
    StdoutLogger().warn("uh oh")
    captured = capsys.readouterr()
    assert "[appss-sdk] WARN uh oh" in captured.err
    assert captured.out == ""


def test_error_writes_to_stderr(capsys):
    StdoutLogger().error("boom")
    captured = capsys.readouterr()
    assert "[appss-sdk] ERROR boom" in captured.err
    assert captured.out == ""


def test_error_includes_json_context(capsys):
    StdoutLogger().error("boom", {"errno": 42})
    captured = capsys.readouterr()
    assert "ERROR" in captured.err
    assert '"errno": 42' in captured.err


def test_empty_context_is_omitted(capsys):
    StdoutLogger().info("plain", {})
    captured = capsys.readouterr()
    # No JSON object trailing the message.
    assert captured.out.strip().endswith("plain")


def test_noop_logger_silent(capsys):
    log = NoopLogger()
    log.debug("a")
    log.info("b", {"c": 1})
    log.warn("d")
    log.error("e", {"f": 2})
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""
