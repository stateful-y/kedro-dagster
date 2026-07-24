"""Griffe extension: attach a "View on GitHub" URL to each documented object.

Runs at collection time and stores the object's source URL on ``obj.extra``,
which the Source Code heading override (``class.html.jinja`` /
``function.html.jinja``) renders as a link. This replaces the HTML
post-processing ``_add_source_links`` did in the docs hooks, in a form that needs
no hook.

Why here and not a template: a mkdocstrings template receives the handler's
options, not the mkdocs config, so it cannot see ``repo_url``. This extension
resolves ``repo_url`` (from ``mkdocs.yml``) and the git ref where the filesystem
and environment are available, and hands the finished URL to the template.
"""

import sys
from pathlib import Path

import yaml
from griffe import Extension

# Share the single git-ref definition with the marker extension: both link at the
# same commit, so a shallow or detached checkout cannot make them disagree. This
# is the consolidation the phase-7 duplicate was left waiting for; `docs_build/`
# is put on the path the way the rest of the build tooling does.
sys.path.insert(0, str(Path(__file__).parent))

from _git_ref import git_ref  # noqa: E402

# The namespace/key the Source Code template override reads back.
_EXTRA_NS = "docs"
_SOURCE_URL_KEY = "github_source_url"


def _repo_url() -> str:
    """Read ``repo_url`` from ``mkdocs.yml``, or return "" if unavailable.

    The config carries ``!ENV`` and ``!!python/name:`` tags a strict loader
    raises on, so both are tolerated. Same reader as ``_api_pages`` uses for
    ``preload_modules``.
    """
    config_file = Path("mkdocs.yml")
    if not config_file.exists():
        return ""

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda _loader, suffix, _node: suffix)
    _Loader.add_constructor("!ENV", lambda _loader, _node: None)
    try:
        config = yaml.load(config_file.read_text(encoding="utf-8"), Loader=_Loader)
    except yaml.YAMLError:
        return ""
    return (config or {}).get("repo_url", "").rstrip("/")


class SourceLinkExtension(Extension):
    """Store each object's "View on GitHub" URL on ``obj.extra`` for the template."""

    def __init__(self) -> None:
        """Start with no base URL; it is resolved once the package loads."""
        self._base = None

    def on_package(self, *, pkg, **_kwargs) -> None:  # noqa: ARG002
        """Resolve the repo/blob/ref prefix once. No repo_url -> no links."""
        repo_url = _repo_url()
        self._base = f"{repo_url}/blob/{git_ref()}" if repo_url else None

    def on_object(self, *, obj, **_kwargs) -> None:
        """Attach the object's source URL, keyed by its file relative to the repo."""
        if self._base is None:
            return
        relative = obj.relative_filepath
        if relative is None:
            return
        # `.as_posix()`, not `str()`: `relative_filepath` is a Path, so on Windows
        # `str()` renders backslashes into the URL (`.../blob/main/src\pkg\x.py`),
        # a broken link. A URL is always forward slashes on every platform.
        obj.extra[_EXTRA_NS][_SOURCE_URL_KEY] = f"{self._base}/{relative.as_posix()}"
