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

# An entry opens a line with a name (backticked or bare, possibly dotted) and a
# colon. A line that does not match is a continuation of the entry above -- a
# wrapped description -- not a new entry. Anchored so a colon inside a
# description ("Target : note: ...") does not start a spurious entry.
_ENTRY_START = re.compile(r"^\s*(?:`[^`]+`|[A-Za-z_][\w.]*)\s*:")

# A single entry: its name (backticked or bare) and the rest of the line.
_ENTRY = re.compile(r"^\s*`?(?P<name>[A-Za-z_][\w.]*)`?\s*:\s*(?P<desc>.*)$")


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
        """Group lines into entries; a continuation line joins the entry above."""
        entries: list[list[str]] = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if _ENTRY_START.match(line) or not entries:
                entries.append([stripped])
            else:
                entries[-1].append(stripped)
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
        - A dotted external name (`numpy.ndarray`) is handed to autorefs by
          identifier; if no inventory resolves it, autorefs leaves it as text
          rather than failing a strict build.
        - A bare name that is not a project symbol is left unlinked: a wrong link
          to an unrelated same-named symbol is worse than no link.
        """
        if name in self._paths:
            return self._paths[name]
        if "." in name:
            head, rest = name.split(".", 1)
            if head == self._package.split(".", 1)[0]:
                return name  # already package-qualified
            if head in self._paths:
                return f"{self._paths[head]}.{rest}"
            return name  # external dotted name: let autorefs try, harmless if it cannot
        return None
