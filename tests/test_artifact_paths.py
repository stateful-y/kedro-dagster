"""Every throwaway path this project writes has exactly one definition.

Coverage reports, the JUnit report, the tool caches, the nox environments and the
built site all land under a single ignored directory instead of at the repo root.
That only holds while the place that *writes* each path and the places that *read*
it agree, and nothing else checks that they do.

The failure is silent in both directions. A stale reader of the built site makes
Read the Docs publish an empty directory and the link check examine a site that was
never built. A stale coverage upload path is worse: the uploader falls back to
searching the workspace, finds the report anyway, and reports success -- so the
configured path is dead while the badge stays green.

This test ships with the project rather than living in the template, because the
paths that break are the ones the template does not own. A project's own workflow,
script or recipe can hard-code `site/` long after the template stopped writing
there, and only a check running inside the project can see it.
"""

import re
import subprocess
from pathlib import Path

_PROJECT = Path(__file__).resolve().parent.parent

# Paths that used to sit at the repository root. Nothing may name one outside the
# single config key that now defines where it goes.
#
# `site/` carries the trailing slash deliberately. It is the entry that matters most
# -- many things read the built site -- but bare `site` also appears in `site_url`,
# `site_name` and ordinary prose. Requiring the slash matches the path, not the word.
_RELOCATED = ("site/", "htmlcov", "coverage.xml", "junit.xml", ".nox", ".pytest_cache", ".ruff_cache")

# How each file format names the artifacts directory. A line carrying one of these is
# defining or deriving a path rather than hard-coding a stray one.
_ARTIFACT_ANCHORS = (".artifacts", "ARTIFACTS_DIR", "artifacts_dir", "SITE_DIR", "site_dir")

# Only files where a path is *acted on* are scanned. Prose may mention `site/` freely;
# a workflow step, a recipe or a script cannot. Scoping this way keeps the check
# precise enough that a hit is always worth acting on.
_EXECUTABLE_SUFFIXES = {".yml", ".yaml", ".py", ".toml", ".cfg", ".ini", ".sh", ".jinja"}
_EXECUTABLE_NAMES = {"justfile", "Makefile", "Dockerfile"}


# Directories that hold no project-authored file, used only when git is unavailable.
_UNTRACKED_DIRS = {".git", ".venv", ".artifacts", ".nox", "__pycache__", "node_modules", "site"}


def _tracked_files():
    """Project files, preferring git so build output and virtualenvs are skipped.

    Falls back to a tree walk when this is not a git repository. That is not a
    hypothetical: a freshly generated project has no `.git` until someone runs
    `git init`, and the template's own integration tests run this suite in exactly
    that state -- where `git ls-files` exits 128 and took the whole check down.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=_PROJECT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return [_PROJECT / name for name in result.stdout.split("\0") if name]

    return [
        path
        for path in _PROJECT.rglob("*")
        if path.is_file() and not _UNTRACKED_DIRS.intersection(path.relative_to(_PROJECT).parts)
    ]


def _site_dir():
    """Return the `site_dir` mkdocs.yml configures.

    Read with a regex rather than a YAML parser on purpose. PyYAML belongs to the
    docs dependency group, while this suite runs under the tests group -- importing
    it here fails the whole run with `ModuleNotFoundError` in the session that
    matters, which is how this first reached CI. Adding PyYAML to the tests group to
    read one top-level scalar is the worse trade. `site_dir` is a plain unquoted key
    the template owns, so this is an exact match, not a general YAML parse.
    """
    text = (_PROJECT / "mkdocs.yml").read_text(encoding="utf-8")
    match = re.search(r"^site_dir:\s*(\S+)\s*$", text, re.M)

    assert match, "mkdocs.yml does not set `site_dir`, so nothing defines where the build writes"
    return match.group(1).strip("\"'")


# `site/` with its slash catches the common form, but not `tar -C site .` or a bare
# quoted "site" -- and the tar form is precisely what broke a project's docs deploy.
# Matching a bare `site` token everywhere is not the answer either: measured against a
# real repo it produced 33 hits, all prose ("call site", "warn site", "the built
# site"). A check that noisy gets ignored, which is the failure this file exists to
# prevent. So the slashless forms are matched only where `site` is unambiguously a
# path operand.
_PATH_OPERAND_PREFIXES = ("-C ", "cd ", "-o ", "--site-dir ", "--site-dir=")


def _pattern_for(name):
    """Regex matching `name` used as a path, not merely mentioned."""
    if not name.endswith("/"):
        return rf"(?<![\w./-]){re.escape(name)}(?![\w-])"

    bare = name.rstrip("/")
    alternatives = [rf"(?<![\w./-]){re.escape(name)}"]
    alternatives += [rf"(?<={re.escape(p)}){re.escape(bare)}(?![\w./-])" for p in _PATH_OPERAND_PREFIXES]
    alternatives.append(rf"[\"']{re.escape(bare)}[\"']")
    return "|".join(alternatives)


def hardcoded_relocated_paths(files=None, root=None):
    """Lines naming a relocated path with no tie to the artifacts directory.

    ``files``/``root`` exist so the check can be pointed at a scratch tree and
    proven to fail; nothing else passes them.
    """
    files = _tracked_files() if files is None else files
    root = _PROJECT if root is None else root
    offenders = []

    for path in files:
        if path.suffix not in _EXECUTABLE_SUFFIXES and path.name not in _EXECUTABLE_NAMES:
            continue
        # This file defines the names, so it is the one that must contain them.
        # Excluded by exact name, so the exemption cannot widen by accident.
        if path.name == "test_artifact_paths.py":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        relative = path.relative_to(root)
        for name in _RELOCATED:
            # An entry ending in `/` is already delimited by the slash, and what
            # follows is the rest of the path. A word-boundary guard there would
            # reject every real use (`site/index.html`) and so match nothing.
            for match in re.finditer(_pattern_for(name), text):
                line = text[: match.start()].rsplit("\n", 1)[-1] + text[match.start() :].split("\n", 1)[0]
                if line.lstrip().startswith("#"):
                    continue
                if any(anchor in line for anchor in _ARTIFACT_ANCHORS):
                    continue
                offenders.append(f"{relative}: {line.strip()}")

    return sorted(set(offenders))


def test_site_dir_is_nested_not_the_artifacts_root():
    """`site_dir` must be a subdirectory, because the build empties it first.

    The docs build clears `site_dir` before writing. Pointing it at the artifacts
    directory itself would delete the nox environments, every tool cache and the
    coverage data on each docs build -- and the build would still succeed, so
    nothing would report it.
    """
    site_dir = _site_dir()

    assert site_dir.count("/") >= 1, f"site_dir is {site_dir!r}; it must nest inside the artifacts directory"


def test_nothing_hard_codes_a_relocated_path():
    """No workflow, recipe or script may name a path that moved.

    Scoped to files where a path is acted on, so a hit is always real. This is the
    check that catches a project's OWN file -- a bespoke deploy workflow that still
    tars up `site/`, for instance -- which no template-side test can see.
    """
    offenders = hardcoded_relocated_paths()

    assert not offenders, "these name a path that now lives under the artifacts directory:\n" + "\n".join(offenders)


def test_every_reader_of_the_built_site_agrees_with_mkdocs():
    """`site_dir` in mkdocs.yml is the only thing deciding where the site lands.

    The docs engine has no site-dir flag, so nothing overrides this key and nothing
    warns when a reader disagrees with it.
    """
    site_dir = _site_dir()

    readers = [".readthedocs.yml", ".github/workflows/tests.yml"]
    for name in readers:
        path = _PROJECT / name
        if not path.is_file():
            continue

        text = path.read_text(encoding="utf-8")

        # Judge a file only if it reads the built site at all -- either correctly (it
        # names `site_dir`) or stalely (it names a bare `site/` path). A project may
        # publish some other way and legitimately reference neither.
        #
        # Both halves are load-bearing. The guard was `if "site" not in text`, and a
        # real project failed on it: its `.readthedocs.yml` downloads a prebuilt tarball
        # rather than building, so it genuinely does not read the built site, but the
        # word "site" appears in its prose and in a release name. `_RELOCATED` carries a
        # trailing slash for exactly that reason, six lines above where the guard did not.
        # Testing only for the stale form would be worse still: a correct file names
        # `.artifacts/site/`, which the path pattern deliberately does not match, so the
        # assertion would never once run on a healthy repo.
        reads_built_site = site_dir in text or re.search(_pattern_for("site/"), text)
        if not reads_built_site:
            continue

        assert site_dir in text, f"{name} reads the built site but not at {site_dir!r} from mkdocs.yml `site_dir`"


def test_coverage_upload_names_the_file_coverage_writes():
    """The Codecov `files:` input must name the file the coverage config produces.

    These drifted apart once before and nothing noticed, because the uploader's
    fallback search found the real report and reported success.
    """
    pyproject = (_PROJECT / "pyproject.toml").read_text(encoding="utf-8")
    written = re.search(r"\[tool\.coverage\.xml\][^\[]*?output\s*=\s*\"([^\"]+)\"", pyproject, re.S)
    assert written, "pyproject.toml does not set [tool.coverage.xml] output; the report path is undefined"

    workflow = (_PROJECT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    uploaded = re.search(r"files:\s*'\$\{\{ github\.workspace \}\}/([^']+)'", workflow)
    assert uploaded, "the coverage upload step does not name a file"

    assert uploaded.group(1) == written.group(1), (
        f"coverage upload reads {uploaded.group(1)!r} but the coverage config writes {written.group(1)!r}"
    )


def test_coverage_upload_does_not_fall_back_to_searching():
    """`fail_ci_if_error` only means something with the uploader's search disabled.

    With search on, a `files:` input naming nothing is not an error: the CLI scans
    the workspace, uploads whatever it finds, and the step passes.
    """
    workflow = (_PROJECT / ".github/workflows/tests.yml").read_text(encoding="utf-8")

    assert "disable_search: true" in workflow, (
        "the coverage upload leaves search enabled, so a wrong `files:` path cannot fail the build"
    )


def test_the_scan_can_fail(tmp_path):
    """The scan must actually catch a path someone spells out again.

    A check whose failure path never runs is indistinguishable from one that works.
    Run against a scratch tree, never the live one: falsifying against a real file
    has cost this fleet real edits before.
    """
    planted = tmp_path / "justfile"
    planted.write_text("stale:\n    uvx linkchecker site/index.html\n", encoding="utf-8")

    offenders = hardcoded_relocated_paths(files=[planted], root=tmp_path)

    assert any("linkchecker site/index.html" in offender for offender in offenders), (
        f"the scan missed a hard-coded site path; it reported {offenders}"
    )
