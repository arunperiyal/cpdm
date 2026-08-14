"""A dependency-free Markdown to HTML renderer.

Only the subset used by the CPDM documentation is supported: ATX headings,
fenced code blocks, pipe tables, bullet and ordered lists, blockquotes,
horizontal rules, paragraphs, and the inline forms (code, bold, italic, links).

If the optional ``markdown`` package is installed it is used instead, which
adds the rest of the CommonMark surface for free.
"""

import html
import re

try:  # optional, better-quality renderer
    import markdown as _markdown
except ImportError:  # pragma: no cover - exercised by environment, not tests
    _markdown = None

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_ORDERED = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")
_BULLET = re.compile(r"^(\s*)[-*+]\s+(.*)$")
_RULE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_TABLE_DIVIDER = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")

_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"(?<![\*\w])\*([^*\n]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_AUTOLINK = re.compile(r"(?<![\"'=(])\b(https?://[^\s<)]+)")


def slugify(text):
    """A stable id for a heading, used for in-page anchors."""
    slug = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", slug) or "section"


def render_inline(text):
    """Escape a line of text, then re-introduce the inline markup as HTML."""
    placeholders = []

    def stash(markup):
        placeholders.append(markup)
        return f"\x00{len(placeholders) - 1}\x00"

    # Code spans win over every other inline rule, so pull them out first.
    def keep_code(match):
        return stash(f"<code>{html.escape(match.group(1))}</code>")

    text = _INLINE_CODE.sub(keep_code, text)

    def keep_link(match):
        label, href = match.group(1), match.group(2)
        return stash(f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>')

    text = _LINK.sub(keep_link, text)

    text = html.escape(text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    text = _AUTOLINK.sub(r'<a href="\1">\1</a>', text)

    for index, markup in enumerate(placeholders):
        text = text.replace(f"\x00{index}\x00", markup)
    return text


def _render_table(header_cells, rows):
    out = ['<div class="table-wrap"><table>', "<thead><tr>"]
    out += [f"<th>{render_inline(cell)}</th>" for cell in header_cells]
    out.append("</tr></thead><tbody>")
    for row in rows:
        out.append("<tr>")
        out += [f"<td>{render_inline(cell)}</td>" for cell in row]
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def _split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _fallback_render(text):
    lines = text.replace("\r\n", "\n").split("\n")
    out = []
    paragraph = []
    list_stack = []  # open list tags, innermost last

    def close_paragraph():
        if paragraph:
            out.append(f"<p>{render_inline(' '.join(paragraph))}</p>")
            paragraph.clear()

    def close_lists(depth=0):
        while len(list_stack) > depth:
            out.append(f"</{list_stack.pop()}>")

    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        # fenced code
        if stripped.startswith("```"):
            close_paragraph()
            close_lists()
            language = stripped[3:].strip()
            index += 1
            block = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            css = f' class="language-{html.escape(language)}"' if language else ""
            out.append(f"<pre><code{css}>{html.escape(chr(10).join(block))}</code></pre>")
            index += 1
            continue

        if not stripped:
            close_paragraph()
            close_lists()
            index += 1
            continue

        if _RULE.match(line):
            close_paragraph()
            close_lists()
            out.append("<hr>")
            index += 1
            continue

        heading = _HEADING.match(stripped)
        if heading:
            close_paragraph()
            close_lists()
            level = len(heading.group(1))
            title = heading.group(2).strip()
            out.append(
                f'<h{level} id="{slugify(title)}">{render_inline(title)}</h{level}>'
            )
            index += 1
            continue

        # pipe table: a header row followed by a divider row
        if "|" in stripped and index + 1 < len(lines) and _TABLE_DIVIDER.match(lines[index + 1]):
            close_paragraph()
            close_lists()
            header_cells = _split_row(stripped)
            index += 2
            rows = []
            while index < len(lines) and "|" in lines[index] and lines[index].strip():
                rows.append(_split_row(lines[index]))
                index += 1
            out.append(_render_table(header_cells, rows))
            continue

        if stripped.startswith(">"):
            close_paragraph()
            close_lists()
            quote = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip()[1:].strip())
                index += 1
            out.append(f"<blockquote><p>{render_inline(' '.join(quote))}</p></blockquote>")
            continue

        bullet = _BULLET.match(line)
        ordered = _ORDERED.match(line)
        if bullet or ordered:
            close_paragraph()
            match = bullet or ordered
            indent = len(match.group(1).replace("\t", "    "))
            depth = indent // 2 + 1
            tag = "ul" if bullet else "ol"
            content = match.group(2) if bullet else match.group(3)

            close_lists(depth)
            while len(list_stack) < depth:
                out.append(f"<{tag}>")
                list_stack.append(tag)

            out.append(f"<li>{render_inline(content.strip())}</li>")
            index += 1
            continue

        close_lists()
        paragraph.append(stripped)
        index += 1

    close_paragraph()
    close_lists()
    return "\n".join(out)


def render(text):
    """Convert Markdown source to an HTML fragment."""
    if _markdown is not None:
        return _markdown.markdown(
            text, extensions=["tables", "fenced_code", "toc", "sane_lists"]
        )
    return _fallback_render(text)


def first_heading(text):
    """The document title: its first ATX heading, if any."""
    for line in text.splitlines():
        match = _HEADING.match(line.strip())
        if match:
            return match.group(2).strip()
    return None


def first_paragraph(text):
    """The first body paragraph, used as a one-line summary."""
    lines = text.replace("\r\n", "\n").split("\n")
    seen_heading = False
    buffer = []
    for line in lines:
        stripped = line.strip()
        if _HEADING.match(stripped):
            seen_heading = True
            continue
        if not stripped:
            if buffer:
                break
            continue
        if stripped.startswith(("```", ">", "|", "-", "*")) and not buffer:
            continue
        buffer.append(stripped)
    summary = " ".join(buffer).strip()
    if not summary and not seen_heading:
        return ""
    return re.sub(r"[*`]", "", summary)
