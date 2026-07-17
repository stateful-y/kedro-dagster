"""MkDocs hooks for post-build processing."""

import ast
import fnmatch
import importlib.util
import logging
import posixpath
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

# Warnings logged under the "mkdocs" logger tree are counted by mkdocs and turn
# a --strict build red. Every marker this file understands is silently inert
# when it does not resolve -- a placeholder that renders nothing looks exactly
# like a page that never had one. Warning here is what makes a dead marker a
# build failure instead of a blank space nobody notices.
log = logging.getLogger("mkdocs.hooks")

# Module-level caches. MkDocs loads hooks as plugin instances and does not
# reload the module between builds, so these live for the whole process --
# under `mkdocs serve` an unreset cache serves stale content for the rest of the
# session. Every cache is cleared per build by on_config() below.
#
# Naming is load-bearing: the reset and its test discover caches by the
# `_CACHE` suffix, so a cache named otherwise escapes both, silently.
_SUBMODULE_CACHE = None
_API_NAME_LOOKUP_CACHE = None
_GLOSSARY_TERMS_CACHE = None


def _get_submodules(project_root):
    """Discover public submodules in the package (cached).

    Scans ``src/kedro_dagster/`` for ``.py`` files (excluding ``__init__``)
    and sub-packages with an ``__init__.py``.  Returns a sorted list of dicts
    with *module_name* and *module_doc* keys.
    """
    global _SUBMODULE_CACHE  # noqa: PLW0603
    if _SUBMODULE_CACHE is not None:
        return _SUBMODULE_CACHE

    pkg_dir = project_root / "src" / "kedro_dagster"
    if not pkg_dir.exists():
        _SUBMODULE_CACHE = []
        return _SUBMODULE_CACHE

    modules = []
    # Single-file modules
    for py_file in sorted(pkg_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = py_file.stem
        module_doc = _extract_module_docstring(py_file)
        modules.append({"module_name": module_name, "module_doc": module_doc})

    # Sub-packages (directories with __init__.py)
    for child in sorted(pkg_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("_"):
            continue
        init = child / "__init__.py"
        if init.exists():
            module_doc = _extract_module_docstring(init)
            modules.append({"module_name": child.name, "module_doc": module_doc})

    _SUBMODULE_CACHE = modules
    return _SUBMODULE_CACHE


def _qualified_name(module_name, member_name):
    """Public dotted path of a member.

    A symbol exported only from the package root has no module segment --
    `pkg.Name`, not `pkg..Name` -- which is the whole reason code keyed on a
    submodule silently drops it.
    """
    parts = ["kedro_dagster", module_name, member_name]
    return ".".join(part for part in parts if part)


def _module_source(pkg_dir, module_name):
    """The file backing a submodule: ``name.py``, else ``name/__init__.py``."""
    mod_file = pkg_dir / f"{module_name}.py"
    if not mod_file.exists():
        mod_file = pkg_dir / module_name / "__init__.py"
    return mod_file


def _get_root_members(project_root):
    """Public symbols the package exports only from its own ``__init__.py``.

    ``_get_submodules`` skips every ``_``-prefixed name, which is right for
    private modules and also silently excludes ``__init__.py`` itself. A package
    that keeps a base class in ``_base.py`` and re-exports it from the root --
    an ordinary layout, and what sklearn does -- therefore has a public symbol
    that belongs to no submodule, reaches no page, and never appears in the API
    table. Nothing reports it: yohou-nixtla ships 18 names in ``__all__`` and the
    table lists 17.

    Their public path has no module segment (``pkg.Name``, not
    ``pkg.module.Name``), which is exactly why they fall through code keyed on a
    submodule. Names a real submodule already publishes keep their module path;
    only the homeless ones are adopted here.
    """
    pkg_dir = project_root / "src" / "kedro_dagster"
    init_file = pkg_dir / "__init__.py"
    if not init_file.exists():
        return {"classes": [], "functions": []}

    covered = set()
    for mod in _get_submodules(project_root):
        members = _get_public_members(_module_source(pkg_dir, mod["module_name"]), pkg_dir)
        covered.update(entry["name"] for entry in members["classes"] + members["functions"])

    root = _get_public_members(init_file, pkg_dir)
    return {key: [entry for entry in root[key] if entry["name"] not in covered] for key in ("classes", "functions")}


def _extract_module_docstring(py_file):
    """Extract the module-level docstring from a Python file."""
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree)
        if docstring:
            # Return only the first line
            return docstring.strip().split("\n")[0]
    except (SyntaxError, UnicodeDecodeError):
        pass
    return ""


def _get_module_members(py_file):
    """Discover public classes and functions in a Python module via AST.

    Returns a dict with *classes* and *functions* lists.  Each entry is a dict
    with *name* and *doc* (first line of the docstring, or empty string).
    """
    classes = []
    functions = []
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return {"classes": classes, "functions": functions}

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            doc = ast.get_docstring(node) or ""
            classes.append({"name": node.name, "doc": doc.strip().split("\n")[0]})
        elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and not node.name.startswith("_"):
            doc = ast.get_docstring(node) or ""
            functions.append({"name": node.name, "doc": doc.strip().split("\n")[0]})

    return {"classes": classes, "functions": functions}


def _get_dunder_all(tree):
    """Return the set of names listed in ``__all__``, or None if absent."""
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "__all__":
                if not isinstance(node.value, ast.List | ast.Tuple):
                    return None
                return {e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return None


def _iter_reexport_nodes(tree):
    """Yield ``ImportFrom`` nodes that re-export names from a package.

    Covers top-level imports and imports guarded by a top-level ``try`` block,
    which is the conventional way to expose an optional extra::

        try:
            from mypkg.neural._impl import Forecaster
        except ImportError as err:
            raise ImportError("install mypkg[neural]") from err

    Only the ``try`` body is walked: names in an ``except`` handler are the
    fallback path, not the package's advertised API.
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom):
            yield node
        elif isinstance(node, ast.Try):
            for inner in node.body:
                if isinstance(inner, ast.ImportFrom):
                    yield inner


def _resolve_import_from(node, init_file, pkg_dir):
    """Map an ``ImportFrom`` node to the file that declares its names.

    Handles relative imports (``from .naive import X``) and absolute imports
    rooted at this package (``from mypkg.stats._base import X``).  Returns
    None for imports that leave the package, which is what keeps incidental
    third-party imports (``from pathlib import Path``) out of the API.
    """
    if node.level:
        base = init_file.parent
        for _ in range(node.level - 1):
            base = base.parent
        parts = node.module.split(".") if node.module else []
    else:
        if not node.module:
            return None
        parts = node.module.split(".")
        if parts[0] != pkg_dir.name:
            return None
        base = pkg_dir
        parts = parts[1:]

    target = base
    for part in parts:
        target = target / part
    for candidate in (target.with_suffix(".py"), target / "__init__.py"):
        if candidate.exists():
            return candidate
    return None


def _resolve_external_module(module_name):
    """Locate a module that lives outside this package.

    A package may deliberately re-export a dependency's symbol -- a convenience
    shim such as ``from otherpkg.thing import Widget`` under its own ``__all__``.
    That name is part of *this* package's public API, but no file under
    ``pkg_dir`` declares it, so ``_resolve_import_from`` cannot reach it and the
    symbol would silently vanish from the index and lose its page.

    ``find_spec`` locates the module's source file so the kind and docstring can
    be read from it like any other module, rather than guessed.  It imports the
    *parent* package to do so, which is why this is only ever consulted for a
    name the author listed in ``__all__``: an incidental ``from pathlib import
    Path`` must never reach here.  Anything that does not resolve to readable
    source is skipped, not invented.
    """
    try:
        spec = importlib.util.find_spec(module_name)
    except (ImportError, AttributeError, ValueError):
        return None
    if spec is None or not spec.origin or not spec.origin.endswith(".py"):
        return None
    return Path(spec.origin)


def _reexports_a_dunder_all_name(node, exported):
    """Whether this ImportFrom binds any name the package advertises in ``__all__``."""
    return any((alias.asname or alias.name) in exported for alias in node.names if alias.name != "*")


def _get_reexported_members(init_file, pkg_dir):
    """Discover members a module exposes by re-export rather than by declaring them.

    A re-exporting ``__init__.py`` declares no classes or functions of its own,
    so an AST scan of that file alone finds nothing.  This resolves each
    ``ImportFrom`` binding to its declaring module and lifts the name's kind
    and docstring from there.

    ``__all__`` acts as a *filter*, not an authority: a name is exposed only if
    it is listed there (when present) *and* resolves to a class or function in
    its declaring module.  Constants and other exports are excluded, because
    only classes and functions get generated pages.

    A plain module can be a re-export shim too, so this is not limited to
    ``__init__.py`` -- but for one, an import is normally a private detail
    (``from .base import Helper`` to use it), not an advertisement.  Only an
    explicit ``__all__`` marks a plain module's imports as its public surface;
    without one, nothing here is re-exported.  An ``__init__.py`` re-exports by
    convention, so it needs no such marker.
    """
    try:
        tree = ast.parse(init_file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return {"classes": [], "functions": []}

    exported = _get_dunder_all(tree)
    if exported is None and init_file.name != "__init__.py":
        return {"classes": [], "functions": []}
    classes = []
    functions = []
    seen = set()

    for node in _iter_reexport_nodes(tree):
        decl_file = _resolve_import_from(node, init_file, pkg_dir)
        if decl_file is None:
            # The import leaves the package. That is normally an incidental
            # third-party import and must stay out of the API -- unless the
            # author advertised the name in __all__, which makes it this
            # package's public API no matter where it was declared.
            if exported is None or node.level or not node.module or not _reexports_a_dunder_all_name(node, exported):
                continue
            decl_file = _resolve_external_module(node.module)
            if decl_file is None:
                continue
        decl_members = None
        for alias in node.names:
            if alias.name == "*":
                continue
            exposed = alias.asname or alias.name
            if exposed.startswith("_") or exposed in seen:
                continue
            if exported is not None and exposed not in exported:
                continue
            if decl_members is None:
                decl_members = _get_module_members(decl_file)
            for bucket, entries in (("classes", decl_members["classes"]), ("functions", decl_members["functions"])):
                match = next((e for e in entries if e["name"] == alias.name), None)
                if match is None:
                    continue
                (classes if bucket == "classes" else functions).append({
                    "name": exposed,
                    "doc": match["doc"],
                    "origin": str(decl_file),
                    "reexported": True,
                })
                seen.add(exposed)
                break

    return {"classes": classes, "functions": functions}


def _get_public_members(mod_file, pkg_dir):
    """Public classes and functions of a module, including re-exported ones.

    Each entry carries *origin* (the file that declares the symbol) and
    *reexported*, so the name lookup can tell one symbol reachable by two paths
    from two different symbols that happen to share a short name.
    """
    if not mod_file.exists():
        return {"classes": [], "functions": []}
    members = _get_module_members(mod_file)
    for key in ("classes", "functions"):
        for entry in members[key]:
            entry.setdefault("origin", str(mod_file))
            entry.setdefault("reexported", False)
    reexported = _get_reexported_members(mod_file, pkg_dir)
    declared = {e["name"] for e in members["classes"] + members["functions"]}
    for key in ("classes", "functions"):
        members[key].extend(e for e in reexported[key] if e["name"] not in declared)
    return members


def _get_api_name_lookup(project_root):
    """Map a symbol's short name to the qualified name of its API page (cached).

    Shared by See Also resolution and example-notebook cross-referencing so the
    two cannot disagree about what a symbol is called.  Built by static
    analysis only; the package is never imported.

    When one symbol is reachable by two paths -- declared in a module and
    re-exported by a package -- the published path wins: that is the name users
    write, and the one whose page they expect.

    When a short name identifies two genuinely different symbols, it is omitted
    rather than resolved arbitrarily: consumers turn this straight into a URL,
    and a wrong link is worse than no link.
    """
    global _API_NAME_LOOKUP_CACHE  # noqa: PLW0603
    if _API_NAME_LOOKUP_CACHE is not None:
        return _API_NAME_LOOKUP_CACHE

    pkg_dir = project_root / "src" / "kedro_dagster"
    candidates = {}
    scans = []
    for mod in _get_submodules(project_root):
        scans.append((mod["module_name"], _get_public_members(_module_source(pkg_dir, mod["module_name"]), pkg_dir)))
    scans.append(("", _get_root_members(project_root)))
    for module_name, members in scans:
        for entry in members["classes"] + members["functions"]:
            qualified = _qualified_name(module_name, entry["name"])
            candidates.setdefault(entry["name"], []).append({
                "qualified": qualified,
                "origin": entry.get("origin"),
                "reexported": entry.get("reexported", False),
            })

    lookup = {}
    for name, cands in candidates.items():
        if len({c["origin"] for c in cands}) > 1:
            continue  # genuinely different symbols share this short name
        published = sorted(c["qualified"] for c in cands if c["reexported"])
        if published:
            lookup[name] = published[0]
        elif len(cands) == 1:
            lookup[name] = cands[0]["qualified"]

    _API_NAME_LOOKUP_CACHE = lookup
    return _API_NAME_LOOKUP_CACHE


def _build_members_tables(package_name, module_name, members):
    """Build markdown tables linking to generated per-class/function pages.

    Produces a markdown string with ``### Classes`` and ``### Functions``
    sections, each containing a markdown table with links to dedicated
    pages under ``generated/``, matching the yohou submodule page style.
    """
    sections = []

    if members["classes"]:
        lines = [
            "### Classes",
            "",
            "| Name | Description |",
            "|------|-------------|",
        ]
        for cls in members["classes"]:
            qualified = f"{package_name}.{module_name}.{cls['name']}"
            link = f"[`{cls['name']}`](generated/{qualified}.md)"
            lines.append(f"| {link} | {cls['doc']} |")
        sections.append("\n".join(lines))

    if members["functions"]:
        lines = [
            "### Functions",
            "",
            "| Name | Description |",
            "|------|-------------|",
        ]
        for func in members["functions"]:
            qualified = f"{package_name}.{module_name}.{func['name']}"
            link = f"[`{func['name']}`](generated/{qualified}.md)"
            lines.append(f"| {link} | {func['doc']} |")
        sections.append("\n".join(lines))

    if not sections:
        return ""

    return "\n\n".join(sections)


def _write_member_pages(generated_dir, page_template, module_name, members):
    """Write one detail page per public class/function. Returns how many."""
    written = 0
    for kind in ("classes", "functions"):
        for entry in members[kind]:
            qualified = _qualified_name(module_name, entry["name"])
            page = generated_dir / f"{qualified}.md"
            page.write_text(page_template.format(name=entry["name"], qualified=qualified))
            written += 1
    return written


def _generate_api_pages(project_root):
    """Generate per-submodule overview pages and per-class/function detail pages.

    Reads ``docs/api-submodule.html`` and writes one ``.md`` overview page per
    discovered submodule into ``docs/pages/api/``.  Each overview page uses
    ``### Classes`` / ``### Functions`` headings with markdown tables linking
    to dedicated per-member pages under ``docs/pages/api/generated/``.
    """
    template_file = project_root / "docs" / "api-submodule.html"
    if not template_file.exists():
        print("[hooks] docs/api-submodule.html not found, skipping API page generation")
        return

    template = template_file.read_text(encoding="utf-8")
    api_dir = project_root / "docs" / "pages" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    generated_dir = api_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    # Clean stale generated pages
    for old in generated_dir.glob("*.md"):
        old.unlink()

    pkg_dir = project_root / "src" / "kedro_dagster"
    modules = _get_submodules(project_root)

    _page_template = (
        "---\n"
        "template: api-page.html\n"
        "---\n\n"
        "# {name}\n\n"
        "::: {qualified}\n"
        "    options:\n"
        "      show_root_heading: true\n"
        "      show_source: true\n"
        "      members_order: source\n"
        "\n"
        "<!-- EXAMPLES_FOR:{qualified} -->\n"
    )

    member_count = 0
    for mod in modules:
        # Determine the source file for member discovery
        mod_file = pkg_dir / f"{mod['module_name']}.py"
        if not mod_file.exists():
            mod_file = pkg_dir / mod["module_name"] / "__init__.py"

        members = _get_public_members(mod_file, pkg_dir)

        # Generate submodule overview page with tables
        members_tables = _build_members_tables(
            "kedro_dagster",
            mod["module_name"],
            members,
        )

        content = template.format(
            package_name="kedro_dagster",
            module_name=mod["module_name"],
            module_doc=mod["module_doc"],
            members_tables=members_tables,
        )
        dest = api_dir / f"{mod['module_name']}.md"
        dest.write_text(content, encoding="utf-8")
        print(f"[hooks] generated api page: pages/api/{mod['module_name']}.md")

        # Generate per-class/function detail pages
        member_count += _write_member_pages(generated_dir, _page_template, mod["module_name"], members)

    # Symbols exported only from the package root have no submodule and so no
    # module page; they still need a detail page for the table and See Also to
    # link at. Without this the link resolves to nothing and, being raw HTML,
    # nothing validates it.
    member_count += _write_member_pages(generated_dir, _page_template, "", _get_root_members(project_root))

    if member_count:
        print(f"[hooks] generated {member_count} API member pages in pages/api/generated/")


def _site_root_prefix(page):
    """Relative path from `page`'s rendered URL back to the site root.

    Every link this file injects is relative, because the site may be served
    under a subpath and `use_directory_urls` makes each page its own directory.
    A hardcoded `../../` only works if the page never moves: a project is free
    to put its API index at `pages/api/index.md` rather than the template's
    `pages/reference/api.md`, and a fixed prefix silently 404s every link on it.
    """
    parts = page.file.src_path.split("/")
    depth = len(parts) if parts[-1] != "index.md" else len(parts) - 1
    return "../" * depth


def _build_api_table_html(project_root, prefix):
    """Build an HTML <table> for the API index with DataTables init.

    Lists every public class and function across all submodules with
    Name, Type, Module, and Description columns.  The table is initialised
    with jQuery DataTables for client-side filtering and sorting.
    """
    modules = _get_submodules(project_root)
    pkg_dir = project_root / "src" / "kedro_dagster"

    rows = []
    scans = []
    for mod in modules:
        mod_file = _module_source(pkg_dir, mod["module_name"])
        if not mod_file.exists():
            continue
        scans.append((mod["module_name"], _get_public_members(mod_file, pkg_dir)))
    # Symbols exported only from the package root belong to no submodule, so a
    # loop over submodules alone leaves them out of the table entirely.
    scans.append(("", _get_root_members(project_root)))

    for module_name, members in scans:
        module_label = _qualified_name(module_name, "").rstrip(".") or "kedro_dagster"
        # A root export has no module page to point at; the API index is its home.
        module_href = f"{prefix}pages/api/{module_name}/" if module_name else f"{prefix}pages/api/"

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
        tbody_lines.append(
            f"      <tr>"
            f'<td><a href="{href}"><code>{name}</code></a></td>'
            f'<td><span class="api-badge {badge_cls}">{kind}</span></td>'
            f'<td><a href="{module_href}">{module_label}</a></td>'
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


# Every name this file substitutes. A comment *opening* with one of these is a
# marker; if one survives to the end of on_page_markdown, it was misspelled.
# Matched without a word boundary so `<!-- GALLERY:quickstart -->` and
# `<!-- SUBPAGES_FOO -->` are both caught, not just the separator-delimited ones.
#
# The net is deliberately the marker namespace and nothing else: it cannot catch
# a typo that mangles the name itself (`<!-- GALLRY -->`), because widening it to
# every upper-case comment would flag ordinary `<!-- TODO -->`s. The realistic
# mistake is right name, wrong syntax -- which is exactly what shipped.
_MARKER_NAMES = ("API_TABLE", "SUBPAGES", "GALLERY", "COMPANION_NOTEBOOKS", "EXAMPLES_FOR")
_UNHANDLED_MARKER_RE = re.compile(r"<!--\s*(?:" + "|".join(_MARKER_NAMES) + r")[^>]*-->")


def _warn_on_unhandled_markers(markdown, src_path):
    """Warn about a marker that no substitution above recognised.

    The per-marker warnings only fire for a *well-formed* marker that resolves to
    nothing -- an unknown gallery section, an index with no children. A
    misspelled one is worse and was completely silent: `<!-- GALLERY:quickstart
    -->` matches neither the bare nor the sectioned pattern, so nothing claimed
    it, nothing substituted it, and it shipped to the page as a raw comment that
    renders as blank space. It cannot even be reported by the code that would
    have handled it, because that code never sees it. Catching the leftovers is
    the only place a typo in the marker namespace can be noticed at all.
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


def _build_subpages_list(config, page, files):
    """List the pages this index page introduces, as ``- [Title](slug.md): summary``.

    Generated rather than hand-written: an index is the one page guaranteed to
    fall behind, because adding a page elsewhere is what makes it stale, and
    nothing fails when it does.
    """
    src = page.file.src_path
    directory = posixpath.dirname(src)

    siblings = []
    for candidate in files:
        candidate_src = getattr(candidate, "src_path", "")
        if not candidate_src.endswith(".md") or candidate_src == src:
            continue
        # Direct children only: a nested section owns its own index.
        if posixpath.dirname(candidate_src) != directory:
            continue
        if posixpath.basename(candidate_src) == "index.md":
            continue
        siblings.append(candidate)

    if not siblings:
        log.warning("<!-- SUBPAGES --> on %s, which has no sibling pages to list.", src)
        return "<!-- no subpages -->\n"

    entries = _nav_entries(config)

    # The index enumerates sibling *files*; the sidebar comes from mkdocs.yml.
    # When the two disagree the index quietly papers over it -- an entry dropped
    # from the nav still appears here, so the page stays reachable by link while
    # vanishing from navigation. mkdocs itself reports not-in-nav pages at INFO,
    # which --strict does not fail on, so nothing else says a word. A copier
    # update deleted a real nav entry exactly this way and every other guard
    # passed it.
    orphans = sorted(s.src_path for s in siblings if s.src_path not in entries)
    if orphans:
        log.warning(
            "%s lists %s, which %s missing from the nav in mkdocs.yml -- the page is linked but "
            "unreachable by navigation.",
            src,
            ", ".join(orphans),
            "is" if len(orphans) == 1 else "are",
        )

    rows = []
    for sibling in siblings:
        title, description = _page_title_and_description(sibling.abs_src_path)
        position, nav_title = entries.get(sibling.src_path, (len(entries) + 1, None))
        if title is None:
            # A page can legitimately have no H1 in its own source: a bare
            # `--8<-- "CHANGELOG.md"` include grows one only once snippets
            # expand, which is after this runs. The nav already names such a
            # page, and that name is what the sidebar shows, so prefer it over
            # dropping the page from its own index.
            title = nav_title
        if title is None:
            log.warning(
                "%s has no H1 heading and no nav title; omitted from the %s index.",
                sibling.src_path,
                src,
            )
            continue
        rows.append((position, title, posixpath.basename(sibling.src_path), description))

    if not rows:
        return "<!-- no subpages -->\n"

    rows.sort(key=lambda row: (row[0], row[1]))
    lines = [f"- [{title}]({slug})" + (f": {desc}" if desc else "") for _, title, slug, desc in rows]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# API sidebar module TOC
# ---------------------------------------------------------------------------


def _build_module_toc(config, current_src_path=None, prefix=None):
    """Build the module TOC list used by the api-submodule sidebar template.

    Parameters
    ----------
    config : dict
        MkDocs config with ``docs_dir``.
    current_src_path : str or None
        Source path of the current page (e.g. ``pages/api/hello.md``).
        When set, the matching entry gets ``active: True``.

    Returns
    -------
    list[dict]
        TOC entries with keys *title*, *url*, *children*, and optionally
        *active*.
    """
    docs_dir = Path(config["docs_dir"])
    api_dir = docs_dir / "pages" / "api"
    project_root = docs_dir.parent

    modules = _get_submodules(project_root)
    module_toc = []

    for mod in modules:
        md_filename = f"{mod['module_name']}.md"
        md_path = api_dir / md_filename
        if not md_path.exists():
            continue

        # Site-root relative, so the TOC is correct on any page that renders it.
        # The old form branched on whether the current page was the API index and
        # hardcoded that index's depth -- which silently 404s for a project that
        # keeps its index somewhere else.
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


# ---------------------------------------------------------------------------
# API page content post-processing
# ---------------------------------------------------------------------------

_GIT_REF_CACHE = None


def _get_git_ref():
    """Return the current git commit hash (short) for GitHub source links.

    Falls back to ``"main"`` when git is unavailable or the working directory
    is not a repository.  The result is cached for the lifetime of the build.
    """
    global _GIT_REF_CACHE  # noqa: PLW0603
    if _GIT_REF_CACHE is not None:
        return _GIT_REF_CACHE
    try:
        _GIT_REF_CACHE = subprocess.check_output(  # noqa: S603
            ["git", "rev-parse", "HEAD"],  # noqa: S607
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        _GIT_REF_CACHE = "main"
    return _GIT_REF_CACHE


# Numpydoc section types to surface in the TOC.
_DOC_SECTION_TITLE_SLUGS = {
    "Parameters": "parameters",
    "Attributes": "attributes",
    "Returns": "returns",
    "Raises": "raises",
    "Examples": "doc-examples",
}
_DETAIL_SECTION_SLUGS = {
    "note": ("notes", "Notes"),
    "see-also": ("see-also", "See Also"),
    "references": ("references", "References"),
}


_SEE_ALSO_BLOCK_RE = re.compile(r'<details\s+class="see-also"[^>]*>.*?</details>', re.DOTALL)
# An entry's name sits at the START of its line -- mkdocstrings renders one entry
# per line inside the paragraph. Anchoring here is what keeps a colon-terminated
# word in an entry's DESCRIPTION ("Target : Note: see below") from being treated
# as another entry and linked.
_SEE_ALSO_ENTRY_RE = re.compile(r"^(\s*)(<code>[^<]+</code>|[A-Za-z_][\w.]*)(\s*:)")


# A See Also entry opens a line with a name and a colon. The name may already be
# a link (mkdocstrings resolved it) or bare (the linkifier is about to). Anything
# else on its own line is a continuation of the previous entry's description.
_SEE_ALSO_ENTRY_START_RE = re.compile(
    r"""^\s*(?:
        <a\s[^>]*>.*?</a>          # already-linked name
      | <autoref[^>]*>.*?</autoref>
      | <code>[^<]+</code>
      | [A-Za-z_][\w.]*
    )\s*:""",
    re.VERBOSE,
)


def _split_see_also_entries(inner):
    """Split a numpydoc See Also paragraph into one string per entry.

    numpydoc puts one entry per source line; a long description wraps onto
    continuation lines that carry no name of their own, and those belong to the
    entry above rather than becoming entries in their own right.
    """
    entries: list[list[str]] = []
    for line in inner.split("\n"):
        if not line.strip():
            continue
        if _SEE_ALSO_ENTRY_START_RE.match(line) or not entries:
            entries.append([line.strip()])
        else:
            entries[-1].append(line.strip())
    return [" ".join(parts) for parts in entries]


def _resolve_see_also_url(name):
    """Resolve a See Also entry naming a project symbol to a URL, or None.

    A dotted name whose leading segment is not this package is external and is
    not resolved here -- see ``_external_autoref`` for why.

    Classifying by leading segment is the only rule that works: the project
    lookup is keyed by *short* name, so a dotted external name always misses it,
    and stripping the qualifier first would let ``sklearn.linear_model.Ridge``
    collide with a project symbol called ``Ridge``.
    """
    package = "kedro_dagster"
    if "." in name and name.split(".", 1)[0] != package:
        return None

    short_name = name.rsplit(".", 1)[-1]
    project_root = Path(__file__).parent.parent
    qualified = _get_api_name_lookup(project_root).get(short_name)
    return f"../{qualified}/" if qualified is not None else None


def _external_autoref(name, title):
    """Defer an external name to autorefs, which resolves it later.

    External names cannot be resolved here: mkdocstrings registers downloaded
    inventories into the autorefs URL map, but autorefs applies them in its
    ``on_env`` hook -- after ``on_page_content`` runs.  Asking for the URL now
    raises ``KeyError`` even when the inventory is configured.

    So emit autorefs' own markup and let it resolve at the right time.  The
    ``optional`` attribute is what keeps an unresolvable name quiet: autorefs
    logs it at debug level and renders the title as plain text, rather than
    recording it as an unmapped reference and warning (which would fail a
    ``--strict`` build for a docstring that names something undocumented).

    Only dotted names get here.  A bare name is not offered to autorefs: it
    could resolve to an unrelated symbol that happens to share the name in some
    configured inventory, and a wrong link is worse than no link.
    """
    return f'<autoref optional identifier="{name}">{title}</autoref>'


def _resolve_member_identifier(name):
    """Qualify a dotted ``Class.member`` See Also entry to its autoref identifier.

    A member -- a method or attribute -- has no page of its own; it is an anchor
    on its class page, so it cannot be resolved to a URL the way a class or a
    function can.  This qualifies the entry to a full identifier and hands it to
    autorefs, which does know the anchor.

    ``OtherClass.build`` becomes ``kedro_dagster.module.OtherClass.build``
    via the short-name lookup; an entry already led by the package name is
    returned unchanged (its trailing segment is a member, so
    ``_resolve_see_also_url`` did not resolve it to a page).  Returns None when
    the leading segment is neither this package nor a known project symbol, so a
    genuinely external dotted name (``sklearn.linear_model.Ridge``) falls through
    to external handling and keeps its own inventory link.
    """
    package = "kedro_dagster"
    if "." not in name:
        return None
    head, rest = name.split(".", 1)
    if head == package:
        return name
    qualified_head = _get_api_name_lookup(Path(__file__).parent.parent).get(head)
    if qualified_head is None:
        return None
    return f"{qualified_head}.{rest}"


def _link_entry(name, title, colon, entry):
    """Render one See Also entry: project link, deferred external ref, or as-is."""
    url = _resolve_see_also_url(name)
    if url:
        return f'<a href="{url}">{title}</a>{colon}'
    member_identifier = _resolve_member_identifier(name)
    if member_identifier is not None:
        return _external_autoref(member_identifier, title) + colon
    if "." in name and name.split(".", 1)[0] != "kedro_dagster":
        return _external_autoref(name, title) + colon
    return entry


# The glossary lives in the explanation quadrant by Diataxis convention. A
# project without this page simply gets no glossary linking.
_GLOSSARY_SRC_PATH = "pages/explanation/glossary.md"

# Text inside these never becomes a glossary link: code is not prose, a heading
# linking mid-title looks broken, and nesting an <a> inside an <a> is invalid.
_GLOSSARY_SKIP_TAGS = frozenset({"code", "pre", "a", "h1", "h2", "h3", "h4", "h5", "h6", "script", "style"})

# A definition-list term carrying attributes, e.g. ``Memory buffer { #memory-buffer .autolink }``.
_GLOSSARY_TERM_RE = re.compile(r"^(?!\s)(.+?)\s*\{:?\s*([^}]*)\}\s*$")


def _get_glossary_terms(project_root):
    """Map each auto-linkable glossary term to its anchor (cached).

    The glossary page is the single source of truth: terms are read from it, so
    a term and its definition cannot drift apart the way a second list in this
    file would.

    A term opts in with ``.autolink``::

        Memory buffer { #memory-buffer .autolink }
        :   The internal store of recent rows...

    Opting in is deliberate rather than automatic. A glossary defines whatever
    its authors find worth defining, including short common words -- "step",
    "pipeline", "ensemble" -- and auto-linking those wherever they appear in
    prose produces noise, not navigation. Defining a term and advertising it
    everywhere are separate editorial decisions, so they get separate syntax.
    """
    global _GLOSSARY_TERMS_CACHE  # noqa: PLW0603
    if _GLOSSARY_TERMS_CACHE is not None:
        return _GLOSSARY_TERMS_CACHE

    terms = {}
    page = project_root / "docs" / _GLOSSARY_SRC_PATH
    try:
        lines = page.read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeDecodeError):
        _GLOSSARY_TERMS_CACHE = terms
        return terms

    for i, line in enumerate(lines[:-1]):
        match = _GLOSSARY_TERM_RE.match(line)
        # The next line starting with ':' is what makes this a definition-list
        # term rather than ordinary prose that happens to end in braces.
        if not match or not lines[i + 1].lstrip().startswith(":"):
            continue
        attrs = match.group(2).split()
        if ".autolink" not in attrs:
            continue
        anchor = next((a[1:] for a in attrs if a.startswith("#")), None)
        if anchor:
            terms[match.group(1).strip().lower()] = anchor

    _GLOSSARY_TERMS_CACHE = terms
    return terms


def _glossary_link_replacer(terms, rel_glossary, linked):
    """Build the text-node rewriter that links a term's first occurrence."""
    # Longest first, so "seasonal naive forecaster" wins over "forecaster"
    # rather than being shadowed by the shorter term inside it.
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")\b",
        re.IGNORECASE,
    )

    def _replace(text):
        def _sub(match):
            term = match.group(1).lower()
            if term in linked:
                return match.group(0)
            linked.add(term)
            return f'<a href="{rel_glossary}/#{terms[term]}">{match.group(0)}</a>'

        return pattern.sub(_sub, text)

    return _replace


class _GlossaryLinker(HTMLParser):
    """Rewrites text nodes into glossary links, leaving markup untouched.

    Parsed rather than regexed over the whole page: a bare regex would match
    inside tag attributes and code blocks, producing broken markup from a
    document that was fine.
    """

    def __init__(self, replace):
        super().__init__(convert_charrefs=False)
        self._replace = replace
        self.result = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in _GLOSSARY_SKIP_TAGS:
            self._skip_depth += 1
        self.result.append(self.get_starttag_text())

    def handle_startendtag(self, tag, attrs):
        self.result.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag.lower() in _GLOSSARY_SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
        self.result.append(f"</{tag}>")

    def handle_data(self, data):
        self.result.append(data if self._skip_depth else self._replace(data))

    def handle_entityref(self, name):
        self.result.append(f"&{name};")

    def handle_charref(self, name):
        self.result.append(f"&#{name};")

    def handle_comment(self, data):
        self.result.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.result.append(f"<!{decl}>")

    def get_html(self):
        """Return the rewritten HTML."""
        return "".join(self.result)


def _linkify_glossary_terms(html, page, project_root):
    """Link the first occurrence of each glossary term on a page.

    First occurrence only: linking every "memory buffer" in a paragraph is
    noise, and the reader only needs the definition once.

    The glossary page itself is skipped -- it would link its own terms to
    themselves.
    """
    src = page.file.src_path
    if src == _GLOSSARY_SRC_PATH or not src.startswith("pages/"):
        return html

    terms = _get_glossary_terms(project_root)
    if not terms:
        return html

    # Relative, not absolute: the site may be served under a subpath, and
    # use_directory_urls means a page's own URL is a directory.
    dest_dir = posixpath.dirname(page.file.dest_path)
    rel_glossary = posixpath.relpath(posixpath.splitext(_GLOSSARY_SRC_PATH)[0], dest_dir)

    linker = _GlossaryLinker(_glossary_link_replacer(terms, rel_glossary, set()))
    linker.feed(html)
    linker.close()
    return linker.get_html()


def _linkify_see_also(html):
    """Turn the names in a rendered See Also section into links.

    Must run while the ``<details class="see-also">`` container still exists --
    see the ordering comment in ``on_page_content``.  Unresolvable names are
    left untouched: a docstring may reference a private helper or a concept,
    and none of those are build errors.
    """

    def _process_block(block_match):
        def _linkify_line(line):
            entry_match = _SEE_ALSO_ENTRY_RE.match(line)
            if not entry_match:
                return line
            lead, token, colon = entry_match.groups()
            rest = line[entry_match.end() :]
            code_match = re.fullmatch(r"<code>([^<]+)</code>", token)
            name = code_match.group(1) if code_match else token
            title = f"<code>{name}</code>" if code_match else name
            return lead + _link_entry(name, title, colon, token + colon) + rest

        def _linkify_inner(inner):
            # Leave an author's explicit [Name][target] reference alone: they have
            # said what they mean, and autorefs resolves it later.
            if "<a " in inner or "<autoref" in inner:
                return inner
            return "\n".join(_linkify_line(line) for line in inner.split("\n"))

        def _process_container(container_match):
            tag, inner = container_match.group(1), container_match.group(2)
            if tag == "li":
                # Already one entry per item; only the names need linking.
                return f"<li>{_linkify_inner(inner)}</li>"
            entries = _split_see_also_entries(_linkify_inner(inner))
            if len(entries) < 2:
                return f"<p>{_linkify_inner(inner)}</p>"
            # numpydoc puts each entry on its own source line inside one
            # paragraph, and HTML collapses those newlines to spaces -- so every
            # entry runs together on a single line, and the more references a
            # symbol has the worse it reads. An author can dodge it by hand-
            # writing markdown bullets (yohou does, which is why its pages look
            # right and nobody else's do), but plain numpydoc is what the other
            # 145 blocks in the fleet are written in. One entry per line is what
            # the section is for.
            items = "".join(f"<li>{entry}</li>" for entry in entries)
            return f"<ul>{items}</ul>"

        # numpydoc renders See Also entries as a paragraph, one per line; an author
        # may also write them as a markdown list, which renders as <li>. Both are
        # ordinary numpydoc, so both get linked.
        return re.sub(r"<(p|li)>(.*?)</\1>", _process_container, block_match.group(0), flags=re.DOTALL)

    return _SEE_ALSO_BLOCK_RE.sub(_process_block, html)


def _make_section_heading(slug, title, level=3):
    """Build a heading element for an API page section."""
    return (
        f'<h{level} id="{slug}" class="doc-section-heading">{title}'
        f'<a class="headerlink" href="#{slug}" '
        f'title="Permanent link">&para;</a></h{level}>'
    )


def _process_api_page_content(html, page, config):
    """Convert numpydoc sections to h3 headings under mkdocstrings h2.

    Restructures the rendered HTML produced by mkdocstrings so that
    Parameters, Attributes, Returns, Raises, Notes, See Also,
    References, and Source Code become proper ``<h3>`` headings.
    The Source Code section is kept collapsible and preceded by a
    link to the source file on GitHub.
    For class pages a "Methods" heading is inserted before
    ``doc-children`` and method headings are re-levelled h3 → h5.
    Finally the page TOC is rebuilt to reflect the new structure.
    """
    from mkdocs.structure.toc import AnchorLink

    is_class_page = bool(re.search(r'<h3\s+id="kedro_dagster\.', html))

    # Locate class-level content region
    h2_match = re.search(r'<h2\s+id="kedro_dagster\.', html)
    if not h2_match:
        return html
    h2_pos = h2_match.start()

    if is_class_page:
        boundary_match = re.search(r'<div\s+class="doc doc-children"', html[h2_pos:])
        boundary_pos = h2_pos + boundary_match.start() if boundary_match else len(html)
    else:
        boundary_pos = len(html)

    class_region = html[h2_pos:boundary_pos]
    sections_found = []  # (id, title) in document order

    # Convert doc-section-title spans to h3 headings
    def _span_to_h3(m):
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip().rstrip(":")
        slug = _DOC_SECTION_TITLE_SLUGS.get(title)
        if slug:
            sections_found.append((slug, title))
            return _make_section_heading(slug, title)
        return m.group(0)

    new_class_region = re.sub(
        r"<p>\s*<span\s+class=\"doc-section-title\"[^>]*>(.*?)</span>\s*</p>",
        _span_to_h3,
        class_region,
    )

    # Convert <details> sections to h3 heading + unwrapped content
    for detail_cls, (slug, title) in _DETAIL_SECTION_SLUGS.items():
        detail_re = re.compile(
            rf'<details\s+class="{re.escape(detail_cls)}"[^>]*>'
            rf"\s*<summary>{re.escape(title)}</summary>"
            rf"(.*?)</details>",
            re.DOTALL,
        )
        m = detail_re.search(new_class_region)
        if m:
            heading = _make_section_heading(slug, title)
            inner = m.group(1).strip()
            new_class_region = new_class_region[: m.start()] + heading + "\n" + inner + new_class_region[m.end() :]
            sections_found.append((slug, title))

    # Convert <details class="mkdocstrings-source"> to collapsible Source Code
    # with a GitHub link preceding the code block
    src_re = re.compile(
        r'<details\s+class="mkdocstrings-source"[^>]*>'
        r"\s*<summary>.*?</summary>"
        r"(.*?)</details>",
        re.DOTALL,
    )
    src_m = src_re.search(new_class_region)
    if src_m:
        heading = _make_section_heading("source-code", "Source Code")
        inner = src_m.group(1).strip()

        # Build GitHub source link from page path and config
        github_link = ""
        repo_url = config.get("repo_url", "").rstrip("/")
        if repo_url:
            # Extract qualified name from page source path
            src_path = page.file.src_path  # pages/api/generated/{qualified}.md
            qualified = src_path.split("/")[-1].removesuffix(".md")
            # qualified = package.module.Name → module path = package/module.py
            parts = qualified.split(".")
            if len(parts) >= 2:
                module_path = "/".join(parts[:-1])
                git_ref = _get_git_ref()
                github_link = (
                    f'<p class="github-source-link">'
                    f'<a href="{repo_url}/blob/{git_ref}/src/{module_path}.py">'
                    f"View on GitHub</a></p>\n"
                )

        source_block = (
            heading
            + "\n"
            + github_link
            + '<details class="source-code-details">\n'
            + "<summary>Show/Hide source</summary>\n"
            + inner
            + "\n"
            + "</details>"
        )
        new_class_region = new_class_region[: src_m.start()] + source_block + new_class_region[src_m.end() :]
        sections_found.append(("source-code", "Source Code"))

    html = html[:h2_pos] + new_class_region + html[boundary_pos:]

    # Insert "Methods" h3 before doc-children
    if is_class_page:
        methods_heading = _make_section_heading("methods", "Methods") + "\n"
        html = re.sub(
            r'(<div\s+class="doc doc-children")',
            methods_heading + r"\1",
            html,
            count=1,
        )

    # Increase method heading levels (h3 -> h4) in doc-children
    if is_class_page:
        dc_match = re.search(r'<div\s+class="doc doc-children"', html)
        if dc_match:
            before = html[: dc_match.start()]
            after = html[dc_match.start() :]
            after = re.sub(r"<h3(\s)", r"<h4\1", after)
            after = re.sub(r"</h3>", "</h4>", after)
            html = before + after

    # Process method numpydoc sections and source code in doc-children
    if is_class_page:
        dc_match2 = re.search(r'<div\s+class="doc doc-children"', html)
        if dc_match2:
            dc_start = dc_match2.start()
            dc_content = html[dc_start:]

            # Build GitHub link once (same source file for all methods)
            method_github_link = ""
            repo_url = config.get("repo_url", "").rstrip("/")
            if repo_url:
                _src_path = page.file.src_path
                _qualified = _src_path.split("/")[-1].removesuffix(".md")
                _parts = _qualified.split(".")
                if len(_parts) >= 2:
                    _module_path = "/".join(_parts[:-1])
                    _git_ref = _get_git_ref()
                    method_github_link = (
                        f'<p class="github-source-link">'
                        f'<a href="{repo_url}/blob/{_git_ref}/src/{_module_path}.py">'
                        f"View on GitHub</a></p>\n"
                    )

            # Find all method headings (h4) with their IDs
            method_positions = [(m.start(), m.group(1)) for m in re.finditer(r'<h4\s+id="([^"]+)"', dc_content)]

            if method_positions:
                new_dc = dc_content[: method_positions[0][0]]
                for idx, (pos, method_id) in enumerate(method_positions):
                    end_pos = method_positions[idx + 1][0] if idx + 1 < len(method_positions) else len(dc_content)
                    method_short = method_id.split(".")[-1]
                    section = dc_content[pos:end_pos]

                    # Convert numpydoc section-title spans to h5 headings
                    def _method_span_to_h5(m, _ms=method_short):
                        title = re.sub(r"<[^>]+>", "", m.group(1)).strip().rstrip(":")
                        base_slug = _DOC_SECTION_TITLE_SLUGS.get(title)
                        if base_slug:
                            slug = f"{_ms}-{base_slug}"
                            return _make_section_heading(slug, title, level=5)
                        return m.group(0)

                    section = re.sub(
                        r"<p>\s*<span\s+class=\"doc-section-title\"[^>]*>(.*?)</span>\s*</p>",
                        _method_span_to_h5,
                        section,
                    )

                    # Convert detail sections (Notes, See Also, References) to h6
                    for detail_cls, (base_slug, title) in _DETAIL_SECTION_SLUGS.items():
                        _slug = f"{method_short}-{base_slug}"
                        detail_re_m = re.compile(
                            rf'<details\s+class="{re.escape(detail_cls)}"[^>]*>'
                            rf"\s*<summary>{re.escape(title)}</summary>"
                            rf"(.*?)</details>",
                            re.DOTALL,
                        )
                        dm = detail_re_m.search(section)
                        if dm:
                            heading = _make_section_heading(_slug, title, level=5)
                            inner = dm.group(1).strip()
                            section = section[: dm.start()] + heading + "\n" + inner + section[dm.end() :]

                    # Convert source code to collapsible block with GitHub link
                    method_src_re = re.compile(
                        r'<details\s+class="mkdocstrings-source"[^>]*>'
                        r"\s*<summary>.*?</summary>"
                        r"(.*?)</details>",
                        re.DOTALL,
                    )
                    msrc_m = method_src_re.search(section)
                    if msrc_m:
                        _slug = f"{method_short}-source-code"
                        heading = _make_section_heading(_slug, "Source Code", level=5)
                        inner = msrc_m.group(1).strip()
                        source_block = (
                            heading
                            + "\n"
                            + method_github_link
                            + '<details class="source-code-details">\n'
                            + "<summary>Show/Hide source</summary>\n"
                            + inner
                            + "\n"
                            + "</details>"
                        )
                        section = section[: msrc_m.start()] + source_block + section[msrc_m.end() :]

                    new_dc += section

                html = html[:dc_start] + new_dc

    # Rename "Examples" h2 to "Tutorials" h3
    examples_h2 = re.search(r'<h2 id="examples">.*?</h2>', html, re.DOTALL)
    if examples_h2:
        old = examples_h2.group(0)
        new = (
            old
            .replace('<h2 id="examples">', '<h3 id="tutorials">')
            .replace("</h2>", "</h3>")
            .replace(">Examples<", ">Tutorials<")
            .replace("#examples", "#tutorials")
        )
        html = html.replace(old, new, 1)

    # Rebuild page.toc
    old_toc = list(page.toc)
    if old_toc:
        h1 = old_toc[0]
        old_h2s = list(h1.children)

        # The first h2 child is the mkdocstrings class/func heading
        if old_h2s:
            main_h2 = old_h2s[0]

        # All sections nest inside the mkdocstrings h2
        section_children = []

        # Numpydoc + detail + source code sections (level 3)
        for slug, title in sections_found:
            section_children.append(AnchorLink(title=title, id=slug, level=3))

        # Methods with individual methods nested underneath (level 3 + 4)
        if is_class_page:
            methods_entry = AnchorLink(title="Methods", id="methods", level=3)
            # Recover method names from the HTML h4 headings
            dc_match_toc = re.search(r'<div\s+class="doc doc-children"', html)
            if dc_match_toc:
                for m_toc in re.finditer(r'<h4[^>]+id="([^"]+)"[^>]*>', html[dc_match_toc.start() :]):
                    method_id = m_toc.group(1)
                    method_short = method_id.split(".")[-1]
                    badge = '<code class="doc-symbol doc-symbol-method"></code> '
                    methods_entry.children.append(AnchorLink(title=badge + method_short, id=method_id, level=4))
            section_children.append(methods_entry)

        # Tutorials (level 3)
        for h2 in old_h2s[1:]:
            if h2.id in ("examples", "tutorials"):
                section_children.append(AnchorLink(title="Tutorials", id="tutorials", level=3))
                break

        if old_h2s:
            main_h2.children = section_children
            h1.children = [main_h2]
        else:
            h1.children = section_children

    return html


def on_config(config):
    """Clear per-build caches.

    `on_config` is the first event on every build, including each rebuild in a
    `mkdocs serve` session -- which is the lifetime these caches need.

    Deliberately not `on_startup`: that runs once per `mkdocs` invocation, so a
    reset there fires when the caches are already empty and never again, and
    `mkdocs serve` keeps serving the first build's content.
    """
    global _SUBMODULE_CACHE, _API_NAME_LOOKUP_CACHE, _GIT_REF_CACHE, _GLOSSARY_TERMS_CACHE  # noqa: PLW0603
    _SUBMODULE_CACHE = None
    _API_NAME_LOOKUP_CACHE = None
    _GIT_REF_CACHE = None
    _GLOSSARY_TERMS_CACHE = None
    return config


def on_page_content(html, page, config, files):
    """Post-process HTML: API page TOC and content restructuring."""
    src = page.file.src_path

    # Process generated API member pages (per-class/function detail pages)
    if src.startswith("pages/api/generated/"):
        # ORDER IS LOAD-BEARING: mkdocstrings emits See Also as a
        # <details class="see-also"> block, and _process_api_page_content
        # dissolves that block for class-level docstrings.  Linkifying after it
        # silently does nothing for class-level See Also sections -- the
        # majority of them -- while appearing to work for method-level ones.
        html = _linkify_see_also(html)
        html = _process_api_page_content(html, page, config)

    # Keyed on the template a page declares, not on where the page happens to
    # live: the index is wherever a project put it. Matching a hardcoded
    # `pages/reference/api.md` leaves a relocated index with no module_toc at
    # all -- its sidebar renders empty, and nothing errors.
    if page.meta.get("template") in ("api-index.html", "api-submodule.html"):
        page.meta["module_toc"] = _build_module_toc(config, current_src_path=src, prefix=_site_root_prefix(page))

    # Last: the API restructuring above rewrites whole regions, so linking
    # before it would have its links discarded with the markup they sat in.
    html = _linkify_glossary_terms(html, page, Path(__file__).parent.parent)

    return html


def on_page_markdown(markdown, page, config, files):
    """Inject dynamic content into markdown pages.

    Placeholder injection
    ---------------------
    ``<!-- API_TABLE -->``            → submodule table for API index
    ``<!-- SUBPAGES -->``             → linked list of the pages an index introduces
    """
    project_root = Path(__file__).parent.parent
    prefix = _site_root_prefix(page)

    # API_TABLE placeholder
    if "<!-- API_TABLE -->" in markdown:
        table = _build_api_table_html(project_root, prefix)
        markdown = markdown.replace("<!-- API_TABLE -->", table)

    # SUBPAGES placeholder
    if "<!-- SUBPAGES -->" in markdown:
        markdown = _replace_marker(markdown, "<!-- SUBPAGES -->", _build_subpages_list(config, page, files))

    # Strip EXAMPLES_FOR placeholders when examples are disabled
    markdown = re.sub(r"<!-- EXAMPLES_FOR:[\w.]+ -->\n?", "", markdown)

    _warn_on_unhandled_markers(markdown, page.file.src_path)

    return markdown


def on_pre_build(config):
    """Generate API submodule pages."""
    project_root = Path(__file__).parent.parent

    # Generate per-submodule API reference pages
    _generate_api_pages(project_root)


class _HtmlToMarkdown(HTMLParser):
    """HTML parser that converts mkdocs-material HTML to clean markdown."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._lines: list[str] = []
        self._line: list[str] = []
        self._list_stack: list[dict[str, int | str]] = []
        self._in_pre = False
        self._pre_buffer: list[str] = []
        self._pre_lang: str | None = None
        self._in_code_inline = False
        self._code_buffer: list[str] = []
        self._code_target: str = "line"
        self._skip_depth = 0
        self._in_table = False
        self._table_rows: list[list[str]] = []
        self._current_row: list[str] = []
        self._current_cell: list[str] = []
        self._row_has_th = False
        self._first_row_is_header = False
        self._in_highlight_table = False
        self._in_doc_section_title = False
        self._skip_next_table = False

    def get_markdown(self) -> str:
        """Return the accumulated markdown content."""
        self._flush_line()
        self._trim_trailing_blank_lines()
        return "\n".join(self._lines).strip() + "\n"

    def _trim_trailing_blank_lines(self) -> None:
        """Remove trailing blank lines from output."""
        while self._lines and not self._lines[-1].strip():
            self._lines.pop()

    def _flush_line(self) -> None:
        """Flush current line buffer to output."""
        if not self._line:
            return
        line = "".join(self._line).rstrip()
        self._lines.append(line)
        self._line = []

    def _ensure_blank_line(self) -> None:
        """Ensure there's a blank line before the next content."""
        if self._line:
            self._flush_line()
        if not self._lines or self._lines[-1].strip():
            self._lines.append("")

    def _start_block(self) -> None:
        """Start a new block-level element."""
        self._ensure_blank_line()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Handle HTML start tags and convert to markdown."""
        if self._skip_depth:
            self._skip_depth += 1
            return
        attr_map = {k: v or "" for k, v in attrs}
        if tag == "a" and "headerlink" in attr_map.get("class", ""):
            self._skip_depth = 1
            return
        if tag == "span" and "doc-section-title" in attr_map.get("class", ""):
            self._in_doc_section_title = True
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush_line()
            self._ensure_blank_line()
            level = int(tag[1])
            self._line.append("#" * level + " ")
        elif tag == "p":
            self._start_block()
        elif tag == "br":
            self._flush_line()
        elif tag == "ul":
            self._start_block()
            self._list_stack.append({"type": "ul", "count": 0})
        elif tag == "ol":
            self._start_block()
            self._list_stack.append({"type": "ol", "count": 1})
        elif tag == "li":
            self._flush_line()
            indent = "  " * max(len(self._list_stack) - 1, 0)
            if self._list_stack and self._list_stack[-1]["type"] == "ol":
                count = int(self._list_stack[-1]["count"])
                self._list_stack[-1]["count"] = count + 1
                bullet = f"{count}."
            else:
                bullet = "-"
            self._line.append(f"{indent}{bullet} ")
        elif tag == "pre":
            self._start_block()
            self._in_pre = True
            self._pre_buffer = []
            self._pre_lang = None
        elif tag == "code" and self._in_pre:
            class_name = attr_map.get("class", "")
            match = re.search(r"language-([a-zA-Z0-9_+-]+)", class_name)
            if match:
                self._pre_lang = match.group(1)
        elif tag == "code":
            self._in_code_inline = True
            self._code_buffer = []
            self._code_target = "cell" if self._in_table else "line"
        elif tag in {"strong", "b"}:
            self._line.append("**")
        elif tag in {"em", "i"}:
            self._line.append("*")
        elif tag == "table":
            if "highlighttable" in attr_map.get("class", ""):
                self._in_highlight_table = True
                return
            if self._skip_next_table:
                self._skip_next_table = False
                self._skip_depth = 1
                return
            self._start_block()
            self._in_table = True
            self._table_rows = []
            self._current_row = []
            self._current_cell = []
            self._row_has_th = False
            self._first_row_is_header = False
        elif tag == "td" and self._in_highlight_table and "linenos" in attr_map.get("class", ""):
            self._skip_depth = 1
        elif tag == "tr" and self._in_table:
            self._current_row = []
            self._row_has_th = False
        elif tag in {"th", "td"} and self._in_table:
            self._current_cell = []
            if tag == "th":
                self._row_has_th = True

    def handle_endtag(self, tag: str) -> None:
        """Handle HTML end tags and complete markdown conversion."""
        if self._skip_depth:
            self._skip_depth -= 1
            return
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"} or tag == "p":
            self._flush_line()
            self._ensure_blank_line()
        elif tag in {"ul", "ol"}:
            if self._list_stack:
                self._list_stack.pop()
            self._flush_line()
            self._ensure_blank_line()
        elif tag == "li":
            self._flush_line()
        elif tag == "pre":
            self._in_pre = False
            self._flush_pre()
        elif tag == "code" and self._in_code_inline:
            code_text = "".join(self._code_buffer).strip()
            if code_text:
                wrapped = f"`{code_text}`"
                if self._code_target == "cell":
                    self._current_cell.append(wrapped)
                else:
                    self._line.append(wrapped)
            self._in_code_inline = False
        elif tag in {"strong", "b"}:
            self._line.append("**")
        elif tag in {"em", "i"}:
            self._line.append("*")
        elif tag in {"th", "td"} and self._in_table:
            cell_text = "".join(self._current_cell).strip()
            self._current_row.append(cell_text)
            self._current_cell = []
        elif tag == "tr" and self._in_table:
            if self._current_row:
                if not self._table_rows:
                    self._first_row_is_header = self._row_has_th
                self._table_rows.append(self._current_row)
            self._current_row = []
        elif tag == "table":
            if self._in_highlight_table:
                self._in_highlight_table = False
                return
            self._emit_table()
            self._in_table = False

    def handle_data(self, data: str) -> None:
        """Handle text data within HTML tags."""
        if self._skip_depth:
            return
        if self._in_doc_section_title:
            section_title = data.strip()
            if section_title == "Parameters:":
                self._skip_next_table = True
            self._in_doc_section_title = False
            return
        if self._in_pre:
            self._pre_buffer.append(data)
            return
        if self._in_code_inline:
            self._code_buffer.append(data)
            return
        text = data
        text = re.sub(r"\s+", " ", text)
        if not text:
            return
        if self._in_table and self._current_cell is not None:
            self._current_cell.append(text)
            return
        if self._line and self._line[-1].endswith(" "):
            text = text.lstrip()
        self._line.append(text)

    def _flush_pre(self) -> None:
        """Flush preformatted code block to markdown."""
        pre_text = "".join(self._pre_buffer)
        pre_text = pre_text.rstrip("\n")
        fence = f"```{self._pre_lang or ''}".rstrip()
        self._lines.append(fence)
        if pre_text:
            self._lines.extend(pre_text.splitlines())
        self._lines.append("```")
        self._lines.append("")
        self._pre_buffer = []
        self._pre_lang = None

    def _emit_table(self) -> None:
        """Emit accumulated table rows as markdown table."""
        if not self._table_rows:
            return
        column_count = max(len(row) for row in self._table_rows)
        rows = [row + [""] * (column_count - len(row)) for row in self._table_rows]
        if self._first_row_is_header:
            header = rows[0]
            body = rows[1:]
        else:
            header = [""] * column_count
            body = rows
        header_line = "| " + " | ".join(self._escape_cell(cell) for cell in header) + " |"
        separator = "| " + " | ".join("---" for _ in header) + " |"
        self._lines.append(header_line)
        self._lines.append(separator)
        for row in body:
            row_line = "| " + " | ".join(self._escape_cell(cell) for cell in row) + " |"
            self._lines.append(row_line)
        self._lines.append("")

    @staticmethod
    def _escape_cell(value: str) -> str:
        """Escape special characters in table cells."""
        return value.replace("|", r"\|").strip()


def _html_to_markdown(html: str) -> str:
    """Convert HTML to clean markdown using custom parser."""
    parser = _HtmlToMarkdown()
    parser.feed(html)
    return parser.get_markdown()


def _extract_article_html(html: str) -> str | None:
    """Extract the main article content from mkdocs HTML."""
    marker = '<article class="md-content__inner md-typeset">'
    start = html.find(marker)
    if start == -1:
        return None
    start += len(marker)
    end = html.find("</article>", start)
    if end == -1:
        return None
    return html[start:end]


def _html_path_for(relative: str, site_dir: Path) -> Path:
    """Convert markdown path to corresponding HTML path in site directory."""
    if relative == "index.md":
        return site_dir / "index.html"
    return site_dir / relative.removesuffix(".md") / "index.html"


def _is_excluded(relative_posix: str, patterns: list[str]) -> bool:
    """Check if a relative path matches any exclusion pattern."""
    return any(fnmatch.fnmatch(relative_posix, pattern) for pattern in patterns)


def on_post_build(config):
    """Copy markdown files for LLM consumption after build completes."""
    site_dir = Path(config["site_dir"])
    docs_dir = Path(config["docs_dir"])
    # Get exclude patterns from config
    # Note: mkdocs converts exclude_docs to a GitIgnoreSpec object, so we hardcode patterns
    exclude_patterns = ["examples/**/CLAUDE.md"]

    # Remove legacy llm/ directory if it exists
    legacy_dir = site_dir / "llm"
    if legacy_dir.exists():
        shutil.rmtree(legacy_dir)

    # Copy llms.txt if it exists
    llms_txt_source = docs_dir / "llms.txt"
    if llms_txt_source.exists():
        llms_txt_dest = site_dir / "llms.txt"
        shutil.copy2(llms_txt_source, llms_txt_dest)
        print("[hooks] copied llms.txt to site")

    # Process markdown files
    copied_count = 0
    for md_file in sorted(docs_dir.rglob("*.md")):
        relative_posix = md_file.relative_to(docs_dir).as_posix()

        # Skip excluded files
        if _is_excluded(relative_posix, exclude_patterns):
            continue

        destination = site_dir / relative_posix
        destination.parent.mkdir(parents=True, exist_ok=True)

        # Try to convert from built HTML first
        html_path = _html_path_for(relative_posix, site_dir)
        if html_path.exists():
            html = html_path.read_text(encoding="utf-8")
            article_html = _extract_article_html(html)
            if article_html:
                markdown = _html_to_markdown(article_html)
                destination.write_text(markdown, encoding="utf-8")
                copied_count += 1
                continue

        # Fallback: copy original markdown
        destination.write_text(md_file.read_text(encoding="utf-8"), encoding="utf-8")
        copied_count += 1

    if copied_count > 0:
        print(f"[hooks] copied {copied_count} markdown files to site")
