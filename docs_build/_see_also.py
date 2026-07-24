"""Griffe extension: rewrite numpydoc "See Also" into markdown cross-references.

This runs during Griffe collection, before mkdocstrings parses the docstring, so
each See Also entry becomes a `[name][target]` reference that autorefs resolves,
and a multi-entry block becomes a real markdown list. It replaces the HTML
post-processing the docs hooks used to do (`_linkify_see_also` and friends),
which reached into mkdocstrings' rendered HTML and was fragile against changes in
that HTML shape.

It is engine-independent: it operates on the Griffe object model, which both
MkDocs and the successor engine drive through the real mkdocstrings and Griffe.
Registered via `handlers.python.options.extensions` in mkdocs.yml.

numpydoc renders See Also as an "admonition" section (Griffe declines to parse it
into structured entries; see griffe's numpy parser), so the entries are only ever
available as raw text. Rewriting the raw docstring is therefore the natural place,
and it is independent of when and how the docstring is later parsed.
"""

import re

from griffe import Extension

# The "See Also" section heading: a line, then an underline of dashes at the same
# indent. numpydoc requires the underline to be at least as long as the title.
_HEADING = re.compile(r"(?m)^(?P<indent>[ \t]*)See Also[ \t]*\n(?P=indent)-{3,}[ \t]*\n")

# A single entry: a name (backticked or bare, possibly dotted) and, optionally, a
# description after a colon. numpydoc allows a See Also target with NO description
# -- just the name -- so the ": desc" tail is optional. Requiring it once left
# every name-only entry unlinked, and (via _split_entries) collapsed a block of
# name-only targets onto one line.
_ENTRY = re.compile(r"^\s*`?(?P<name>[A-Za-z_][\w.]*)`?\s*(?::\s*(?P<desc>.*))?$")

# A leading markdown list marker on an entry line. Some docstrings hand-write See
# Also as a bullet list already (``- `X` : ...``); stripping the marker before we
# re-wrap the entry stops ``- `X``` becoming ``- - `X```` -- a nested,
# double-bulleted list once rendered.
_LIST_MARKER = re.compile(r"^[-*+]\s+")


class SeeAlsoExtension(Extension):
    """Rewrite See Also blocks into markdown cross-references at collection time."""

    def __init__(self) -> None:
        """Start with an empty name lookup; it is filled once the package loads."""
        self._package = ""
        self._paths: dict[str, str] = {}

    def on_package(self, *, pkg, **_kwargs) -> None:
        """Build the short-name -> qualified-path lookup once, from the package."""
        self._package = pkg.path
        self._collect(pkg)

    def _collect(self, obj) -> None:
        """Map each public class/function short name to its qualified path.

        Recurses through modules and classes so a name written in a See Also
        block resolves wherever the symbol lives in the package. The first
        definition of a short name wins, matching how the API index is built.
        """
        for member in obj.members.values():
            target = member
            if getattr(member, "is_alias", False):
                try:
                    target = member.final_target
                except Exception:  # unresolved alias: skip it
                    continue
            kind = getattr(getattr(target, "kind", None), "value", None)
            if kind in ("class", "function"):
                self._paths.setdefault(target.name, target.path)
            if kind in ("module", "class"):
                self._collect(target)

    def on_object(self, *, obj, **_kwargs) -> None:
        """Rewrite the See Also block of any object whose docstring has one."""
        docstring = obj.docstring
        if docstring is None or "See Also" not in docstring.value:
            return
        docstring.value = self._rewrite(docstring.value)

    def _rewrite(self, text: str) -> str:
        """Replace a See Also block's entries with cross-referenced markdown."""
        heading = _HEADING.search(text)
        if heading is None:
            return text

        body_start = heading.end()
        # The block runs to the first blank line: numpydoc separates sections by
        # a blank line, and See Also entries (with their wrapped descriptions) are
        # consecutive non-blank lines.
        body_lines: list[str] = []
        consumed = 0
        for line in text[body_start:].splitlines(keepends=True):
            if not line.strip():
                break
            body_lines.append(line)
            consumed += len(line)

        entries = self._split_entries(body_lines)
        if not entries:
            return text

        rendered = [self._render_entry(entry) for entry in entries]
        # Multiple entries become a markdown list (a <ul>); a lone entry stays a
        # paragraph. This matches what the HTML transform produced.
        block = "".join(f"- {item}\n" for item in rendered) if len(rendered) > 1 else rendered[0] + "\n"

        return text[:body_start] + block + text[body_start + consumed :]

    def _split_entries(self, lines: list[str]) -> list[str]:
        """Group lines into entries by indentation.

        numpydoc puts each See Also target at the section's base indent and
        indents any wrapped description beneath it. A target often has NO
        description (just a name), so the presence of a colon cannot mark a new
        entry: keying on it collapsed every name-only block onto a single line and
        left it unlinked. Indentation is the real signal -- a line at (or below)
        the first entry's indent starts a new entry; a more-indented line
        continues the one above.

        A leading markdown list marker on an entry is stripped: some docstrings
        hand-write See Also as a bullet list, and re-wrapping ``- `X``` into
        ``- - `X``` renders a nested, double-bulleted list.
        """
        entries: list[list[str]] = []
        base_indent: int | None = None
        for line in lines:
            if not line.strip():
                continue
            indent = len(line) - len(line.lstrip())
            if base_indent is None:
                base_indent = indent
            if not entries or indent <= base_indent:
                entries.append([_LIST_MARKER.sub("", line.strip())])
            else:
                entries[-1].append(line.strip())
        return [" ".join(parts) for parts in entries]

    def _render_entry(self, entry: str) -> str:
        """Turn one entry into `[name][target] : desc`, or leave it unlinked."""
        match = _ENTRY.match(entry)
        if match is None:
            return entry
        name = match.group("name")
        desc = match.group("desc")
        target = self._resolve(name)
        link = f"[`{name}`][{target}]" if target else f"`{name}`"
        return f"{link} : {desc}" if desc else link

    def _resolve(self, name: str) -> str | None:
        """Resolve a name to an autoref identifier, or None to leave it plain.

        - A project class or function resolves to its qualified path.
        - `Class.member` resolves the class, then appends the member, so a method
          named in a See Also block links to its anchor on the class page.
        - A dotted name qualified with THIS package resolves to itself; a wrong
          path there (`pkg.config.logging.X` where the class is `pkg.config.X`) is
          a real broken reference and SHOULD red the strict build.
        - A dotted name from ANOTHER top-level package (`numpy.ndarray`,
          `yohou.point.Base`) is left unlinked. At collection time we cannot know
          whether an inventory will resolve it, and an autoref that fails to
          resolve is a FATAL warning under `--strict`, not the harmless plain text
          this once assumed -- so a legitimate cross-reference to a dependency
          symbol reddened the whole build. Plain text is what the old HTML hook
          produced for these, and it never failed.
        - A bare name that is not a project symbol is left unlinked: a wrong link
          to an unrelated same-named symbol is worse than no link.
        """
        if name in self._paths:
            return self._paths[name]
        if "." in name:
            head, rest = name.split(".", 1)
            if head == self._package.split(".", 1)[0]:
                return name  # already package-qualified (internal; a wrong path here is a real bug)
            if head in self._paths:
                return f"{self._paths[head]}.{rest}"
            return None  # foreign-package dotted name: an unresolvable autoref is fatal under --strict
        return None
