"""Explicit pre/post-build steps, replacing the deleted mkdocs build hooks.

mkdocs' ``on_pre_build`` / ``on_post_build`` do not run under the successor
engine, so the API-page generation and the LLM markdown
export run as explicit commands around ``mkdocs build`` instead -- wired into the
justfile, the noxfile, CI and ``.readthedocs.yml``. Run

    python docs_build/build.py prebuild     # before `mkdocs build`
    python docs_build/build.py postbuild DIR # after it (DIR is the built site)

so the same steps run identically on every engine, with nothing hidden in a hook.
"""

import sys
from pathlib import Path

# Loaded as a script, not a package member, so put its own directory on sys.path
# and import the build steps as plain modules -- the pattern the rest of the docs
# tooling uses.
sys.path.insert(0, str(Path(__file__).parent))

import _api_pages  # noqa: E402
import _markdown_export  # noqa: E402

_PROJECT_ROOT = Path(__file__).parent.parent


def prebuild():
    """Generate the API submodule pages."""
    _api_pages.generate(_PROJECT_ROOT)


def postbuild(site_dir):
    """Copy the cleaned markdown into the built site, for LLM consumption."""
    _markdown_export.export(site_dir, str(_PROJECT_ROOT / "docs"), _PROJECT_ROOT)


if __name__ == "__main__":
    _command = sys.argv[1] if len(sys.argv) > 1 else "prebuild"
    if _command == "prebuild":
        prebuild()
    elif _command == "postbuild":
        # Default matches mkdocs' default site_dir; callers (RTD) pass their own.
        postbuild(sys.argv[2] if len(sys.argv) > 2 else "site")
    else:
        raise SystemExit(f"unknown build step: {_command!r} (use 'prebuild' or 'postbuild')")
