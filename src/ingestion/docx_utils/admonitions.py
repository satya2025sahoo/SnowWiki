import re

_ADMONITION_MAP = {
    "note": "NOTE",
    "notice": "NOTE",
    "warning": "WARNING",
    "danger": "WARNING",
    "important": "IMPORTANT",
    "tip": "TIP",
    "hint": "TIP",
    "caution": "CAUTION",
}

_ADMONITION_RE = re.compile(
    r"^\*{0,2}(Note|Notice|Warning|Danger|Important|Tip|Hint|Caution)\*{0,2}[:\-]?(?:\*\*)?\s*(.*)$",
    re.IGNORECASE
)


def _format_admonition(tag: str, first_line_content: str, subsequent_lines: list[str] | None = None) -> list[str]:
    """
    Format an admonition into GitHub-style alert blockquotes.
    Ensures every subsequent line is prefixed with '> ' (Refinement 1).
    """
    lines = [f"> [!{tag}]"]
    if first_line_content.strip():
        lines.append(f"> {first_line_content.strip()}")
    if subsequent_lines:
        for sub in subsequent_lines:
            s = sub.strip()
            if not s:
                lines.append(">")
            else:
                lines.append(f"> {s}")
    return lines


def _unwrap_single_cell_pipe_tables(text: str) -> str:
    """
    Detect single-cell 1x1 pipe tables emitted by Mammoth:
      | Note: Make sure to check ACLs. |
      | --- |
    and unwrap them into clean blockquotes or GitHub-style admonitions.
    """
    pattern = re.compile(
        r"^\|\s*([^|\n]+?)\s*\|\s*\n\|\s*[-:]+\s*\|\s*$",
        re.MULTILINE
    )

    def _repl(match):
        content = match.group(1).strip()
        adm = _ADMONITION_RE.match(content)
        if adm:
            tag = _ADMONITION_MAP.get(adm.group(1).lower(), "NOTE")
            rest = adm.group(2).strip()
            lines = _format_admonition(tag, rest)
            return "\n".join(lines)
        return f"> {content}"

    return pattern.sub(_repl, text)
