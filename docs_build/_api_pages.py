"""Generate the API reference pages for Kedro-Dagster.

Reads the package source and writes ``docs/pages/api/*.md`` plus one page per
public class and function under ``docs/pages/api/generated/``. Discovery is
static -- the package is never imported -- so this runs in an environment where
the package's own dependencies are absent.

Importable and runnable on its own::

    python docs_build/_api_pages.py

This module deliberately imports nothing from ``mkdocs``. It is called from
``docs_build/build.py``'s ``prebuild`` step (and by ``serve.py`` on a source
edit), but nothing here depends on that being the caller -- which is what makes
it testable without a docs build, and what the template's test suite enforces.

``docs_build/_markers.py`` also imports the discovery helpers below (the marker
builders need the same answer to "what is public in this package?"), so this
module is the one definition of that surface. Two definitions drift, and the
drift renders as a missing page rather than an error.
"""

import logging
import sys
from pathlib import Path

import yaml
from griffe import GriffeLoader

# By NAME, not by importing mkdocs -- this module must import nothing from it,
# and the generated project's own test suite enforces that. `_markers.py` and
# `_notebooks.py` use the same idiom, so a warning raised here lands in the same
# stream mkdocs' `--strict` escalates.
log = logging.getLogger("mkdocs.hooks")

# Module-level caches. The build loads this module once per process, so an
# unreset cache serves stale content for the rest of a `mkdocs serve` session.
#
# Naming is load-bearing: the per-build reset and its registration test discover
# caches by the `_CACHE` suffix, so a cache named otherwise escapes both,
# silently. The test scans every module the build tooling loads.
_SURFACE_CACHE = None
_API_NAME_LOOKUP_CACHE = None


def reset_caches():
    """Clear this module's per-build caches.

    Called by ``_markers.reset_caches()`` and by ``serve.py`` when a source edit
    regenerates the pages. Exposed as a function because a caller cannot rebind
    another module's globals with a ``global`` statement -- resetting from
    elsewhere would need ``_api_pages._SURFACE_CACHE = None``, which works but
    puts the cache set's definition in the wrong file.
    """
    global _SURFACE_CACHE, _API_NAME_LOOKUP_CACHE  # noqa: PLW0603
    _SURFACE_CACHE = None
    _API_NAME_LOOKUP_CACHE = None


def _preload_modules(project_root):
    """Return the packages Griffe must load before it can resolve re-exports into them.

    Read from ``mkdocs.yml``'s
    ``plugins.mkdocstrings.handlers.python.options.preload_modules`` rather than
    from a key of our own. mkdocstrings already owns that setting and at least
    one project in this template's fleet already sets it, so a second key would
    mean two declarations of one list -- and a list that silently disagrees with
    itself renders as a missing page, which is the failure mode this whole
    module is written to avoid.

    Reading the file is not importing MkDocs: this module still imports nothing
    from it. The custom tags have to be tolerated because a real ``mkdocs.yml``
    carries ``!ENV`` and ``python/name:``, and a strict loader raises on them.
    """
    config_file = project_root / "mkdocs.yml"
    if not config_file.exists():
        return []

    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor("tag:yaml.org,2002:python/name:", lambda _loader, suffix, _node: suffix)
    _Loader.add_constructor("!ENV", lambda _loader, _node: None)
    try:
        config = yaml.load(config_file.read_text(encoding="utf-8"), Loader=_Loader)
    except yaml.YAMLError:
        return []
    for plugin in (config or {}).get("plugins", []) or []:
        if isinstance(plugin, dict) and "mkdocstrings" in plugin:
            handlers = (plugin["mkdocstrings"] or {}).get("handlers", {}) or {}
            options = (handlers.get("python", {}) or {}).get("options", {}) or {}
            return list(options.get("preload_modules") or [])
    return []


def _kind_of(obj):
    """Return the object's kind, or None when it cannot be determined.

    An alias Griffe CAN see through reports its target's kind -- that is what
    makes a re-export appear as the class or function it points at. One it
    CANNOT see through reports ``Kind.ALIAS``, which is the signal wanted here,
    and is why that value maps to None rather than being passed through: a
    caller comparing against "class"/"function" would otherwise drop the symbol
    as merely uninteresting and say nothing, which is the silence this module
    was rewritten to remove.

    Do NOT use ``Alias.resolved`` for this. It reports whether the alias has
    been resolved YET, not whether it can be: a perfectly resolvable in-package
    re-export reads ``resolved=False`` until something touches it, while
    ``.kind`` resolves on demand and answers correctly. Testing ``resolved``
    here dropped every such re-export -- caught only because a fixture asserted
    one had to survive.
    """
    try:
        kind = obj.kind.value
    except Exception:  # noqa: BLE001
        return None
    return None if kind == "alias" else kind


def _members_of(module, collection):
    """Public members of one module: declarations, plus ``__all__`` re-exports.

    Three rules, each measured against the previous AST implementation across
    the seven packages generated from this template:

    1. **Declarations always count.**
    2. **An import counts when ``__all__`` names it**, wherever it points. That
       is what makes a re-export a deliberate part of the API rather than a
       detail, and it is the only way a dependency's symbol becomes ours.
    3. **A package's ``__init__`` re-exports by convention**, so an in-package
       import counts there even with no ``__all__``. A PLAIN module does not:
       ``from .base import Helper`` in ``translator.py`` is normally something
       that module uses, not something it advertises.

    Rule 3 is the one with teeth in both directions. Drop its first half and a
    package that re-exports without ``__all__`` loses every page it publishes.
    Drop its second half -- treat every module's imports as public -- and the
    seven packages generated from this template gain **67 phantom pages**, each
    a second URL for a symbol already documented elsewhere. The distinction is
    inherited verbatim from the AST implementation this replaced; it was right.

    4. **``__all__`` beats a submodule of the same name.** A package holding
       ``commands.py`` that also does ``from .commands import commands`` has the
       submodule occupying ``members["commands"]``; Python's import rebinds the
       name to the function, and ``module.imports`` records that binding
       independently. Without this the function's page disappears.

    ``exports`` is ``None`` when there is no ``__all__`` and an EMPTY LIST when
    ``__all__`` is computed (a comprehension) -- hence ``if exports`` and not
    ``if exports is not None``. The latter filters an empty list down to zero
    members and deletes every page for that module without raising.
    """
    exports = getattr(module, "exports", None)
    exported = {e if isinstance(e, str) else getattr(e, "name", str(e)) for e in exports} if exports else set()
    reexports_by_convention = getattr(module, "is_package", False) or getattr(module, "is_subpackage", False)
    own_prefix = "kedro_dagster."

    selected = {}
    for name, member in module.members.items():
        if name.startswith("_"):
            continue
        if getattr(member, "is_alias", False):
            target = str(getattr(member, "target_path", "") or "")
            if name in exported or (reexports_by_convention and target.startswith(own_prefix)):
                selected[name] = member
        else:
            selected[name] = member

    for name in exported:
        target_path = (getattr(module, "imports", None) or {}).get(name)
        if not target_path:
            continue
        owner_path, _, attr = target_path.rpartition(".")
        try:
            target = collection[owner_path].members.get(attr)
        except Exception:  # noqa: BLE001
            target = None
        if target is not None and _kind_of(target) in ("class", "function"):
            selected[name] = target

    return selected


def _entry(name, obj, module_label, *, reexported):
    """One member entry, or None if this object gets no page.

    *origin* is the object's own canonical path, which is what distinguishes one
    symbol reachable by two paths from two different symbols that happen to
    share a short name -- the distinction ``_get_api_name_lookup`` turns into a
    URL.

    Returning None is NOT a problem report. A re-exported submodule, a constant
    and an unresolvable alias all land here, and only the last is worth a word:
    only classes and functions get pages, so the first two are ordinary. The
    caller decides, using ``_kind_of`` -- conflating the two produced 120
    warnings on one package for its own submodules and constants, which would
    have failed a ``--strict`` build on nothing at all.
    """
    kind = _kind_of(obj)
    if kind not in ("class", "function"):
        return None
    doc = ""
    try:
        if obj.docstring and obj.docstring.value:
            doc = obj.docstring.value.strip().split("\n")[0]
    except Exception:  # noqa: BLE001
        doc = ""
    return {
        "name": name,
        "doc": doc,
        "origin": getattr(obj, "path", f"{module_label}.{name}"),
        "reexported": reexported,
        "kind": kind,
    }


def _load_surface(project_root):
    """Discover the package's public surface with Griffe (cached).

    Griffe is the same analysis mkdocstrings renders the API pages from, so this
    module and the rendered pages cannot disagree about what is public. Nothing
    is imported: the package's own dependencies may be absent.

    Returns ``{module_name: {"module_doc", "classes", "functions"}}`` with the
    package root under the empty-string key.
    """
    global _SURFACE_CACHE  # noqa: PLW0603
    if _SURFACE_CACHE is not None:
        return _SURFACE_CACHE

    package = "kedro_dagster"
    src = project_root / "src"
    if not (src / package).exists():
        _SURFACE_CACHE = {}
        return _SURFACE_CACHE

    # `src` first, then the interpreter's own path. Passing `search_paths`
    # REPLACES Griffe's default rather than extending it, so a bare `[src]`
    # leaves it unable to find any installed package -- which silently disables
    # `preload_modules` entirely, and with it the only case Griffe cannot handle
    # on its own. Measured: with `[src]` alone, a project preloading a
    # dependency to resolve three re-exported classes got none of them and one
    # "could not preload" warning; with `sys.path` appended, all three resolve.
    #
    # `src` stays first so the project under documentation always wins over an
    # installed copy of itself.
    loader = GriffeLoader(search_paths=[str(src), *sys.path])
    # Preloading is the one case Griffe does not handle by default: it will not
    # resolve an alias into a module it has not loaded, and neither extra search
    # paths nor `allow_inspection` change that (`allow_inspection` also imports
    # code, which this module must not do).
    for name in _preload_modules(project_root):
        try:
            loader.load(name)
        except Exception as exc:  # noqa: BLE001
            log.warning("api: could not preload %r for re-export resolution: %s", name, exc)
    root = loader.load(package)
    loader.resolve_aliases(external=True)
    collection = loader.modules_collection

    surface = {}
    submodules = {
        name: member
        for name, member in root.members.items()
        if _kind_of(member) == "module" and not name.startswith("_")
    }
    for module_name, module in sorted(submodules.items()):
        module_doc = ""
        try:
            if module.docstring and module.docstring.value:
                module_doc = module.docstring.value.strip().split("\n")[0]
        except Exception:  # noqa: BLE001
            module_doc = ""
        entries = {"classes": [], "functions": [], "module_doc": module_doc}
        for name, member in _members_of(module, collection).items():
            entry = _entry(
                name,
                member,
                f"{package}.{module_name}",
                reexported=getattr(member, "is_alias", False)
                or not str(getattr(member, "path", "")).startswith(f"{package}.{module_name}."),
            )
            if entry is None:
                # Only an alias we genuinely cannot see is worth reporting.
                # A submodule or a constant simply gets no page, which is normal.
                if _kind_of(member) is None:
                    _warn_unresolved(f"{package}.{module_name}", name)
                continue
            entries["classes" if entry["kind"] == "class" else "functions"].append(entry)
        surface[module_name] = entries

    # Root-only exports: a symbol the package publishes from its own
    # `__init__.py` that no submodule publishes has no module segment in its
    # public path, and falls through anything keyed on a submodule.
    published = {e["name"] for m in surface.values() for e in m["classes"] + m["functions"]}
    root_entries = {"classes": [], "functions": [], "module_doc": ""}
    for name, member in _members_of(root, collection).items():
        if name in published:
            continue
        entry = _entry(name, member, package, reexported=getattr(member, "is_alias", False))
        if entry is None:
            if _kind_of(member) is None:
                _warn_unresolved(package, name)
            continue
        root_entries["classes" if entry["kind"] == "class" else "functions"].append(entry)
    surface[""] = root_entries

    _SURFACE_CACHE = surface
    return _SURFACE_CACHE


def _warn_unresolved(module_label, name):
    """Warn that a symbol we meant to publish could not be resolved.

    Scoped deliberately to symbols the package publishes, NOT to every alias
    Griffe fails to resolve. ``resolve_aliases`` reports across the whole loaded
    object graph, so on a package depending on numpy and scikit-learn it returns
    over a hundred unresolved aliases that all live inside those dependencies --
    none of them ours, and warning on each would fail a `--strict` build for
    reasons having nothing to do with this project's documentation.

    The previous implementation returned ``None`` here and the symbol vanished
    from the index with no signal at all. Silence is the behaviour being
    removed: ``nox -s check_docs`` builds with warnings fatal, so this becomes a
    CI failure while an ordinary `mkdocs serve` keeps working.
    """
    log.warning(
        "api: %s.%s could not be resolved and gets no page; "
        "if it re-exports a dependency's symbol, add that package to "
        "mkdocstrings' preload_modules in mkdocs.yml",
        module_label,
        name,
    )


def _get_submodules(project_root):
    """Public submodules of the package, with their one-line docstrings."""
    surface = _load_surface(project_root)
    return [
        {"module_name": name, "module_doc": entries["module_doc"]} for name, entries in sorted(surface.items()) if name
    ]


def _get_public_members(project_root, module_name):
    """Public classes and functions of one module, including re-exported ones."""
    entries = _load_surface(project_root).get(module_name)
    if entries is None:
        return {"classes": [], "functions": []}
    return {"classes": entries["classes"], "functions": entries["functions"]}


def _get_root_members(project_root):
    """Public symbols the package exports only from its own ``__init__.py``.

    A package that keeps a base class in ``_base.py`` and re-exports it from the
    root -- an ordinary layout -- has a public symbol that belongs to no
    submodule and would otherwise reach no page. Their public path has no module
    segment (``pkg.Name``, not ``pkg.module.Name``), which is exactly why they
    fall through code keyed on a submodule. Names a real submodule already
    publishes keep their module path; only the homeless ones are adopted here.
    """
    return _get_public_members(project_root, "")


def _qualified_name(module_name, member_name):
    """Dotted path of a member's API page.

    A root-only export has no module segment, so the empty module name must not
    produce a doubled dot.
    """
    package = "kedro_dagster"
    return f"{package}.{module_name}.{member_name}" if module_name else f"{package}.{member_name}"


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

    candidates = {}
    for module_name, entries in _load_surface(project_root).items():
        for entry in entries["classes"] + entries["functions"]:
            candidates.setdefault(entry["name"], []).append({
                "qualified": _qualified_name(module_name, entry["name"]),
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
        print("[docs] docs/api-submodule.html not found, skipping API page generation")
        return

    template = template_file.read_text(encoding="utf-8")
    api_dir = project_root / "docs" / "pages" / "api"
    api_dir.mkdir(parents=True, exist_ok=True)

    generated_dir = api_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    # Clean stale generated pages
    for old in generated_dir.glob("*.md"):
        old.unlink()

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
        # Discovery is keyed on the module NAME now, not on a source path: a
        # single-file module and a package directory are the same thing to
        # Griffe, so the file-or-__init__ probe this used to do is gone.
        members = _get_public_members(project_root, mod["module_name"])

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
        print(f"[docs] generated api page: pages/api/{mod['module_name']}.md")

        # Generate per-class/function detail pages
        member_count += _write_member_pages(generated_dir, _page_template, mod["module_name"], members)

    # Symbols exported only from the package root have no submodule and so no
    # module page; they still need a detail page for the table and See Also to
    # link at. Without this the link resolves to nothing and, being raw HTML,
    # nothing validates it.
    member_count += _write_member_pages(generated_dir, _page_template, "", _get_root_members(project_root))

    if member_count:
        print(f"[docs] generated {member_count} API member pages in pages/api/generated/")


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
