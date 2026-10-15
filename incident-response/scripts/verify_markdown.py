"""Check readable Markdown and unsafe-link/HTML containment in offline reports."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from investigation_core.markdown_view import render

source = '''# Assessment

**Strong evidence** and *uncertain impact*, with `file.exe`.

- First finding
- Second finding

1. Check source
2. Correlate time

| Fact | Status |
| --- | --- |
| Download | Observed |

> This is a quoted observation.

```powershell
<script>alert(1)</script>
```

[Report](analysis.md) [Research](https://example.org/research)
[Bad](javascript:alert(1)) [Data](data:text/html,evil)
<img src=x onerror=alert(1)>
'''
view, outline = render(source)
assert '<strong>Strong evidence</strong>' in view
assert '<em>uncertain impact</em>' in view and '<code>file.exe</code>' in view
assert '<ul>' in view and '<ol>' in view and '<table>' in view and '<blockquote>' in view
assert '<a href="analysis.md"' in view and 'rel="noopener noreferrer"' in view
assert '<script>' not in view and '<img ' not in view
assert 'href="javascript:' not in view and 'href="data:' not in view
assert '&lt;script&gt;' in view
assert outline[0]['title'] == 'Assessment'
print('PASS: Markdown structure, safe links, escaped HTML, inert code blocks and report outline')
