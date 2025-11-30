#!/usr/bin/env python3
"""
epub_to_html.py
----------------

This script converts an ePub file exported with fixed‑layout pages into a single
HTML document that stacks each page vertically, preserving the original
layout.  It embeds all images, GIFs and fonts as data URIs so that the
resulting HTML file is self‑contained.

Usage
-----

    python epub_to_html.py input.epub [output.html]

If no output filename is supplied, the script will produce a file with the
same basename as the input but with a ``.html`` extension in the current
directory.

The script handles arbitrary numbers of pages.  It looks for page files
matching ``page-*.xhtml`` inside the ePub’s package directory (commonly
``OPS``).  For each page it extracts the body content, fixes any
self‑closing tags that are illegal in HTML (e.g. ``<div/>``), replaces
relative image references with data URIs, updates internal links to anchor
IDs, and appends it into the final document.  All fonts referenced in the
CSS are inlined as base64 data URIs.

The final document includes a small CSS overlay to centre the pages on a
dark background, add labels like “Page 1”, and cast a drop shadow.  The
dimensions of each page (595.28×841.89 px) correspond to the viewport
specified in the original ePub; if your ePub uses different viewport
dimensions you may need to adjust the constants at the top of the script.

Requirements
------------

This script uses only Python’s standard library (``zipfile``, ``argparse``,
``base64``, etc.), so no third‑party dependencies are needed.  It should
work on macOS, Linux or Windows, provided Python 3.6+ is installed.
"""

import argparse
import base64
import mimetypes
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, List, Optional


# Constants for page dimensions (A4 in points as exported by Pages)
PAGE_WIDTH = 595.28
PAGE_HEIGHT = 841.89


def natural_sort_key(s: str) -> List:
    """Return a list that can be used as a key for natural sorting.

    Splits the string into digit and non‑digit parts so that 'page-10'
    sorts after 'page-9'.
    """
    return [int(text) if text.isdigit() else text for text in re.split(r'(\d+)', s)]


def find_pages(root: Path) -> List[Path]:
    """Search for page files matching 'page-*.xhtml' under the given root.

    The function returns a list of Path objects sorted naturally by the numeric
    part of the filename.
    """
    pages = list(root.rglob('page-*.xhtml'))
    return sorted(pages, key=lambda p: natural_sort_key(p.name))


def read_css(root: Path) -> str:
    """Read and concatenate all CSS files under root/css.

    If no CSS directory is found, returns an empty string.
    """
    css_dir = next((p for p in (root / 'css').iterdir() if p.is_dir()), None) if (root / 'css').exists() else None
    if css_dir is None and (root / 'css').exists():
        # css is a directory itself
        css_dir = root / 'css'
    css = []
    if css_dir and css_dir.exists():
        for file in css_dir.iterdir():
            if file.suffix.lower() in {'.css', '.scss'}:
                css.append(file.read_text(encoding='utf-8'))
    return '\n'.join(css)


def embed_fonts(css: str, fonts_dir: Path) -> str:
    """Replace font URLs in the CSS with base64 data URIs.

    Only ``.ttf``, ``.otf``, ``.woff`` and ``.woff2`` files are considered.  If a
    referenced font cannot be found, the original URL is left unchanged.
    """
    # Preload and encode fonts
    font_data: Dict[str, str] = {}
    if fonts_dir.exists():
        for font_file in fonts_dir.iterdir():
            if font_file.is_file():
                ext = font_file.suffix.lstrip('.').lower()
                mime = {
                    'ttf': 'font/ttf',
                    'otf': 'font/otf',
                    'woff': 'font/woff',
                    'woff2': 'font/woff2',
                }.get(ext)
                if mime:
                    encoded = base64.b64encode(font_file.read_bytes()).decode('ascii')
                    font_data[font_file.name] = f'data:{mime};base64,{encoded}'

    def repl(match: re.Match[str]) -> str:
        font_path = match.group(1)
        fname = Path(font_path).name
        uri = font_data.get(fname)
        return f'url({uri})' if uri else match.group(0)

    # Replace url(..fonts/filename)
    css = re.sub(r'url\([^\)]+\/fonts\/([^\)]+)\)', repl, css)
    # Also replace url(fonts/filename)
    css = re.sub(r'url\(fonts\/([^\)]+)\)', repl, css)
    return css


def encode_images(images_dir: Path) -> Dict[str, str]:
    """Return a mapping from image filename to data URI.

    Supports GIF, PNG and JPEG.  Other types are ignored.
    """
    data = {}
    if images_dir.exists():
        for img in images_dir.iterdir():
            if not img.is_file():
                continue
            ext = img.suffix.lower().lstrip('.')
            mime = {
                'gif': 'image/gif',
                'png': 'image/png',
                'jpg': 'image/jpeg',
                'jpeg': 'image/jpeg'
            }.get(ext)
            if mime:
                encoded = base64.b64encode(img.read_bytes()).decode('ascii')
                data[img.name] = f'data:{mime};base64,{encoded}'
    return data


def fix_self_closing(html: str) -> str:
    """Convert self‑closing tags for non‑void elements into proper open/close tags.

    XHTML exported by Pages sometimes contains ``<div/>`` or ``<span/>``, which
    are invalid in HTML and confuse browsers.  This function replaces those
    patterns with ``<div></div>`` and ``<span></span>``.  Void elements
    (e.g. ``<img/>``) are left untouched.
    """
    non_void = [
        'div', 'span', 'p', 'bdi', 'a', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'section', 'article', 'header', 'footer', 'li', 'ul', 'ol', 'table',
        'tbody', 'td', 'tr', 'th', 'strong', 'em', 'b', 'i', 'small', 'big',
        'sup', 'sub', 'u'
    ]
    pattern = re.compile(r'<(' + '|'.join(non_void) + r')(\b[^>]*)/>')
    return pattern.sub(lambda m: f'<{m.group(1)}{m.group(2)}></{m.group(1)}>', html)


def replace_images_in_html(html: str, images: Dict[str, str]) -> str:
    """Replace relative image sources in the HTML with base64 data URIs."""
    def repl_src(m: re.Match[str]) -> str:
        fname = m.group(1)
        uri = images.get(fname)
        return f'src="{uri}"' if uri else m.group(0)

    def repl_url(m: re.Match[str]) -> str:
        fname = m.group(1)
        uri = images.get(fname)
        return f'url({uri})' if uri else m.group(0)

    html = re.sub(r'src="images/([^"/]+)"', repl_src, html)
    html = re.sub(r'url\(images/([^\)]+)\)', repl_url, html)
    return html


def extract_body_content(page_path: Path) -> str:
    """Extract the HTML between <body> and </body> from an XHTML page."""
    text = page_path.read_text(encoding='utf-8')
    m = re.search(r'<body[^>]*>(.*)</body>', text, re.DOTALL)
    if not m:
        return ''
    body = m.group(1).strip()
    return body


def build_html_document(pages: List[str], css: str) -> str:
    """Assemble the final HTML document from page contents and CSS."""
    parts: List[str] = []
    parts.append('<!DOCTYPE html>')
    parts.append('<html lang="fr">')
    parts.append('<head>')
    parts.append('<meta charset="utf-8">')
    parts.append('<title>Document EPUB converti</title>')
    parts.append('<style>')
    parts.append(css)
    parts.append('html, body { margin:0; padding:0; background:#111; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }')
    parts.append('body { position: static !important; }')
    parts.append('.wrapper { max-width: 635px; margin:0 auto; padding:2rem 0; }')
    parts.append('h1 { color:#f5f5f5; text-align:center; margin-bottom:2rem; font-size:1.5rem; font-weight:600; }')
    parts.append('.page-label { color:#ccc; text-align:center; margin:0 0 .5rem; font-size:0.85rem; letter-spacing:0.08em; text-transform:uppercase; }')
    parts.append(f'.page {{ position: relative; width: {PAGE_WIDTH}px; height: {PAGE_HEIGHT}px; margin:0 auto 3rem; background:#fff; box-shadow:0 0 20px rgba(0,0,0,0.3); overflow:hidden; }}')
    parts.append('.page .body { position: relative; }')
    parts.append('</style>')
    parts.append('</head>')
    parts.append('<body>')
    parts.append('<div class="wrapper">')
    parts.append('<h1>Document converti</h1>')
    for idx, content in enumerate(pages, 1):
        parts.append(f'<p class="page-label">Page {idx}</p>')
        parts.append(f'<div class="page page-{idx}" id="page-{idx}">')
        parts.append(content)
        parts.append('</div>')
    parts.append('</div>')
    parts.append('</body>')
    parts.append('</html>')
    return '\n'.join(parts)


def convert_epub(epub_path: Path, output_path: Path) -> None:
    """Main conversion routine."""
    # Create a temporary directory to extract the ePub
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        # Unzip ePub
        with zipfile.ZipFile(epub_path, 'r') as zf:
            zf.extractall(tmp_path)
        # Determine the OPS/root directory.  In Apple exports it is often 'OPS',
        # but we search for a directory containing page-*.xhtml.
        root = None
        for candidate in tmp_path.rglob('page-1.xhtml'):
            root = candidate.parent
            break
        if root is None:
            # fallback: look for any page-*.xhtml
            pages_found = list(tmp_path.rglob('page-*.xhtml'))
            if not pages_found:
                raise RuntimeError('Could not locate any page-*.xhtml files in the EPUB')
            root = pages_found[0].parent
        # Locate CSS and fonts directories
        css_text = read_css(root)
        fonts_dir = root / 'fonts'
        css_text = embed_fonts(css_text, fonts_dir)
        # Encode images
        images_dir = root / 'images'
        images = encode_images(images_dir)
        # Process pages
        page_files = find_pages(root)
        pages_html: List[str] = []
        for page in page_files:
            body = extract_body_content(page)
            if not body:
                continue
            body = fix_self_closing(body)
            body = replace_images_in_html(body, images)
            # Convert internal links to anchors
            body = re.sub(r'href="page-(\d+)\.xhtml"', r'href="#page-\1"', body)
            pages_html.append(body)
        if not pages_html:
            raise RuntimeError('No pages could be processed from the EPUB')
        # Build final document
        final_html = build_html_document(pages_html, css_text)
        output_path.write_text(final_html, encoding='utf-8')


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Convert fixed‑layout ePub to a single HTML document.')
    parser.add_argument('epub', type=Path, help='Input ePub file')
    parser.add_argument('output', nargs='?', type=Path, help='Output HTML file (default: same basename with .html)')
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)
    epub_path: Path = args.epub
    if not epub_path.is_file():
        print(f"Error: input file {epub_path} does not exist", file=sys.stderr)
        sys.exit(1)
    output_path: Path
    if args.output:
        output_path = args.output
    else:
        output_path = epub_path.with_suffix('.html')
    try:
        convert_epub(epub_path, output_path)
    except Exception as exc:
        print(f'Failed to convert {epub_path}: {exc}', file=sys.stderr)
        sys.exit(1)
    print(f'Converted {epub_path} -> {output_path}')


if __name__ == '__main__':
    main()