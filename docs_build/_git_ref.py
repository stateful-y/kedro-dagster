"""The single definition of "which commit is this build", shared by the docs tooling.

The marker extension (marimo playground links) and the Source Code template
override (View on GitHub links) both need the same ref. They used to derive it
separately, so a build could publish the two pointing at different commits on one
page -- a shallow or detached checkout where ``git rev-parse`` fails but Read the
Docs' environment still names the commit. Both import this now, so they cannot
disagree; when ``hooks.py`` was deleted this became the one home for the logic.
"""

import os
import subprocess

_CACHE = None


def git_ref() -> str:
    """Return the git ref every repository link points at, most specific first.

    1. ``READTHEDOCS_GIT_COMMIT_HASH`` -- the exact commit RTD checked out, and
       authoritative there precisely because the checkout may not be queryable.
    2. ``git rev-parse HEAD`` -- the answer for a local or CI build.
    3. ``READTHEDOCS_GIT_IDENTIFIER`` -- the branch or tag; less precise than a
       commit but still a ref every link target resolves.
    4. ``"main"`` -- last resort.

    Cached for the lifetime of the process: the ref does not change during a
    build, so a shared value across every link is the point.
    """
    global _CACHE  # noqa: PLW0603
    if _CACHE is not None:
        return _CACHE

    ref = os.environ.get("READTHEDOCS_GIT_COMMIT_HASH")
    if not ref:
        try:
            ref = subprocess.check_output(  # noqa: S603
                ["git", "rev-parse", "HEAD"],  # noqa: S607
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            ref = ""
    if not ref:
        ref = os.environ.get("READTHEDOCS_GIT_IDENTIFIER", "")

    _CACHE = ref or "main"
    return _CACHE
