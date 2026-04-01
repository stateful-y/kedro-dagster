"""MkDocs hooks for post-build processing."""

import ast
import fnmatch
import re
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

_SUBMODULE_CACHE = None


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


def _get_package_members(pkg_dir, module_name):
    """Discover members in a sub-package by scanning all child ``.py`` files.

    For sub-packages like ``config/`` or ``datasets/``, scans each non-private
    child module and aggregates class/function definitions.  Each member dict
    gets a *qualified_prefix* key so callers can build fully qualified names
    (e.g. ``kedro_dagster.config.execution.ExecutorOptions``).
    """
    child_dir = pkg_dir / module_name
    classes = []
    functions = []
    seen = set()

    for py_file in sorted(child_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        child_name = py_file.stem
        members = _get_module_members(py_file)
        prefix = f"kedro_dagster.{module_name}.{child_name}"
        for cls in members["classes"]:
            if cls["name"] not in seen:
                seen.add(cls["name"])
                cls["qualified_prefix"] = prefix
                classes.append(cls)
        for func in members["functions"]:
            if func["name"] not in seen:
                seen.add(func["name"])
                func["qualified_prefix"] = prefix
                functions.append(func)

    return {"classes": classes, "functions": functions}


def _resolve_members(pkg_dir, module_name):
    """Return members for a module, scanning child files for sub-packages."""
    mod_file = pkg_dir / f"{module_name}.py"
    if mod_file.exists():
        members = _get_module_members(mod_file)
        prefix = f"kedro_dagster.{module_name}"
        for cls in members["classes"]:
            cls.setdefault("qualified_prefix", prefix)
        for func in members["functions"]:
            func.setdefault("qualified_prefix", prefix)
        return members

    # Sub-package
    init_file = pkg_dir / module_name / "__init__.py"
    if init_file.exists():
        return _get_package_members(pkg_dir, module_name)

    return {"classes": [], "functions": []}


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
            prefix = cls.get("qualified_prefix", f"{package_name}.{module_name}")
            qualified = f"{prefix}.{cls['name']}"
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
            prefix = func.get("qualified_prefix", f"{package_name}.{module_name}")
            qualified = f"{prefix}.{func['name']}"
            link = f"[`{func['name']}`](generated/{qualified}.md)"
            lines.append(f"| {link} | {func['doc']} |")
        sections.append("\n".join(lines))

    if not sections:
        return ""

    return "\n\n".join(sections)


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
        members = _resolve_members(pkg_dir, mod["module_name"])

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
        for cls in members["classes"]:
            prefix = cls.get("qualified_prefix", f"kedro_dagster.{mod['module_name']}")
            qualified = f"{prefix}.{cls['name']}"
            page = generated_dir / f"{qualified}.md"
            page.write_text(_page_template.format(name=cls["name"], qualified=qualified))
            member_count += 1

        for func in members["functions"]:
            prefix = func.get("qualified_prefix", f"kedro_dagster.{mod['module_name']}")
            qualified = f"{prefix}.{func['name']}"
            page = generated_dir / f"{qualified}.md"
            page.write_text(_page_template.format(name=func["name"], qualified=qualified))
            member_count += 1

    if member_count:
        print(f"[hooks] generated {member_count} API member pages in pages/api/generated/")


def _build_api_table_html(project_root):
    """Build an HTML <table> for the API index with DataTables init.

    Lists every public class and function across all submodules with
    Name, Type, Module, and Description columns.  The table is initialised
    with jQuery DataTables for client-side filtering and sorting.
    """
    modules = _get_submodules(project_root)
    pkg_dir = project_root / "src" / "kedro_dagster"

    rows = []
    for mod in modules:
        members = _resolve_members(pkg_dir, mod["module_name"])
        module_label = f"kedro_dagster.{mod['module_name']}"
        module_href = f"../../api/{mod['module_name']}/"

        for cls in members["classes"]:
            prefix = cls.get("qualified_prefix", module_label)
            qualified = f"{prefix}.{cls['name']}"
            rows.append((cls["name"], "Class", module_label, module_href, cls["doc"], qualified))

        for func in members["functions"]:
            prefix = func.get("qualified_prefix", module_label)
            qualified = f"{prefix}.{func['name']}"
            rows.append((func["name"], "Function", module_label, module_href, func["doc"], qualified))

    rows.sort(key=lambda r: r[0].lower())

    _type_badge_cls = {
        "Class": "api-badge--class",
        "Function": "api-badge--function",
    }

    tbody_lines = []
    for name, kind, module_label, module_href, desc, qualified in rows:
        href = f"../../api/generated/{qualified}/"
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


def _build_module_toc(config, current_src_path=None):
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

    is_index = current_src_path is None or current_src_path == "pages/reference/api.md"

    modules = _get_submodules(project_root)
    module_toc = []

    for mod in modules:
        md_filename = f"{mod['module_name']}.md"
        md_path = api_dir / md_filename
        if not md_path.exists():
            continue

        # Compute relative URL
        if is_index:
            # reference/api.md is at pages/reference/api/, submodule pages at pages/api/
            page_url = f"../../api/{md_filename.replace('.md', '/')}"
        else:
            page_url = f"../{md_filename.replace('.md', '/')}".replace("//", "/")

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
            old.replace('<h2 id="examples">', '<h3 id="tutorials">')
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


def on_page_content(html, page, config, files):
    """Post-process HTML: API page TOC and content restructuring."""
    src = page.file.src_path

    # Process generated API member pages (per-class/function detail pages)
    if src.startswith("pages/api/generated/"):
        html = _process_api_page_content(html, page, config)

    if src == "pages/reference/api.md":
        # API index: flat module list (api-index.html template)
        page.meta["module_toc"] = _build_module_toc(config, current_src_path=src)
    elif (
        src.startswith("pages/api/")
        and not src.startswith("pages/api/generated/")
        and page.meta.get("template") == "api-submodule.html"
    ):
        # Submodule page: module list with active/children expansion
        page.meta["module_toc"] = _build_module_toc(config, current_src_path=src)

    return html


def on_page_markdown(markdown, page, config, files):
    """Inject dynamic content into markdown pages.

    Placeholder injection
    ---------------------
    ``<!-- API_TABLE -->``         → submodule table for API index
    """
    project_root = Path(__file__).parent.parent

    # API_TABLE placeholder
    if "<!-- API_TABLE -->" in markdown:
        table = _build_api_table_html(project_root)
        markdown = markdown.replace("<!-- API_TABLE -->", table)
    # Strip EXAMPLES_FOR placeholders when examples are disabled
    markdown = re.sub(r"<!-- EXAMPLES_FOR:[\w.]+ -->\n?", "", markdown)
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
