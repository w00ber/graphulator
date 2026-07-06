"""Tests for the macOS PATH-augmentation helper.

Pure-logic tests (no Qt/GUI): monkeypatch ``sys.platform`` and
``os.path.isdir`` so the darwin behaviour can be exercised on any host.
"""

import os

from graphulator import _macos_env
from graphulator._macos_env import ensure_external_tools_on_path


def _run_with(monkeypatch, platform, existing_dirs, path_value):
    """Invoke the helper with a fake platform / filesystem / PATH and return
    the resulting PATH entries."""
    monkeypatch.setattr(_macos_env.sys, "platform", platform)
    monkeypatch.setattr(
        _macos_env.os.path, "isdir", lambda d: d in existing_dirs
    )
    monkeypatch.setenv("PATH", path_value)
    ensure_external_tools_on_path()
    return os.environ["PATH"].split(os.pathsep)


def test_prepends_existing_dirs(monkeypatch):
    existing = {"/Library/TeX/texbin", "/opt/homebrew/bin"}
    entries = _run_with(monkeypatch, "darwin", existing, "/usr/bin:/bin")

    # Both existing tool dirs are prepended, ahead of the original PATH.
    assert "/Library/TeX/texbin" in entries
    assert "/opt/homebrew/bin" in entries
    assert entries.index("/Library/TeX/texbin") < entries.index("/usr/bin")
    assert entries[-2:] == ["/usr/bin", "/bin"]


def test_skips_missing_dirs(monkeypatch):
    entries = _run_with(monkeypatch, "darwin", set(), "/usr/bin:/bin")
    # None of the tool dirs exist -> PATH is untouched.
    assert entries == ["/usr/bin", "/bin"]


def test_no_duplicates_when_already_present(monkeypatch):
    existing = {"/usr/local/bin"}
    entries = _run_with(
        monkeypatch, "darwin", existing, "/usr/local/bin:/usr/bin"
    )
    # Already on PATH -> not added a second time.
    assert entries.count("/usr/local/bin") == 1
    assert entries == ["/usr/local/bin", "/usr/bin"]


def test_noop_off_macos(monkeypatch):
    existing = set(_macos_env._MAC_TOOL_DIRS)  # pretend they all exist
    for platform in ("linux", "win32"):
        entries = _run_with(monkeypatch, platform, existing, "/usr/bin:/bin")
        assert entries == ["/usr/bin", "/bin"]


def test_empty_path(monkeypatch):
    existing = {"/Library/TeX/texbin"}
    entries = _run_with(monkeypatch, "darwin", existing, "")
    # No spurious empty entry from splitting an empty PATH.
    assert entries == ["/Library/TeX/texbin"]
