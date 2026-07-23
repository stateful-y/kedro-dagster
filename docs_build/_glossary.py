"""Glossary auto-linking as a Python-Markdown Preprocessor, engine-independent.

This replaces what ``hooks._linkify_glossary_terms`` did in ``on_page_content``:
link the first occurrence of each opted-in glossary term on a page to its
definition. It moves off rendered HTML and onto the markdown, for two reasons:

1. **First-occurrence is page-global ordered state** ("interval forecast" occurs
   seven times on one page and is linked once). A Postprocessor is context-free
   and cannot express that; a Preprocessor is called exactly once per page, so
   the ordered state is trivially correct -- and it runs under any engine, which
   a hook does not.
2. **Skipping code and links is simpler in markdown.** The old HTML parser walked
   tags to avoid linking inside ``<code>``/``<a>``; here a fenced block, an inline
   code span, and an existing link are all recognisable in the source directly.

Runs at priority 110, **above** the marker Preprocessor (100): the markers inject
HTML tables and cards, and linking a glossary term inside generated HTML is
exactly what this must not do. Running first means it only ever sees author prose.

Emits a markdown link with a source-relative ``.md`` target, so the engine
resolves it to the right URL under ``use_directory_urls`` -- no engine-specific
``dest_path`` arithmetic, which is the coupling this change exists to remove.
"""

import posixpath
import re
import sys
from pathlib import Path

from markdown.extensions import Extension
from markdown.preprocessors import Preprocessor

# Reach the shared page-context bridge rather than fork a second copy: two
# ``_current_page`` implementations that must stay in step is the drift this
# codebase avoids. ``docs_build`` is put on the path the same way hooks.py does.
sys.path.insert(0, str(Path(__file__).parent))

from _markers import _current_page  # noqa: E402

_PROJECT_ROOT = Path(__file__).parent.parent

# The glossary lives in the explanation quadrant by Diataxis convention. A
# project without this page simply gets no glossary linking.
_GLOSSARY_SRC_PATH = "pages/explanation/glossary.md"

# A definition-list term carrying attributes, e.g. ``Memory buffer { #memory-buffer .autolink }``.
_GLOSSARY_TERM_RE = re.compile(r"^(?!\s)(.+?)\s*\{:?\s*([^}]*)\}\s*$")

# A run of one or more backticks opens an inline code span that the same-length
# run closes; a markdown link/image, a reference link, and a raw HTML tag or
# autolink are all likewise off-limits. Terms are never linked inside any of
# these -- code is not prose, and a link inside a link is invalid markup.
_PROTECTED_SPAN_RE = re.compile(
    r"(`+)[^`]*\1"  # inline code span (opened and closed by equal-length backtick runs)
    r"|!?\[[^\]]*\]\([^)]*\)"  # inline link or image
    r"|!?\[[^\]]*\]\[[^\]]*\]"  # reference link or image
    r"|<[^>]+>"  # raw HTML tag, HTML comment, or autolink
)

# A fenced code block opens and closes with a run of >=3 backticks or tildes.
_FENCE_RE = re.compile(r"^(`{3,}|~{3,})")


def _get_glossary_terms(project_root):
    """Map each auto-linkable glossary term (lower-cased) to its anchor.

    The glossary page is the single source of truth: terms are read from it, so a
    term and its definition cannot drift apart. A term opts in with ``.autolink``::

        Memory buffer { #memory-buffer .autolink }
        :   The internal store of recent rows...

    Opting in is deliberate: a glossary defines short common words too ("step",
    "pipeline"), and auto-linking those wherever prose uses them is noise, not
    navigation. Read fresh each call rather than cached -- the file is small, and
    a persistent cache would serve a stale glossary through ``mkdocs serve`` after
    an edit, which is exactly the live-preview case that must keep working.
    """
    terms = {}
    page = project_root / "docs" / _GLOSSARY_SRC_PATH
    try:
        lines = page.read_text(encoding="utf-8").split("\n")
    except (OSError, UnicodeDecodeError):
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

    return terms


def _term_pattern(terms):
    """Compile the alternation that matches any term, longest first.

    Longest first so "seasonal naive forecaster" wins over "forecaster" rather
    than being shadowed by the shorter term nested inside it.
    """
    return re.compile(
        r"\b(" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")\b",
        re.IGNORECASE,
    )


def _link_prose(text, pattern, terms, rel_glossary, linked):
    """Link first-occurrence terms in a run of prose (no code/link spans in it)."""

    def _sub(match):
        term = match.group(1).lower()
        if term in linked:
            return match.group(0)
        linked.add(term)
        # Source-relative .md target: the engine rewrites it to the page's URL.
        return f"[{match.group(0)}]({rel_glossary}#{terms[term]})"

    return pattern.sub(_sub, text)


def _link_line(line, pattern, terms, rel_glossary, linked):
    """Link terms in a single line, leaving code spans, links and HTML untouched."""
    out = []
    pos = 0
    for protected in _PROTECTED_SPAN_RE.finditer(line):
        out.append(_link_prose(line[pos : protected.start()], pattern, terms, rel_glossary, linked))
        out.append(protected.group(0))
        pos = protected.end()
    out.append(_link_prose(line[pos:], pattern, terms, rel_glossary, linked))
    return "".join(out)


def _linkify(lines, page):
    """Link glossary terms across a page's markdown lines.

    Returns the lines unchanged when there is nothing to do: no page context, the
    glossary page itself (it would link its own definitions to themselves), a page
    outside ``pages/``, or a project with no glossary.
    """
    if page is None:
        return lines
    src = page.file.src_path
    if src == _GLOSSARY_SRC_PATH or not src.startswith("pages/"):
        return lines

    terms = _get_glossary_terms(_PROJECT_ROOT)
    if not terms:
        return lines

    rel_glossary = posixpath.relpath(_GLOSSARY_SRC_PATH, posixpath.dirname(src))
    pattern = _term_pattern(terms)
    linked = set()  # page-global: each term is linked on its first occurrence only

    out = []
    fence = None
    for line in lines:
        fence_match = _FENCE_RE.match(line)
        if fence is not None:
            out.append(line)
            if fence_match and line.startswith(fence):
                fence = None
            continue
        if fence_match:
            fence = fence_match.group(1)
            out.append(line)
            continue
        # Indented code (4 spaces or a tab) and ATX headings are not prose: a
        # link mid-heading looks broken, and code is code.
        if line.startswith(("    ", "\t")) or line.lstrip().startswith("#"):
            out.append(line)
            continue
        out.append(_link_line(line, pattern, terms, rel_glossary, linked))
    return out


class _GlossaryPreprocessor(Preprocessor):
    """Link glossary terms once per page, before the markers inject HTML."""

    def run(self, lines):
        """Link terms in this page's prose."""
        return _linkify(lines, _current_page(self.md))


class GlossaryExtension(Extension):
    """Register the glossary linker above the marker Preprocessor."""

    def extendMarkdown(self, md):
        """Register at priority 110, above the markers (100) and html_block (~20).

        Above the markers so it links only author prose, never the tables and
        cards they inject; above ``html_block`` so it sees existing links and code
        as source text rather than after they have been stashed out of the stream.
        """
        md.preprocessors.register(_GlossaryPreprocessor(md), "docs_glossary", 110)


def makeExtension(**_kwargs):
    """Entry point Python-Markdown calls when loading this by module name."""
    return GlossaryExtension()
