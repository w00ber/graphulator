"""Keep a test run out of the real per-user files.

The suite builds real application windows, and a window reads and writes
the live ``~/.graphulator*`` state as part of starting up and of any
open/save it is asked to do. So a run used to:

* append pytest temp paths to the recent-files list, pushing the real
  entries off the end of it,
* point the last-used directory at a temp folder that no longer exists, so
  the file dialogs opened somewhere dead, and
* overwrite the session autosave with whatever (usually empty) graph a test
  happened to be holding -- which is why the app came back blank, having
  "forgotten" the graph that was open before the test run.

``GRAPHULATOR_STATE_DIR`` is set before anything imports the package, so
even a test that builds a window without redirecting anything lands in a
temp directory; the autouse fixture then gives each test its own, so tests
cannot see each other's bookkeeping either.
"""

import copy
import os
import tempfile
from pathlib import Path

import pytest

# Before the first `import graphulator`: settings_manager resolves its paths
# at import time, and pytest imports conftest ahead of the test modules.
_SESSION_STATE_DIR = tempfile.mkdtemp(prefix='graphulator-test-state-')
os.environ.setdefault('GRAPHULATOR_STATE_DIR', _SESSION_STATE_DIR)

#: Every per-user path settings_manager exposes, and the dotfile each one
#: hangs off the state directory.
_STATE_PATHS = {
    'USER_SETTINGS_DIR': '.graphulator',
    'USER_SETTINGS_FILE': '.graphulator/settings.json',
    'RECENT_FILES_PATH': '.graphulator_recent',
    'LAST_GRAPH_PATH': '.graphulator_last.graph',
    'LAST_DIRECTORY_PATH': '.graphulator_last_dir',
}


@pytest.fixture(autouse=True)
def isolated_user_state(tmp_path, monkeypatch):
    """Give this test its own state directory.

    Belt and braces over the environment variable above: a test that
    redirects these itself (several do, to assert on what was written)
    still works, and one that forgets cannot reach the real files.
    """
    from graphulator.para_core import settings_manager

    state = tmp_path / 'user-state'
    state.mkdir(exist_ok=True)
    monkeypatch.setenv(settings_manager.STATE_DIR_ENV, str(state))
    for name, relative in _STATE_PATHS.items():
        monkeypatch.setattr(settings_manager, name, state / relative,
                            raising=False)
    return state


@pytest.fixture(autouse=True)
def pristine_config_modules():
    """Undo whatever a test did to the two config modules.

    The Settings dialog applies by setattr-ing the config module, which is
    process-global: one test that pressed Apply left its export scale (or
    node radius, or arrowhead angle) in place for every test that ran
    after it, so the suite's result depended on its order. Snapshotting
    the uppercase attributes and putting them back is cheap and makes each
    test independent of the ones before it.
    """
    from graphulator import graphulator_config, graphulator_para_config

    modules = (graphulator_config, graphulator_para_config)
    saved = [{name: copy.deepcopy(value)
              for name, value in vars(module).items() if name.isupper()}
             for module in modules]
    try:
        yield
    finally:
        for module, snapshot in zip(modules, saved):
            for name, value in snapshot.items():
                setattr(module, name, value)


def pytest_configure(config):
    """Fail loudly rather than quietly writing to the real home."""
    if Path(os.environ['GRAPHULATOR_STATE_DIR']) == Path.home():
        raise RuntimeError(
            "GRAPHULATOR_STATE_DIR points at the real home directory; the "
            "suite would overwrite the live recent-files list and session "
            "autosave. Unset it and let conftest pick a temp directory.")
