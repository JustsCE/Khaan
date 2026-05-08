# Implementation Guide

How to build HTML reports for this project. Every rule below is extracted from the 8 golden docs in this folder. Follow them exactly.

---

## Principles

1. **No AI slop.** Do exactly what is asked. No filler paragraphs, no "in conclusion" summaries, no restating the obvious. Every sentence earns its place or gets cut.

2. **KISS.** Simplest path to the goal. Measure in LOC -- fewer is better. One CSS block, one page-wrap div, semantic HTML. No frameworks, no build steps, no JavaScript unless the content demands it (graphs).

3. **Deviations.** If anything in the output deviates from what the docs specify, mark it:

```html
<p><strong>[DEVIATES FROM SPEC]</strong> reason here.</p>
```

Visible. Inline. No footnotes, no appendix. The reader sees it where it matters.

---

## HTML structure

Every report follows this skeleton. Taken directly from the golden docs.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{{TITLE}}</title>
<style>
  /* full CSS block -- see next section */
</style>
</head>
<body>
<div class="page-wrap">

  <div class="cover">
    <h1 style="border:none">{{TITLE}}</h1>
    <div class="subtitle">{{ONE-LINE DESCRIPTION}}</div>
    <div class="meta">{{DATE}} · JustsCE/Khaan</div>
  </div>

  <div class="toc"><h3>Contents</h3>
    <ol>
      <li><a href="#section-id">Section name</a></li>
    </ol>
  </div>

  <h2 id="section-id">Section name</h2>
  <!-- content -->

</div>
</body>
</html>
```

- One `div.page-wrap` per document. Nothing outside it.
- Cover block: centered title, subtitle in `#666`, meta line in `#999`.
- TOC: left-bordered box, `#fafafa` background, uppercase heading, ordered list of anchor links.
- Sections separated by `<hr>`.

---

## CSS spec

Copy this block verbatim into every report. It is the exact stylesheet from the golden docs.

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
.cover .subtitle {
    color: #666;
    font-size: 11pt;
    margin-top: 2mm;
}
.cover .meta {
    color: #999;
    font-size: 9pt;
    margin-top: 4mm;
    letter-spacing: .04em;
}
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

## Color rules

**Dominantly white.** The page is white (`#fff`). Body background is `#f7f7f5` (barely off-white). Alternating table rows are `#fafafa`. That is the entire palette for normal content.

**Black for text.** Body text is `#1a1a1a`. Headings h3 use `#333`, h4 use `#555`. Table headers are white-on-black (`#1a1a1a` background, `#fff` text).

**Red: inline code only.** The only red in the golden docs is `#b91c1c` on inline `<code>` elements. This is a muted red, not a bright warning red. It distinguishes code tokens from prose. That is its only use.

**Orange callout boxes.** For mechanical enforcement warnings or critical contract details. Used sparingly (2-3 times across all 8 docs). The pattern:

```html
<div style="background:#fff7ed; border:2px solid #c2410c; padding:5mm 7mm; margin:6mm 0; page-break-inside:avoid;">
  <p style="margin:0 0 3mm; font-weight:700; color:#7c2d12; font-size:11.5pt;">
    Title of the callout
  </p>
  <p style="margin:0 0 3mm;">Body text.</p>
</div>
```

Use these for things that MUST NOT be missed. Not for general notes. Not for "nice to know." If it's not mechanically load-bearing, it doesn't get a box.

**No other colors.** No green for success. No yellow for warnings. No blue for info. No gradients. No colored backgrounds on sections.

---

## Code blocks

Two types in the golden docs:

### Inline code

```html
<code>file_name.py</code>
```

Rendered: `#b91c1c` text on `#f1f1ef` background, 9.5pt monospace, 1mm padding. Use for file paths, function names, config keys, binary names, any token that is a literal identifier.

### Block code

```html
<pre><code>multi-line code here
preserves whitespace
no syntax highlighting</code></pre>
```

Rendered: `#f8f8f6` background, 2px left border in `#ddd`, 9pt monospace. Text is `#1a1a1a` (black, not red -- `pre code` overrides inline code color). Use for:
- File tree diagrams
- Command sequences
- JSON schemas
- ASCII flow charts
- Pinned prompts

No syntax highlighting. The golden docs use none. Keep it that way.

---

## Tables

```html
<table>
  <thead><tr><th>Header</th><th>Header</th></tr></thead>
  <tbody>
    <tr><td>Cell</td><td>Cell</td></tr>
  </tbody>
</table>
```

- Full width, collapsed borders.
- Header row: white text on `#1a1a1a` black background.
- Even rows: `#fafafa` background.
- Bottom borders only (`1px solid #e5e5e5`).
- 9.5pt font size.
- Avoid page breaks inside tables.

Use tables for structured data: binary lists, scoring signals, phase summaries, hook dispatch tables. Not for prose.

---

## Blockquotes

```html
<blockquote>
  <p><strong>The key statement.</strong></p>
  <p><strong>Another key statement.</strong></p>
</blockquote>
```

Used at the top of each doc section as a philosophy declaration. 3px solid black left border, `#fafafa` background, italic, 11.5pt. Bold the content inside. Use only for foundational statements that frame everything below them.

---

## Graphs and diagrams

The golden docs use ASCII art inside `<pre><code>` blocks for:
- Flow diagrams (box-and-arrow style with `+--+` boxes and `-->` arrows)
- Bar charts (using block characters like `████`)
- Tree structures (using `├──`, `└──`, `│`)
- State machines (using `→` arrows)

No images. No SVG. No canvas. No charting libraries. If a visualization is needed, build it in ASCII inside a `<pre>` block.

**Exception:** If a graph requires interactivity or is too complex for ASCII (e.g., a real-time 3D brain mesh), then and only then use JavaScript. Mark it:

```html
<!-- [DEVIATES FROM SPEC] Interactive graph requires JS. ASCII insufficient for this visualization. -->
```

---

## Document naming

Golden docs use lowercase-kebab-case: `brain.html`, `recall-engine.html`, `learning-engine.html`.

Implementation reports follow the same pattern. No camelCase, no underscores, no spaces.

---

## What NOT to do

- No `<div>` wrappers beyond `page-wrap`. The golden docs use flat semantic HTML.
- No CSS classes beyond the ones in the spec above. Inline styles for one-off callout boxes only.
- No external stylesheets. CSS is in a `<style>` block in the `<head>`.
- No `<script>` tags unless the content demands interactivity.
- No emoji.
- No "Summary" or "Conclusion" sections. The content ends when the content ends.
- No table of contents entries for subsections (h3/h4). TOC lists h2 sections only.
- No numbered figure captions.
- No footer.
