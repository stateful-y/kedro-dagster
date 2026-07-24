"""Griffe extension: normalize numpydoc "References" into a markdown list.

This runs during Griffe collection, before mkdocstrings parses the docstring, so a
References section written in any of the three styles seen across the fleet --
reStructuredText citation definitions (`.. [1] ...`), bare-bracket entries
(`[1] ...`), or an already-markdown ordered list (`1. ...`) -- renders as one
clean markdown ordered list. It is the twin of `_see_also.py`: Griffe's numpy
parser hands a References section to mkdocstrings as an unstructured *admonition*
whose raw text is passed straight to `convert_markdown`, so RST citation syntax
renders literally (`.. [1]` appears verbatim on the page) and a bare-bracket block
collapses into one run-on paragraph. Rewriting the raw docstring here fixes both,
independent of when and how the docstring is later parsed, and under any engine.

Registered via `handlers.python.options.extensions` in mkdocs.yml, next to
`_see_also`. Unlike See Also, References entries are freeform citations that name
no project symbols, so this extension needs no name lookup -- it only reshapes
text.

The render target is a markdown ordered list, NOT markdown footnotes (`[^1]`):
mkdocstrings pools footnotes at the *page* bottom and their numbers collide across
the many objects rendered on one API page, so a list -- which stays inside each
object's own section -- is the portable form. `hello.py` in the template models it.
"""

import logging
import re

from griffe import Extension

# Warnings logged under the "mkdocs" logger tree are counted by mkdocs and turn a
# --strict build red -- the same idiom `_markers` and `_api_pages` use. A References
# section that still holds RST citation syntax after this pass would otherwise ship
# as literal text on the page; warning here makes that a build failure instead.
log = logging.getLogger("mkdocs.hooks")

# The "References" section heading: a line, then an underline of dashes at the same
# indent (numpydoc requires the underline to be at least as long as the title).
_HEADING = re.compile(r"(?m)^(?P<indent>[ \t]*)References[ \t]*\n(?P=indent)-{3,}[ \t]*\n")

# The start of the NEXT numpydoc section: a non-blank title line followed by a
# dashes-only underline. This -- not the first blank line, which is where See Also
# stops -- is where a References block ends, because references are routinely
# separated by blank lines; stopping at the first one would drop every entry after
# it. A reference entry's continuation lines are never a dashes-only line, so this
# cannot mistake an entry for a section header.
_NEXT_SECTION = re.compile(r"(?m)^[ \t]*\S.*\n[ \t]*-{3,}[ \t]*$")

# A leading markdown list marker (`- `, `* `, `+ `, `1. `) on an entry line. Some
# docstrings already write References as a list; stripping the marker before we
# re-number stops `1. X` becoming `1. 1. X` (or `- X` a nested `1. - X`).
_LIST_MARKER = re.compile(r"^(?:\d+\.|[-*+])\s+")

# A leading citation label: the RST definition form (`.. [1] `, `.. [CIT2002] `) or
# the bare-bracket form (`[1] `). The bare form requires whitespace after the `]` so
# a markdown link at the start of an entry (`[Title](url)`) is left untouched -- its
# `]` is followed by `(`, not a space.
_CITATION = re.compile(r"^\.\. \[[^\]]+\]\s*|^\[[^\]]+\]\s+")

# An inline citation *reference* in RST style: `[1]_`, `[CIT2002]_`. Rewritten to
# plain `[1]` so no trailing-underscore reference survives into rendered prose.
_BODY_CITE = re.compile(r"\[([^\]]+)\]_")

# Whatever the RST citation-definition marker looks like after normalization has run.
# If it survives, an entry could not be reshaped and the page would show it literally.
_RESIDUAL_RST = ".. ["


class ReferencesExtension(Extension):
    """Rewrite numpydoc References blocks into a markdown ordered list at collection."""

    def on_object(self, *, obj, **_kwargs) -> None:
        """Rewrite the References block of any object whose docstring has one."""
        docstring = obj.docstring
        if docstring is None or "References" not in docstring.value:
            return
        rewritten = self._rewrite(docstring.value, obj.path)
        # Inline `[1]_` references point at a References entry, so only rewrite them
        # where a References section exists -- conservative, and there are none in
        # the fleet today anyway.
        rewritten = _BODY_CITE.sub(r"[\1]", rewritten)
        if rewritten != docstring.value:
            docstring.value = rewritten

    def _rewrite(self, text: str, path: str) -> str:
        """Replace a References block's entries with a markdown ordered list."""
        heading = _HEADING.search(text)
        if heading is None:
            return text

        body_start = heading.end()
        rest = text[body_start:]
        # The block runs to the next section header, or to the end of the docstring.
        next_section = _NEXT_SECTION.search(rest)
        body_end = body_start + (next_section.start() if next_section else len(rest))

        entries = self._split_entries(text[body_start:body_end])
        if not entries:
            return text

        block = "".join(f"{i}. {entry}\n" for i, entry in enumerate(entries, start=1))
        if _RESIDUAL_RST in block:
            # An entry held RST citation syntax the marker strip did not reach (a
            # second directive, a directive on a continuation line). Left alone it
            # renders verbatim; under --strict this warning fails the build.
            log.warning("references: RST citation syntax survived normalization in %s", path)

        return text[:body_start] + block + text[body_end:]

    def _split_entries(self, body: str) -> list[str]:
        """Group the block's lines into entries and strip each entry's marker.

        A new reference begins at a citation marker (`[1]`, `.. [1]`) or a list
        marker (`1.`, `-`); every other line continues the entry above it. This is
        keyed on the marker, NOT on indentation: numpydoc *recommends* indenting a
        wrapped continuation, but many docstrings write the continuation flush with
        the marker line, and splitting those by indent turned one citation into one
        list item per physical line. Marker-keyed splitting folds a flush-left
        multi-line citation into a single entry and still separates blank-line- or
        indent-separated entries correctly. Each entry's leading marker is stripped
        so the caller can re-number from 1 without doubling markers.
        """
        entries: list[list[str]] = []
        for line in body.splitlines():
            if not line.strip():
                continue
            stripped = line.strip()
            if not entries or self._starts_entry(stripped):
                entries.append([self._strip_marker(stripped)])
            else:
                entries[-1].append(stripped)
        return [" ".join(parts).strip() for parts in entries]

    def _starts_entry(self, line: str) -> bool:
        """Whether a (stripped) line begins a new reference: it leads with a marker."""
        return bool(_LIST_MARKER.match(line) or _CITATION.match(line))

    def _strip_marker(self, line: str) -> str:
        """Remove a leading list marker and citation label from an entry's first line."""
        line = _LIST_MARKER.sub("", line, count=1)
        return _CITATION.sub("", line, count=1)
