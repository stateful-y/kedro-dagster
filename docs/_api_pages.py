"""Generate the API reference pages for Kedro-Dagster.

Reads the package source and writes ``docs/pages/api/*.md`` plus one page per
public class and function under ``docs/pages/api/generated/``. Discovery is
static -- the package is never imported -- so this runs in an environment where
the package's own dependencies are absent.

Importable and runnable on its own::

    python docs/_api_pages.py

This module deliberately imports nothing from ``mkdocs``. It is called from
``docs/hooks.py``'s ``on_pre_build`` so that ``mkdocs serve`` regenerates on a
source edit, but nothing here depends on that being the caller -- which is what
makes it testable without a docs build, and what the template's test suite
enforces.

``docs/hooks.py`` also imports the discovery helpers below (the page hooks need
the same answer to "what is public in this package?"), so this module is the one
definition of that surface. Two definitions drift, and the drift renders as a
missing page rather than an error.
"""

import ast
import importlib.util
from pathlib import Path

# Module-level caches, moved here with the functions that own them. The build
# loads this module once per process, so an unreset cache serves stale content
# for the rest of a `mkdocs serve` session.
#
# Naming is load-bearing: the per-build reset and its registration test discover
# caches by the `_CACHE` suffix, so a cache named otherwise escapes both,
# silently. The test scans every module the hooks load, not just hooks.py --
# these two live here now, and a scan of hooks.py alone would quietly stop
# covering them while still passing.
_SUBMODULE_CACHE = None
_API_NAME_LOOKUP_CACHE = None


def reset_caches():
    """Clear this module's per-build caches.

    Called by ``on_config`` in ``docs/hooks.py``, which fires on every build
    including each rebuild in a serve session. Exposed as a function because a
    caller cannot rebind another module's globals with a ``global`` statement --
    resetting from hooks.py would need ``_api_pages._SUBMODULE_CACHE = None``,
    which works but puts the cache set's definition in the wrong file.
    """
    global _SUBMODULE_CACHE, _API_NAME_LOOKUP_CACHE  # noqa: PLW0603
    _SUBMODULE_CACHE = None
    _API_NAME_LOOKUP_CACHE = None


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
    """Return the file backing a submodule: ``name.py``, else ``name/__init__.py``."""
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


def generate(project_root):
    """Generate every API reference page under ``docs/pages/api/``.

    The public entry point. ``project_root`` is the directory holding ``src/``
    and ``docs/``.
    """
    _generate_api_pages(project_root)


def main():
    """Generate the API pages for the project this file lives in."""
    generate(Path(__file__).parent.parent)


if __name__ == "__main__":
    main()
