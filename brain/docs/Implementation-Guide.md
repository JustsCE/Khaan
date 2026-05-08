# Implementation Guide

Two parts. How to make HTML pages. How to write code.

---

# Part 1 — HTML Reports

Every HTML page in this project looks the same. Here's how.

---

## Three rules

1. **Say only what you mean.** No filler. No "in summary" at the end. If a sentence doesn't teach something, delete it.

2. **Keep it simple.** One file. One style block. No JavaScript unless you absolutely need it. Fewer lines = better.

3. **If you change something, say so.** If your page does something different from what was asked for, write this where the change is:

```html
<p><strong>[DEVIATES FROM SPEC]</strong> what you changed and why.</p>
```

---

## Page skeleton

Every page uses this exact shape:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Page Title</title>
<style>
  /* paste the full CSS from the next section */
</style>
</head>
<body>
<div class="page-wrap">

  <div class="cover">
    <h1 style="border:none">Page Title</h1>
    <div class="subtitle">One sentence about what this page is.</div>
    <div class="meta">2026-05-08 · JustsCE/Khaan</div>
  </div>

  <div class="toc"><h3>Contents</h3>
    <ol>
      <li><a href="#first">First section</a></li>
      <li><a href="#second">Second section</a></li>
    </ol>
  </div>

  <h2 id="first">First section</h2>
  <p>Content goes here.</p>
  <hr>

  <h2 id="second">Second section</h2>
  <p>More content.</p>

</div>
</body>
</html>
```

That's it. Title at the top. Table of contents. Sections with `<h2>`. Horizontal lines between them. Everything inside one `div.page-wrap`.

---

## CSS

Paste this into every page. Don't change it.

```css
@page { size: A4; margin: 14mm 14mm 16mm 14mm; }
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.5;
    color: #1a1a1a;
    margin: 0;
    background: #f7f7f5;
}
.page-wrap {
    max-width: 200mm;
    margin: 0 auto;
    padding: 8mm;
    background: #fff;
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
@media print {
    body { background: #fff; }
    .page-wrap { box-shadow: none; max-width: none; padding: 0; }
}
h1 {
    font-size: 26pt;
    margin: 0 0 4mm;
    letter-spacing: -.02em;
    line-height: 1.1;
    border-bottom: 2px solid #1a1a1a;
    padding-bottom: 3mm;
}
h2 {
    font-size: 16pt;
    margin: 8mm 0 3mm;
    letter-spacing: -.01em;
    border-bottom: 1px solid #ddd;
    padding-bottom: 2mm;
    page-break-after: avoid;
}
h3 {
    font-size: 12.5pt;
    margin: 5mm 0 2mm;
    color: #333;
    page-break-after: avoid;
}
h4 {
    font-size: 11pt;
    margin: 3mm 0 1.5mm;
    color: #555;
    page-break-after: avoid;
}
p { margin: 1.5mm 0 2.5mm; }
hr { border: none; border-top: 1px solid #ddd; margin: 5mm 0; }
blockquote {
    border-left: 3px solid #1a1a1a;
    padding: 2mm 4mm;
    margin: 3mm 0;
    background: #fafafa;
    font-style: italic;
    font-size: 11.5pt;
}
blockquote p { margin: 1mm 0; }
strong, b { color: #000; }
code {
    font-family: "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 9.5pt;
    background: #f1f1ef;
    padding: .3mm 1mm;
    border-radius: 1mm;
    color: #b91c1c;
}
pre {
    background: #f8f8f6;
    border-left: 2px solid #ddd;
    padding: 3mm 4mm;
    margin: 3mm 0;
    font-family: "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;
    font-size: 9pt;
    line-height: 1.4;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-word;
    page-break-inside: avoid;
}
pre code {
    background: transparent;
    color: #1a1a1a;
    padding: 0;
}
ul, ol { margin: 1.5mm 0 3mm 6mm; padding: 0; }
li { margin: .5mm 0; }
table {
    width: 100%;
    border-collapse: collapse;
    margin: 3mm 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
}
th, td {
    padding: 1.5mm 2mm;
    border-bottom: 1px solid #e5e5e5;
    vertical-align: top;
    text-align: left;
}
th {
    background: #1a1a1a;
    color: #fff;
    font-weight: 600;
}
tr:nth-child(even) td { background: #fafafa; }
.cover {
    text-align: center;
    padding: 30mm 0 8mm;
    border-bottom: 1px solid #ddd;
    margin-bottom: 6mm;
}
.cover .subtitle { color: #666; font-size: 11pt; margin-top: 2mm; }
.cover .meta { color: #999; font-size: 9pt; margin-top: 4mm; letter-spacing: .04em; }
.toc {
    background: #fafafa;
    border-left: 2px solid #1a1a1a;
    padding: 4mm 6mm;
    margin: 4mm 0 8mm;
    page-break-inside: avoid;
}
.toc h3 {
    margin: 0 0 2mm;
    font-size: 10pt;
    text-transform: uppercase;
    letter-spacing: .12em;
    color: #555;
}
.toc ol { margin: 0 0 0 5mm; }
.toc li { font-size: 9.5pt; padding: .3mm 0; }
.toc a { color: #1a1a1a; text-decoration: none; }
```

---

## Colors

Almost everything is **white and black**. That's on purpose.

- Page background: white (`#fff`)
- Text: near-black (`#1a1a1a`)
- Table headers: white text on black
- Alternating table rows: barely-gray (`#fafafa`)

**Red** shows up in one place only: inside inline `<code>` tags. It's a muted red (`#b91c1c`) that makes code names stand out from regular text.

**Orange boxes** are for "stop and read this" moments. Use them rarely -- only when something will break if the reader misses it:

```html
<div style="background:#fff7ed; border:2px solid #c2410c; padding:5mm 7mm; margin:6mm 0; page-break-inside:avoid;">
  <p style="margin:0 0 3mm; font-weight:700; color:#7c2d12; font-size:11.5pt;">
    Warning title
  </p>
  <p style="margin:0;">What the reader must know.</p>
</div>
```

No other colors. No green. No blue. No yellow.

---

## Code in pages

**Short code names** inside a sentence: use `<code>like this</code>`. Shows up red on gray.

**Longer code blocks**: wrap in `<pre><code>`:

```html
<pre><code>this is a code block
it keeps spacing
no syntax coloring</code></pre>
```

Shows up black on light gray with a line on the left side. Use it for file trees, command examples, JSON, diagrams.

---

## Tables

```html
<table>
  <thead><tr><th>Name</th><th>Value</th></tr></thead>
  <tbody>
    <tr><td>First</td><td>100</td></tr>
    <tr><td>Second</td><td>200</td></tr>
  </tbody>
</table>
```

Black header row. Alternating gray/white rows. Use tables for data, not for layout.

---

## Diagrams

Draw them with text characters inside `<pre><code>` blocks:

```
+---------+     +---------+     +---------+
| Step 1  | --> | Step 2  | --> | Step 3  |
+---------+     +---------+     +---------+
```

No images. No chart libraries. If you need something interactive, use JavaScript and mark it as a deviation.

---

## File names

Lowercase, words separated by dashes: `recall-engine.html`, `learning-engine.html`.

---

## Don't

- Don't add extra `<div>` wrappers
- Don't link external CSS or JS files
- Don't use emoji
- Don't write a "Summary" or "Conclusion" section
- Don't put subsections (h3, h4) in the table of contents -- only h2

---

# Part 2 — Code

Every Python file in this project follows these rules.

---

## Three rules

1. **No filler.** Don't write a comment that says what the next line already says. Don't add a docstring that restates the function name. If the code is clear, leave it alone.

2. **Fewer lines wins.** If you can do it in 15 lines, don't write 40. Don't make a class when a function works. Don't make a config file for a number that appears once.

3. **If you change something, say so.** If your code does something different from what the docs ask for:

```python
# [DEVIATES FROM SPEC: decision-engine.html]
# Using file lock instead of nonce -- simpler, same result.
```

Write it at the spot where the change is.

---

## Python 3, nothing else

- Standard library only. `os`, `json`, `hashlib`, `time`, `secrets`, `subprocess`, `re`, `pathlib`, `threading`, `tempfile`. No pip packages.
- LLM calls go through `claude -p --output-format json`. That's a command-line call, not an API call.

---

## Writing files safely

When you write to a shared file (like a JSON config or a gate file), never write directly. Write to a temporary file first, then rename it. This way, if something crashes halfway through, the old file is still intact.

```python
import os, json, tempfile

def atomic_write(path, data):
    tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(path))
    try:
        with os.fdopen(tmp_fd, 'w') as f:
            json.dump(data, f)
        os.rename(tmp_path, path)
    except:
        os.unlink(tmp_path)
        raise
```

---

## Gate files

A gate file is a tiny text file that holds either `0` (off) or `1` (on). That's the whole file -- one character. Reading one:

```python
def read_gate(root, name):
    path = os.path.join(root, "binaries", f"{name}.bin")
    try:
        return int(open(path).read().strip())
    except:
        return 0
```

Writing one uses the safe-write pattern above.

---

## Overlap

When you need to check if two things are talking about the same topic, compare their word sets:

```python
def overlap(a, b):
    shared = len(a & b)
    smallest = min(len(a), len(b))
    return shared / smallest if smallest > 0 else 0.0
```

`a` and `b` are sets of words. The result is 0.0 (nothing in common) to 1.0 (identical).

What the score means:
- **0.5 or higher** — same topic. Reinforce the existing entry.
- **0.25 to 0.5** — maybe the same. Look closer.
- **Below 0.25** — different topic.

---

## Logging

Append a JSON line to a file. That's the entire logging system.

```python
def write_log(directory, event, payload):
    path = os.path.join(LOGGER_ROOT, directory, f"{date.today()}.jsonl")
    line = json.dumps({"event": event, "ts": now_iso(), **payload})
    with open(path, "a") as f:
        f.write(line + "\n")
```

No log rotation. No log library. One line per event, one file per day.

---

## When things fail

Every engine follows the same recovery pattern:

1. Try up to 3 times.
2. If all 3 fail, set the engine's gate to `1` (this blocks the agent from using tools until it deals with it).
3. On the next user message, clear the gate automatically and try fresh.
4. On session start, clear all gates.

The agent can always run in a degraded state (missing one engine's output). It can never be permanently locked out.

---

## Don't

- Don't make classes when functions work
- Don't add type annotations everywhere -- only where it actually helps
- Don't use `async` -- use `threading` for parallelism
- Don't install pip packages
- Don't write test files with a framework -- plain `assert` in `if __name__ == "__main__"` is enough
- Don't put constants in environment variables -- they go in one JSON config file, read once at startup
- Don't make abstract base classes or interfaces
