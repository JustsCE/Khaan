# Implementation Guide

---

# Part 1 — HTML Reports

Every HTML page in this project looks the same. Here's how.

---

## Three rules

1. **Say only what you mean.** No filler. If a sentence doesn't teach something, delete it.

2. **Keep it simple.** One file. One style block. No JavaScript unless you absolutely need it.

3. **If you change something, say so.** Write `[DEVIATES FROM SPEC]` right where the change is.

---

## Page skeleton

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
    </ol>
  </div>

  <h2 id="first">First section</h2>
  <p>Content goes here.</p>

</div>
</body>
</html>
```

Title at the top. Table of contents. Sections with `<h2>`. Horizontal lines between them. Everything inside one `div.page-wrap`.

---

## CSS

Paste this into every page. Don't change it.

```css
@page { size: A4; margin: 14mm 14mm 16mm 14mm; }
* { box-sizing: border-box; }
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    font-size: 10.5pt; line-height: 1.5; color: #1a1a1a; margin: 0; background: #f7f7f5;
}
.page-wrap {
    max-width: 200mm; margin: 0 auto; padding: 8mm;
    background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
@media print { body { background: #fff; } .page-wrap { box-shadow: none; max-width: none; padding: 0; } }
h1 { font-size: 26pt; margin: 0 0 4mm; letter-spacing: -.02em; line-height: 1.1; border-bottom: 2px solid #1a1a1a; padding-bottom: 3mm; }
h2 { font-size: 16pt; margin: 8mm 0 3mm; letter-spacing: -.01em; border-bottom: 1px solid #ddd; padding-bottom: 2mm; page-break-after: avoid; }
h3 { font-size: 12.5pt; margin: 5mm 0 2mm; color: #333; page-break-after: avoid; }
h4 { font-size: 11pt; margin: 3mm 0 1.5mm; color: #555; page-break-after: avoid; }
p { margin: 1.5mm 0 2.5mm; }
hr { border: none; border-top: 1px solid #ddd; margin: 5mm 0; }
blockquote { border-left: 3px solid #1a1a1a; padding: 2mm 4mm; margin: 3mm 0; background: #fafafa; font-style: italic; font-size: 11.5pt; }
blockquote p { margin: 1mm 0; }
strong, b { color: #000; }
code { font-family: "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; font-size: 9.5pt; background: #f1f1ef; padding: .3mm 1mm; border-radius: 1mm; color: #b91c1c; }
pre { background: #f8f8f6; border-left: 2px solid #ddd; padding: 3mm 4mm; margin: 3mm 0; font-family: "SF Mono", Menlo, Consolas, "Liberation Mono", monospace; font-size: 9pt; line-height: 1.4; overflow-x: auto; white-space: pre-wrap; word-break: break-word; page-break-inside: avoid; }
pre code { background: transparent; color: #1a1a1a; padding: 0; }
ul, ol { margin: 1.5mm 0 3mm 6mm; padding: 0; }
li { margin: .5mm 0; }
table { width: 100%; border-collapse: collapse; margin: 3mm 0; font-size: 9.5pt; page-break-inside: avoid; }
th, td { padding: 1.5mm 2mm; border-bottom: 1px solid #e5e5e5; vertical-align: top; text-align: left; }
th { background: #1a1a1a; color: #fff; font-weight: 600; }
tr:nth-child(even) td { background: #fafafa; }
.cover { text-align: center; padding: 30mm 0 8mm; border-bottom: 1px solid #ddd; margin-bottom: 6mm; }
.cover .subtitle { color: #666; font-size: 11pt; margin-top: 2mm; }
.cover .meta { color: #999; font-size: 9pt; margin-top: 4mm; letter-spacing: .04em; }
.toc { background: #fafafa; border-left: 2px solid #1a1a1a; padding: 4mm 6mm; margin: 4mm 0 8mm; page-break-inside: avoid; }
.toc h3 { margin: 0 0 2mm; font-size: 10pt; text-transform: uppercase; letter-spacing: .12em; color: #555; }
.toc ol { margin: 0 0 0 5mm; }
.toc li { font-size: 9.5pt; padding: .3mm 0; }
.toc a { color: #1a1a1a; text-decoration: none; }
```

---

## Colors

White and black. That's it.

- Red (`#b91c1c`) only inside `<code>` tags
- Orange box only when something will break if missed:

```html
<div style="background:#fff7ed; border:2px solid #c2410c; padding:5mm 7mm; margin:6mm 0;">
  <p style="margin:0 0 3mm; font-weight:700; color:#7c2d12; font-size:11.5pt;">Title</p>
  <p style="margin:0;">What will break.</p>
</div>
```

No green. No blue. No yellow.

---

## Diagrams

Text characters inside `<pre><code>`. No images. No chart libraries.

---

## Don't

- Don't add extra `<div>` wrappers
- Don't link external files
- Don't use emoji
- Don't write a "Summary" section
- Don't put h3/h4 in the table of contents

---

# Part 2 — Code

---

## Write less code

If it can be 10 lines, don't write 30. Don't add things "just in case." Don't write error handling for errors that won't happen. Don't add logging unless someone asked for logging. Don't add retry loops unless someone asked for retries.

The right amount of code is the least amount that does the job.

---

## Don't be clever

Write the obvious thing. If a function does one thing, make it do one thing in the obvious way. No tricks, no abstractions, no "what if we need this later."

```python
# good
def read_gate(path):
    return int(open(path).read().strip())

# bad
class GateReader:
    def __init__(self, config):
        self.config = config
    def read(self, name):
        path = self.config.get_gate_path(name)
        ...
```

---

## No unnecessary layers

- Don't make a class when a function works
- Don't make a config file for one number
- Don't make a wrapper around something that's already simple
- Don't make an abstract base class
- Don't make a factory

---

## Standard library only

Python 3. No pip. `os`, `json`, `hashlib`, `time`, `subprocess`, `re`, `pathlib`, `threading`, `tempfile`. That's your toolkit.

---

## If you change something, say so

```python
# [DEVIATES FROM SPEC: decision-engine.html]
# File lock instead of nonce. Simpler. Same result.
```

At the spot where it happens. Not in a changelog.

---

## Don't

- Don't add docstrings that restate the function name
- Don't add comments that describe what the next line does
- Don't add type annotations everywhere
- Don't use `async`
- Don't add a test framework
- Don't add error handling you weren't asked for
- Don't add fallback behavior you weren't asked for
- Don't add logging you weren't asked for
