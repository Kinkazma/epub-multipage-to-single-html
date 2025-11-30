# epub-multipage-to-single-html

`epub-multipage-to-single-html` is a small command-line tool written in Python
that converts a **fixed-layout ePub** (for example, one exported from Apple
Pages) into a **single standalone HTML file**:

- all pages (`page-1.xhtml`, `page-2.xhtml`, …) are stacked vertically,
- the absolute layout of each page is preserved (facsimile),
- images, animated GIFs and fonts are embedded as **base64 data URIs**,
- the result is a **self-contained HTML file** (no external assets required).

The generated HTML displays each page in a white “sheet” centered on a dark
background, with a subtle drop shadow and an optional page label (“Page 1”,
“Page 2”, …).


## Features

- Automatically opens the ePub (ZIP) into a temporary directory.
- Detects and sorts page files matching `page-*.xhtml` in natural numeric order.
- Extracts only the `<body>…</body>` content of each page.
- Fixes self-closing tags that are invalid in HTML (`<div />` → `<div></div>`,
  `<span />` → `<span></span>`, etc.).
- Inlines fonts (`.ttf`, `.otf`, `.woff`, `.woff2`) referenced in CSS as
  base64 data URIs.
- Inlines images (`.png`, `.gif`, `.jpg`, `.jpeg`) as base64 data URIs.
- Rewrites internal links `href="page-N.xhtml"` to anchor links `href="#page-N"`.
- Wraps each page in a `.page` container with fixed dimensions and a drop shadow.
- Adds a small CSS overlay to center pages on a dark background and to show
  configurable page labels.


## How it works

At a high level, the tool performs the following steps:

1. **Detect the package root** inside the ePub (commonly a directory like `OPS/`),
   then list all files in it.
2. **Locate page files** whose names match `page-*.xhtml` and sort them by page
   number (e.g. `page-1.xhtml`, `page-2.xhtml`, `page-10.xhtml`).
3. **Load CSS** from the `css/` directory in the package root (such as
   `css/book.css`), then replace any `url(../fonts/FontName.ttf)` references
   with base64 data URIs by reading the corresponding files under `fonts/`.
4. **Inline images** by scanning the `images/` directory in the package root,
   reading each file and converting it to a `data:image/*;base64,...` URI. All
   `<img src="images/…">` attributes in page HTML are replaced with these data
   URIs.
5. **Fix self-closing tags** that are legal in XHTML but not in HTML (e.g.
   `<div/>`, `<span/>`). These are rewritten as paired opening/closing tags so
   that browsers render them consistently inside a larger HTML document.
6. **Append each page** into the final document inside a wrapper like:
   - a page label paragraph: `<p class="page-label">Page N</p>`,
   - a page container: `<div class="page page-N" id="page-N">…page content…</div>`.
7. **Apply a small CSS overlay** that:
   - sets a dark page background (`#111`),
   - centers a `.wrapper` column of ~635 px width,
   - defines `.page` as `position: relative; width: 595.28px; height: 841.89px;`
     with a white background and box shadow,
   - prevents overflow outside each page container.

The default page dimensions (595.28×841.89 px) match the viewport used by A4-ish
fixed-layout ePubs exported from Apple Pages. If your ePub uses different
viewport dimensions, you can adjust the constants at the top of the script.


## Quick start

### 1. Requirements

- Python **3.6+**
- No third-party libraries required (only standard library modules such as
  `zipfile`, `argparse`, `base64`, `tempfile`, etc.).
- Works on macOS, Linux and Windows.

Clone or download this repository, then place your ePub file in the same
directory as `epub_to_html.py`.


### 2. Basic usage

Convert an ePub and create an HTML file with the same basename in the current
directory:

```bash
python3 epub_to_html.py MyBook.epub
```

This will produce:

- `MyBook.html` in the same directory as `MyBook.epub`.

Convert an ePub and explicitly choose the output path/filename:

```bash
python3 epub_to_html.py MyBook.epub /path/to/output.html
```

This will produce:

- `/path/to/output.html` regardless of the input filename.


### 3. Usage from anywhere

If you want to run the script from any directory, you can either:

- add the repository directory to your `PATH`, or
- call it with an explicit path, for example:

```bash
python3 /path/to/epub-multipage-to-single-html/epub_to_html.py MyBook.epub
```


## Script reference: `epub_to_html.py`

### Synopsis

```bash
python epub_to_html.py input.epub [output.html]
```

- If `output.html` is **omitted**, the script creates a file with the same base
  name as `input.epub`, but with a `.html` extension in the current directory.
- If `output.html` is **provided**, it is used as the exact path of the output
  file (directories will be created if needed).

### Behaviour

The script:

- handles an arbitrary number of pages (it is not hard-coded to 12 or any
  specific number),
- looks for page files matching `page-*.xhtml` inside the ePub’s package
  directory (commonly something like `OPS/`),
- for each page:
  - extracts the `<body>…</body>` content,
  - fixes XHTML-style self-closing tags that are illegal in HTML (e.g.
    `<div/>`, `<span/>`),
  - replaces relative image references (`src="images/whatever.png"`) with
    base64 data URIs,
  - updates internal links `href="page-N.xhtml"` to anchor IDs
    `href="#page-N"`,
  - appends the processed content into the final HTML document.

All fonts referenced in the CSS via `url(...)` are inlined as base64 data URIs.
The resulting HTML file is completely self-contained: you can send it by email,
drop it on a web server or open it locally without any additional assets.

The final document includes a minimal CSS overlay to centre the pages on a dark
background, add labels like “Page 1”, and cast a drop shadow.  The default
dimensions of each page (595.28×841.89 px) correspond to the viewport used by
the original ePub; if your ePub uses different viewport dimensions you may need
to adjust the constants at the top of the script.


## Limitations and assumptions

- The tool assumes a **fixed-layout** ePub where each page is represented as a
  separate `page-N.xhtml` file and elements are positioned absolutely.
- It expects a structure similar to:

  - `OPS/page-1.xhtml`, `OPS/page-2.xhtml`, …
  - `OPS/css/book.css` (or similar CSS files)
  - `OPS/images/…` for images and GIFs
  - `OPS/fonts/…` for font files

- Reflowable ePubs (where content is not laid out in fixed pages) will still
  be processed, but the result may not resemble the original reading
  experience.
- Extremely large ePubs with many high-resolution images will produce large
  HTML files, since everything is embedded as base64. This is a deliberate
  tradeoff in favour of portability and self-contained documents.


## License

- MIT License
