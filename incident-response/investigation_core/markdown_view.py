"""Small offline Markdown renderer: escape HTML and permit only safe link schemes."""
import html
import re
from urllib.parse import urlsplit


def inline(text):
    tokens = []
    def hold(value):
        tokens.append(value)
        return '\x00' + str(len(tokens)-1) + '\x00'
    text = re.sub(r'`([^`]+)`', lambda m: hold('<code>' + html.escape(m[1]) + '</code>'), text)
    def link(match):
        label, target = match[1], match[2].strip('<>')
        try:
            scheme = urlsplit(target).scheme.lower()
        except ValueError:
            return html.escape(label)
        if scheme not in {'', 'http', 'https', 'mailto'} or target.startswith(('//', '\\')) or any(ord(c) < 32 for c in target):
            return hold(html.escape(label))
        extra = ' target="_blank" rel="noopener noreferrer"' if scheme in {'http', 'https'} else ''
        return hold('<a href="' + html.escape(target, quote=True) + '"' + extra + '>' + html.escape(label) + '</a>')
    text = re.sub(r'\[([^\]\n]+)\]\((<[^>\n]+>|[^\s)]+)\)', link, text)
    text = html.escape(text)
    text = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: '<strong>' + (m[1] or m[2]) + '</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', text)
    for index, token in enumerate(tokens):
        text = text.replace('\x00' + str(index) + '\x00', token)
    return text


def render(markdown):
    lines = markdown.replace('\r\n', '\n').splitlines()
    output, outline = [], []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.lstrip().startswith('```'):
            code = []
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith('```'):
                code.append(lines[i]); i += 1
            output.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
            i += 1
            continue
        heading = re.match(r'^(#{1,6})\s+(.+)', line)
        if heading:
            level, title = len(heading[1]), heading[2]
            anchor = 'section-' + str(len(outline))
            outline.append(dict(id=anchor, title=title, level=level))
            output.append(f'<h{level} id="{anchor}">' + inline(title) + f'</h{level}>')
            i += 1
            continue
        if i+1 < len(lines) and '|' in line and re.fullmatch(r'\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*', lines[i+1]):
            cells = lambda value: re.split(r'(?<!\\)\|', value.strip().strip('|'))
            output.append('<div class="table-scroll"><table><thead><tr>' + ''.join('<th>' + inline(c.strip()) + '</th>' for c in cells(line)) + '</tr></thead><tbody>')
            i += 2
            while i < len(lines) and '|' in lines[i] and lines[i].strip():
                output.append('<tr>' + ''.join('<td>' + inline(c.strip().replace('\\|', '|')) + '</td>' for c in cells(lines[i])) + '</tr>')
                i += 1
            output.append('</tbody></table></div>')
            continue
        item = re.match(r'^\s*(?:([-+*])|\d+[.)])\s+(.+)', line)
        if item:
            ordered = not item[1]
            tag = 'ol' if ordered else 'ul'
            start = re.match(r'^\s*(\d+)', line) if ordered else None
            attr = ' start="' + start[1] + '"' if start and start[1] != '1' else ''
            output.append('<' + tag + attr + '>')
            while i < len(lines):
                item = re.match(r'^\s*(?:([-+*])|\d+[.)])\s+(.+)', lines[i])
                if not item or bool(item[1]) == ordered:
                    break
                value = item[2]; i += 1
                while i < len(lines) and lines[i].startswith(('  ', '\t')) and not re.match(r'^\s*(?:[-+*]|\d+[.)])\s+', lines[i]):
                    value += ' ' + lines[i].strip(); i += 1
                output.append('<li>' + inline(value) + '</li>')
                following = i
                while following < len(lines) and not lines[following].strip():
                    following += 1
                next_item = re.match(r'^\s*(?:([-+*])|\d+[.)])\s+', lines[following]) if following < len(lines) else None
                if next_item and bool(next_item[1]) != ordered:
                    i = following
            output.append('</' + tag + '>')
            continue
        if line.startswith('>'):
            quotes = []
            while i < len(lines) and lines[i].startswith('>'):
                quotes.append(lines[i][1:].strip()); i += 1
            output.append('<blockquote>' + inline(' '.join(quotes)) + '</blockquote>')
            continue
        if re.fullmatch(r'\s*(?:---+|\*\*\*+)\s*', line):
            output.append('<hr>'); i += 1; continue
        paragraph = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r'^\s*(?:#{1,6}\s|```|>|[-+*]\s|\d+[.)]\s)', lines[i]):
            paragraph.append(lines[i]); i += 1
        output.append('<p>' + inline(' '.join(paragraph)) + '</p>')
    return '\n'.join(output), outline
