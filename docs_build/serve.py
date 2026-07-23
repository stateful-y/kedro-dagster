"""Live documentation preview for Kedro-Dagster.

Run the documentation server together with a file watcher that regenerates the
API pages whenever the package source changes, so a newly added class appears in
the preview without a restart.

This replaces what the mkdocs ``on_pre_build`` hook did during ``serve``, in a
form that does not depend on the documentation engine executing a hook. That
independence is the point: the successor engine runs no hooks, and it refuses to
watch files outside the project folder -- so it cannot watch ``src/`` at all. An
external watcher is the only mechanism that works under either engine.

The division of labour: this watcher owns ``src/`` (source change -> regenerate
the API pages under ``docs/pages/api/``), and the documentation engine watches
only ``docs/`` (a regenerated page -> rebuild the site and reload the browser).
That is why ``mkdocs.yml`` watches ``docs`` and not ``src``.

Run it with ``just serve`` or ``nox -s serve_docs``; both call this module.
Notebooks are deliberately out of scope for the live watcher (their export
executes the notebook, which is slow); they are exported once at startup and are
otherwise a build-time step, matching ``serve-fast``/``MKDOCS_SKIP_NOTEBOOKS``.
"""

import subprocess
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

# This module is a plain script run by `just serve`, not a package member, so
# `from ._api_pages import ...` cannot resolve. Put this file's directory on
# sys.path and import the build steps as plain modules -- the same pattern the
# rest of the docs tooling uses.
sys.path.insert(0, str(Path(__file__).parent))

import _api_pages  # noqa: E402

PROJECT_ROOT = Path(__file__).parent.parent
SRC = PROJECT_ROOT / "src"

# watchdog fires several events for a single save (create, modify, moved). A
# short coalescing window turns a burst into one regeneration.
_DEBOUNCE_SECONDS = 0.5
_POLL_SECONDS = 0.2

# The one line that knows which engine renders the docs. Under the successor
# engine this becomes its own serve command; nothing else here changes.
_SERVE_COMMAND = ["mkdocs", "serve", "-a", "localhost:8080"]


def regenerate():
    """Regenerate the API pages from the current package source.

    This is the live case: only the API pages depend on ``src/``. Notebooks are
    not re-exported here -- executing them on every source edit is too slow.

    The discovery caches are reset first. They persist for the process lifetime
    (that is what makes them caches, and a single build fills them once), so
    without a reset a second regeneration reuses the first walk and never sees a
    newly added class. ``on_config`` did this per build; the supervisor does it
    per regeneration.
    """
    _api_pages.reset_caches()
    _api_pages.generate(PROJECT_ROOT)


def _initial_build():
    """Generate the derived pages once, before the server starts.

    Without this the first paint has no API pages when no hook runs them. Mirrors
    what ``on_pre_build`` does, so the served site is complete from the start.
    """
    regenerate()


class _SourceChangeHandler(FileSystemEventHandler):
    """Record Python-file changes under ``src/`` for debounced regeneration."""

    def __init__(self):
        self._pending_since = None

    def on_any_event(self, event):
        """Note the time of any ``.py`` change; a directory event is ignored."""
        if event.is_directory or not str(event.src_path).endswith(".py"):
            return
        self._pending_since = time.monotonic()

    def take_due(self):
        """Return whether a change has settled past the debounce window.

        Clears the pending marker when it fires, so a settled burst regenerates
        exactly once.
        """
        if self._pending_since is None:
            return False
        if time.monotonic() - self._pending_since < _DEBOUNCE_SECONDS:
            return False
        self._pending_since = None
        return True


def main():
    """Build once, serve, and regenerate the API pages on every source change."""
    _initial_build()

    server = subprocess.Popen(_SERVE_COMMAND)  # noqa: S603

    handler = _SourceChangeHandler()
    observer = Observer()
    observer.schedule(handler, str(SRC), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(_POLL_SECONDS)
            if handler.take_due():
                regenerate()
            if server.poll() is not None:
                break  # the server exited on its own; stop watching
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    main()
