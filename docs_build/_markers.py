"""Marker resolution and the API sidebar TOC, as engine-independent hosts.

This is what ``hooks.on_page_markdown`` and the ``module_toc`` half of
``hooks.on_page_content`` used to do, plus every builder they relied on, now
hosted in a Python-Markdown extension instead of mkdocs hooks. mkdocs and the
successor engine (Zensical) both drive the same Python-Markdown, so this keeps
working when the ``hooks:`` key does not.

Two facts make it possible, both settled by spike (see the change's design):

1. **Loading.** A markdown extension is loaded by *module name* at config time,
   before any hook runs, so ``docs_build/`` must be importable then.
   ``dev-mode-dirs = ["."]`` in the wheel target puts the repo root on
   ``sys.path`` in the editable install, so ``docs_build._markers`` resolves --
   with nothing added to the built wheel.
2. **Page context.** A Preprocessor is handed the ``Markdown`` instance, not the
   page. ``_current_page(md)`` recovers it the same way mkdocstrings does: the
   Zensical page provider if present, else the ``mkdocs-autorefs`` plugin's
   ``current_page``. Writing ``page.meta`` from the Preprocessor reaches the
   template intact -- the mechanism the ``module_toc`` sidebar depends on.

The ``<!-- SUBPAGES -->`` index is built off the filesystem: a markdown extension
never receives mkdocs' ``files`` collection, so it scans the index page's own
directory instead.
"""

import contextlib
import logging
import posixpath
import re
import sys
from pathlib import Path

import yaml
from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

# Loaded by path/name as an extension, ``docs_build/`` is not a package here, so
# put this file's own directory on sys.path and import the build steps and the
# shared git-ref helper as plain modules -- the pattern hooks.py used before it
# was deleted.
sys.path.insert(0, str(Path(__file__).parent))

import _api_pages  # noqa: E402
from _api_pages import (  # noqa: E402
    _get_public_members,
    _get_root_members,
    _get_submodules,
    _qualified_name,
)

# The docs tree is a sibling of this file, so the project root is two up. A
# markdown extension is not handed mkdocs' config, so paths anchor here.
_PROJECT_ROOT = Path(__file__).parent.parent

# Warnings logged under the "mkdocs" logger tree are counted by mkdocs and turn a
# --strict build red. Every marker is silently inert when it does not resolve, so
# warning here is what makes a dead marker a build failure instead of blank space.
log = logging.getLogger("mkdocs.hooks")


def reset_caches():
    """Clear the per-build discovery caches.

    Kept for tests and any caller that rebuilds in-process. A single `mkdocs
    build` fills each cache once and never calls this; `serve.py` calls
    `_api_pages.reset_caches()` directly on a source edit.
    """
    _api_pages.reset_caches()


def _current_page(md):
    """Return the page being rendered, or ``None`` if it cannot be found.

    Under Zensical the page provider is the preprocessor registered as
    ``rendering_context`` (``zensical.extensions.context.ContextPreprocessor``),
    which exposes ``.page`` -- a ``Page`` with ``url``/``path``/``title``/``meta``.
    An earlier version of this function probed a ``zensical_current_page`` key that
    does not exist in Zensical, so every page-context marker silently rendered
    empty at a green ``--strict`` build; read ``.page`` off ``rendering_context``
    instead. Under MkDocs there is no such seam, so reach the ``mkdocs-autorefs``
    plugin's ``current_page`` through the processors it registered on this md
    instance -- exactly how mkdocstrings gets the page.
    """
    with contextlib.suppress(KeyError, TypeError, AttributeError):
        rc = md.preprocessors["rendering_context"]
        if getattr(rc, "page", None) is not None:
            return rc.page

    for registry in (md.treeprocessors, md.inlinePatterns, md.preprocessors):
        for proc in registry:
            plugin = getattr(proc, "_plugin", None) or getattr(proc, "plugin", None)
            if plugin is not None and hasattr(plugin, "current_page"):
                return plugin.current_page
    return None


def _page_src_path(page):
    """Source path of ``page`` under either documentation engine.

    MkDocs pages carry ``page.file.src_path``; Zensical's ``Page`` has
    ``page.path``. Every marker that lists a page's siblings or resolves a
    page-relative link needs this identity, so it must read whichever shape the
    engine in use provides.
    """
    file = getattr(page, "file", None)
    if file is not None and getattr(file, "src_path", None) is not None:
        return file.src_path
    return page.path


def _mkdocs_config():
    """Read ``mkdocs.yml`` for the keys the markers need (``nav``, ``repo_url``).

    A markdown extension gets the handler/extension config, not the mkdocs
    config, so it reads the file directly. ``!!python/name:`` (pymdownx.emoji) and
    ``!ENV`` are tolerated, the same reader ``_source_links`` and ``_api_pages``
    use, so a strict loader does not raise on them.
    """
    config_file = _PROJECT_ROOT / "mkdocs.yml"
    if not config_file.exists():
        return {}

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda _loader, suffix, _node: suffix)
    _Loader.add_constructor("!ENV", lambda _loader, _node: None)
    try:
        return yaml.load(config_file.read_text(encoding="utf-8"), Loader=_Loader) or {}
    except yaml.YAMLError:
        return {}


def _site_root_prefix(page):
    """Relative path from `page`'s rendered URL back to the site root.

    Every link injected is relative, because the site may be served under a
    subpath and `use_directory_urls` makes each page its own directory. A
    hardcoded `../../` only works if the page never moves: a project is free to
    put its API index at `pages/api/index.md` rather than the template's
    `pages/reference/api.md`, and a fixed prefix silently 404s every link on it.
    """
    parts = _page_src_path(page).split("/")
    depth = len(parts) if parts[-1] != "index.md" else len(parts) - 1
    return "../" * depth


def _build_api_table_html(project_root, prefix):
    """Build an HTML <table> for the API index with DataTables init.

    Lists every public class and function across all submodules with
    Name, Type, Module, and Description columns.  The table is initialised
    with jQuery DataTables for client-side filtering and sorting.
    """
    modules = _get_submodules(project_root)

    rows = []
    scans = []
    for mod in modules:
        # Keyed on the module NAME: discovery no longer takes a source path, so
        # the single-file-or-package probe and its `.exists()` guard are gone.
        scans.append((mod["module_name"], _get_public_members(project_root, mod["module_name"])))
    # Symbols exported only from the package root belong to no submodule, so a
    # loop over submodules alone leaves them out of the table entirely.
    scans.append(("", _get_root_members(project_root)))

    for module_name, members in scans:
        module_label = _qualified_name(module_name, "").rstrip(".") or "kedro_dagster"
        # A root export has no module page, and there is nothing to link it to: this
        # pointed at pages/api/, which is only a directory of generated module pages
        # and has no index of its own, so every root export's Module cell was a 404.
        # Nothing catches that -- the cell is raw HTML, which --strict never
        # validates, and only a project with a root-only export renders one.
        module_href = f"{prefix}pages/api/{module_name}/" if module_name else None

        for cls in members["classes"]:
            qualified = _qualified_name(module_name, cls["name"])
            rows.append((cls["name"], "Class", module_label, module_href, cls["doc"], qualified))

        for func in members["functions"]:
            qualified = _qualified_name(module_name, func["name"])
            rows.append((func["name"], "Function", module_label, module_href, func["doc"], qualified))

    rows.sort(key=lambda r: r[0].lower())

    _type_badge_cls = {
        "Class": "api-badge--class",
        "Function": "api-badge--function",
    }

    tbody_lines = []
    for name, kind, module_label, module_href, desc, qualified in rows:
        href = f"{prefix}pages/api/generated/{qualified}/"
        badge_cls = _type_badge_cls.get(kind, "")
        module_cell = f'<a href="{module_href}">{module_label}</a>' if module_href else module_label
        tbody_lines.append(
            f"      <tr>"
            f'<td><a href="{href}"><code>{name}</code></a></td>'
            f'<td><span class="api-badge {badge_cls}">{kind}</span></td>'
            f"<td>{module_cell}</td>"
            f"<td>{desc}</td>"
            f"</tr>"
        )

    tbody = "\n".join(tbody_lines)
    return (
        '<div class="api-table-wrapper">\n'
        '<table id="api-table" class="display" style="width:100%">\n'
        "  <thead>\n"
        "    <tr>\n"
        "      <th>Name</th>\n"
        "      <th>Type</th>\n"
        "      <th>Module</th>\n"
        "      <th>Description</th>\n"
        "    </tr>\n"
        "  </thead>\n"
        "  <tbody>\n"
        f"{tbody}\n"
        "  </tbody>\n"
        "</table>\n"
        "</div>\n"
        "\n"
        "<script>\n"
        "document.addEventListener('DOMContentLoaded', function() {\n"
        '  if (typeof jQuery !== "undefined" && jQuery.fn.DataTable) {\n'
        '    jQuery("#api-table").DataTable({\n'
        "      pageLength: 25,\n"
        '      order: [[0, "asc"]],\n'
        "      columns: [\n"
        "        null,\n"
        "        null,\n"
        "        null,\n"
        "        { orderable: false }\n"
        "      ],\n"
        "      language: {\n"
        '        search: "",\n'
        '        searchPlaceholder: "Filter API reference...",\n'
        '        info: "Showing _START_ to _END_ of _TOTAL_ entries",\n'
        '        lengthMenu: "Show _MENU_",\n'
        "      },\n"
        '      dom: \'<"api-controls"fl>t<"api-footer"ip>\',\n'
        "    });\n"
        "  }\n"
        "});\n"
        "</script>"
    )


# ---------------------------------------------------------------------------
# Marker substitution
# ---------------------------------------------------------------------------


# Every name this extension substitutes. A comment *opening* with one of these is
# a marker; if one survives to the end of `_inject`, it was misspelled. Matched
# without a word boundary so `<!-- GALLERY:quickstart -->` and `<!-- SUBPAGES_FOO
# -->` are both caught, not just the separator-delimited ones.
#
# The net is deliberately the marker namespace and nothing else: it cannot catch
# a typo that mangles the name itself (`<!-- GALLRY -->`), because widening it to
# every upper-case comment would flag ordinary `<!-- TODO -->`s.
_MARKER_NAMES = ("API_TABLE", "SUBPAGES", "GALLERY", "COMPANION_NOTEBOOKS", "EXAMPLES_FOR")
_UNHANDLED_MARKER_RE = re.compile(r"<!--\s*(?:" + "|".join(_MARKER_NAMES) + r")[^>]*-->")


def _warn_on_unhandled_markers(markdown, src_path):
    """Warn about a marker that no substitution above recognised.

    The per-marker warnings only fire for a *well-formed* marker that resolves to
    nothing. A misspelled one is worse and was completely silent: `<!--
    GALLERY:quickstart -->` matches neither the bare nor the sectioned pattern, so
    nothing claimed it, nothing substituted it, and it shipped to the page as a
    raw comment that renders as blank space. Catching the leftovers is the only
    place a typo in the marker namespace can be noticed at all.
    """
    for match in _UNHANDLED_MARKER_RE.finditer(markdown):
        log.warning(
            "%s: unrecognised marker %s -- it renders as blank space. "
            "Known markers: <!-- API_TABLE -->, <!-- SUBPAGES -->, <!-- GALLERY -->, "
            "<!-- GALLERY:section:NAME -->, <!-- COMPANION_NOTEBOOKS -->, <!-- EXAMPLES_FOR:NAME -->.",
            src_path,
            match.group(0),
        )


def _replace_marker(markdown, marker, replacement):
    """Replace ``marker`` with ``replacement``, re-indented to the marker's column.

    A marker nested inside an indented block -- an admonition body, a list item
    -- carries leading whitespace that its replacement has to inherit. A plain
    ``str.replace`` indents only the first line, so every line after it lands at
    column 0 and silently falls out of the enclosing block: the block keeps the
    first line and the rest renders as a sibling. That failure is invisible in
    the markdown and only shows up in the built HTML, which is why it survived
    so long. Matching the indentation keeps the replacement inside whatever the
    author nested it in.
    """
    if marker not in markdown:
        return markdown

    out = []
    for line in markdown.split("\n"):
        stripped = line.strip()
        if stripped != marker:
            # A marker sharing its line with prose is substituted in place; it
            # was never nested, so there is no indentation to match.
            out.append(line.replace(marker, replacement) if marker in line else line)
            continue
        indent = line[: len(line) - len(line.lstrip())]
        if not replacement:
            continue
        if not indent:
            out.append(replacement)
            continue
        # Blank lines stay blank: trailing whitespace on an "empty" line is a
        # lint violation, and markdown does not need it to keep the block open.
        out.extend(indent + rline if rline.strip() else "" for rline in replacement.split("\n"))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Section index (<!-- SUBPAGES -->)
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
_DESCRIPTION_RE = re.compile(r"^description:\s*(.+?)\s*$", re.MULTILINE)


def _nav_entries(config):
    """Map ``src_path`` -> (position in the nav, title the nav gives it).

    The nav is the order the author chose and the order the reader sees in the
    sidebar; an index that lists its pages in a different order than the nav
    beside it reads as a different set of pages. The title is a fallback for a
    page that has no H1 of its own -- see _page_title_and_description.
    """
    entries = {}

    def walk(node, title=None):
        if isinstance(node, str):
            entries.setdefault(node, (len(entries), title))
        elif isinstance(node, list):
            for child in node:
                walk(child)
        elif isinstance(node, dict):
            for key, value in node.items():
                walk(value, key if isinstance(value, str) else None)

    walk(config.get("nav") or [])
    return entries


def _page_title_and_description(abs_path):
    """Pull a page's title and one-line summary from its own source.

    Title is the H1; summary is the frontmatter ``description`` when present,
    else the first prose paragraph. Deriving both from the page keeps the index
    honest -- there is no second copy of the title to drift out of sync.
    """
    try:
        text = Path(abs_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, ""

    description = ""
    frontmatter = _FRONTMATTER_RE.match(text)
    if frontmatter:
        found = _DESCRIPTION_RE.search(frontmatter.group(1))
        if found:
            description = found.group(1).strip().strip("\"'")
        text = text[frontmatter.end() :]

    heading = _H1_RE.search(text)
    if not heading:
        return None, description
    title = heading.group(1).strip()

    if not description:
        body = text[heading.end() :]
        for raw_block in body.split("\n\n"):
            block = raw_block.strip()
            # Skip anything that is not prose: nested headings, markers,
            # admonitions, code fences, tables, images, lists.
            if not block or block[0] in "#<!|-*>`" or block.startswith("!!!"):
                continue
            description = " ".join(block.split())
            break

    return title, description


def _build_subpages_list(config, page, project_root):
    """List the pages this index introduces, as ``- [Title](slug.md): summary``.

    Off the filesystem: the hook version iterated mkdocs' ``files`` collection,
    which a markdown extension is never handed. It scans the index page's own
    directory instead -- direct children only, since a nested section owns its
    own index -- and reads each sibling's title and summary out of its own
    source, so there is no second copy of either to drift.
    """
    src = _page_src_path(page)
    directory = posixpath.dirname(src)
    dir_path = project_root / "docs" / directory

    siblings = []
    for candidate in sorted(dir_path.glob("*.md")):
        name = candidate.name
        candidate_src = f"{directory}/{name}" if directory else name
        if candidate_src == src or name == "index.md":
            continue
        siblings.append((candidate_src, candidate))

    if not siblings:
        log.warning("<!-- SUBPAGES --> on %s, which has no sibling pages to list.", src)
        return "<!-- no subpages -->\n"

    entries = _nav_entries(config)

    # The index enumerates sibling *files*; the sidebar comes from mkdocs.yml.
    # When the two disagree the index quietly papers over it -- an entry dropped
    # from the nav still appears here, so the page stays reachable by link while
    # vanishing from navigation. mkdocs reports not-in-nav pages at INFO, which
    # --strict does not fail on, so nothing else says a word.
    orphans = sorted(candidate_src for candidate_src, _ in siblings if candidate_src not in entries)
    if orphans:
        log.warning(
            "%s lists %s, which %s missing from the nav in mkdocs.yml -- the page is linked but "
            "unreachable by navigation.",
            src,
            ", ".join(orphans),
            "is" if len(orphans) == 1 else "are",
        )

    rows = []
    for candidate_src, candidate in siblings:
        title, description = _page_title_and_description(str(candidate))
        position, nav_title = entries.get(candidate_src, (len(entries) + 1, None))
        if title is None:
            # A page can legitimately have no H1 in its own source: a bare
            # `--8<-- "CHANGELOG.md"` include grows one only once snippets
            # expand, which is after this runs. The nav already names such a
            # page, so prefer its name over dropping the page from its own index.
            title = nav_title
        if title is None:
            log.warning(
                "%s has no H1 heading and no nav title; omitted from the %s index.",
                candidate_src,
                src,
            )
            continue
        rows.append((position, title, posixpath.basename(candidate_src), description))

    if not rows:
        return "<!-- no subpages -->\n"

    rows.sort(key=lambda row: (row[0], row[1]))
    lines = [f"- [{title}]({slug})" + (f": {desc}" if desc else "") for _, title, slug, desc in rows]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# API sidebar module TOC (page.meta, read by the api-submodule template)
# ---------------------------------------------------------------------------


def _build_module_toc(project_root, current_src_path=None, prefix=None):
    """Build the module TOC list used by the api-submodule sidebar template.

    ``current_src_path`` marks the matching entry ``active``; ``prefix`` makes
    every url site-root relative, so the TOC is correct on any page that renders
    it. Reads the generated module pages under ``docs/pages/api/`` off the
    filesystem -- they exist by the time this runs, the prebuild step generates
    them before mkdocs is invoked.
    """
    docs_dir = project_root / "docs"
    api_dir = docs_dir / "pages" / "api"

    modules = _get_submodules(project_root)
    module_toc = []

    for mod in modules:
        md_filename = f"{mod['module_name']}.md"
        md_path = api_dir / md_filename
        if not md_path.exists():
            continue

        page_url = f"{prefix}pages/api/{md_filename.replace('.md', '/')}"
        active = current_src_path == f"pages/api/{md_filename}" if current_src_path else False

        entry = {
            "title": f"kedro_dagster.{mod['module_name']}",
            "url": page_url,
            "active": active,
            "children": [],
        }

        # Parse h3 subsections from the module markdown for sidebar children
        content = md_path.read_text(encoding="utf-8")
        for m in re.finditer(r"^###\s+(.+)$", content, re.MULTILINE):
            sub_title = m.group(1).strip()
            sub_slug = re.sub(r"[^\w]+", "-", sub_title.lower()).strip("-")
            child_url = f"{page_url}#{sub_slug}" if not active else f"#{sub_slug}"
            entry["children"].append({"title": sub_title, "url": child_url, "active": False})

        module_toc.append(entry)

    return module_toc


def _set_module_toc(page):
    """Attach the API sidebar module TOC to ``page.meta`` for the template.

    The api-index / api-submodule pages declare their template in frontmatter, so
    ``page.meta`` already carries it by the time this Preprocessor runs. Keyed on
    the declared template, not on where the page sits: the index is wherever a
    project put it, and a hardcoded ``pages/reference/api.md`` leaves a relocated
    index with an empty sidebar and nothing erroring.
    """
    meta = getattr(page, "meta", None)
    if not isinstance(meta, dict):
        return
    if meta.get("template") in ("api-index.html", "api-submodule.html"):
        meta["module_toc"] = _build_module_toc(
            _PROJECT_ROOT, current_src_path=_page_src_path(page), prefix=_site_root_prefix(page)
        )


def _inject(markdown, page, config=None):
    """Resolve every marker in ``markdown`` for ``page`` and return the result.

    This is the body of the retired ``on_page_markdown`` hook. ``config`` is read
    from ``mkdocs.yml`` when not supplied (the Preprocessor path); tests pass one
    to exercise a specific nav or ``repo_url`` without touching the file.
    """
    if config is None:
        config = _mkdocs_config()
    project_root = _PROJECT_ROOT
    prefix = _site_root_prefix(page)

    # API_TABLE placeholder
    if "<!-- API_TABLE -->" in markdown:
        table = _build_api_table_html(project_root, prefix)
        markdown = markdown.replace("<!-- API_TABLE -->", table)

    # SUBPAGES placeholder
    if "<!-- SUBPAGES -->" in markdown:
        markdown = _replace_marker(markdown, "<!-- SUBPAGES -->", _build_subpages_list(config, page, project_root))

    # Strip EXAMPLES_FOR placeholders when examples are disabled
    markdown = re.sub(r"<!-- EXAMPLES_FOR:[\w.]+ -->\n?", "", markdown)

    _warn_on_unhandled_markers(markdown, _page_src_path(page))

    return markdown


class _MarkerPreprocessor(Preprocessor):
    """Resolve markers and set the sidebar TOC once per page, before HTML stashing."""

    def run(self, lines):
        """Inject markers into the page, or pass it through if the page is unknown."""
        page = _current_page(self.md)
        if page is None:
            # No page context means no SUBPAGES/COMPANION resolution and no
            # prefix for URL rewrites. Passing the lines through unchanged is
            # safer than resolving against a guessed page.
            return lines
        _set_module_toc(page)
        return _inject("\n".join(lines), page).split("\n")


class MarkerExtension(Extension):
    """Register the marker Preprocessor high enough to see raw HTML comments."""

    def extendMarkdown(self, md):
        """Register at priority 100, above Python-Markdown's html_block (~20).

        The markers are HTML comments. The stock ``html_block`` preprocessor
        stashes HTML out of the stream at priority 20, so a lower priority would
        never see ``<!-- API_TABLE -->`` as text. Running first keeps them
        visible.
        """
        md.preprocessors.register(_MarkerPreprocessor(md), "docs_markers", 100)


def makeExtension(**_kwargs):
    """Entry point Python-Markdown calls when loading this by module name."""
    return MarkerExtension()
