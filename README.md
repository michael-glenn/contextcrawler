# ContextCrawler

A Python tool that crawls a website and converts its content into clean, structured documents — PDF or Markdown — optimised for use as context in large language models (LLMs).

---

## Why this exists

LLMs like Claude, GPT-4, and others are most useful when they have access to relevant, well-structured context. However, website content is often spread across dozens or hundreds of pages, full of navigation menus, ads, cookie banners, and other noise that wastes context window space and reduces quality.

**ContextCrawler** solves this by:

1. Crawling an entire website (or a portion of it) starting from a URL you provide
2. Extracting only the meaningful body text from each page
3. Automatically detecting and filtering site-wide navigation, ads, and widget noise
4. Producing clean output in your choice of format:
   - A **book-like PDF** — one chapter per page, with a table of contents
   - **Topic-grouped Markdown files** — one `.md` file per section, ready to feed directly to an LLM
5. Optionally converting any existing PDF to clean Markdown with a dedicated LLM-cleaning pass

Typical use cases include:
- Converting product documentation into structured context files for an AI assistant
- Capturing a help site or knowledge base for offline use or AI ingestion
- Archiving web content in a clean, readable format

---

## Requirements

- Python 3.10 or later
- Install dependencies:

```bash
py -m pip install -r requirements.txt
```

On first run, Playwright's Chromium browser will be downloaded automatically (~300 MB, one-time).

---

## Usage

### GUI (recommended)

Launch with no arguments to open the graphical interface:

```bash
py contextcrawler.py
```

Or explicitly:

```bash
py contextcrawler.py --gui
```

The GUI has three tabs:

**Crawl to PDF**
1. Enter a URL and click **Estimate site size** — performs a shallow scan and tells you roughly how many pages are reachable
2. Choose your crawl depth based on the estimate; the output filename is auto-suggested
3. Click **Start Crawl** — live progress is shown in the output panel

**Crawl to Markdown** *(recommended for LLM use)*
- Same two-step flow, but outputs topic-grouped `.md` files directly with no PDF intermediate
- Output folder is auto-suggested from the URL

**Convert PDF → Markdown**
- Pick an existing PDF and convert it to Markdown; the output path is auto-suggested
- Enable **Clean for LLM use** to strip TOC noise, page markers, nav blocks, and reflow paragraphs

---

### Command line

**Crawl a website to PDF:**

```bash
py contextcrawler.py https://example.com
```

```bash
# Specify depth and output file
py contextcrawler.py https://docs.example.com -d 2 -o docs.pdf

# Skip the site-size estimate, unlimited depth, slower crawl
py contextcrawler.py https://example.com --no-estimate -d 999 --delay 1.0
```

**Crawl directly to topic-grouped Markdown (recommended for LLMs):**

```bash
# Auto-named output directory
py contextcrawler.py https://docs.example.com --md-dir

# Custom directory name and depth
py contextcrawler.py https://docs.example.com -d 2 --md-dir my_docs
```

Output:
```
my_docs/
  index.md          ← table of contents
  api.md            ← all pages under /docs/api/
  guides.md         ← all pages under /docs/guides/
  _root.md          ← top-level pages
```

**Convert an existing PDF to Markdown:**

```bash
py contextcrawler.py --to-md my_document.pdf
```

**Convert and clean for LLM use:**

```bash
py contextcrawler.py --to-md my_document.pdf --clean
```

---

## Options

| Flag | Default | Description |
|---|---|---|
| `url` | — | Starting URL to crawl |
| `-o`, `--output` | auto-generated | Output file path |
| `-d`, `--depth N` | interactive | Maximum crawl depth (0 = homepage only) |
| `--delay SECONDS` | `0.5` | Politeness delay between requests |
| `--images` | off | Include image alt text and captions in PDF |
| `--no-estimate` | off | Skip the shallow site-size scan |
| `--md-dir [DIR]` | — | Crawl directly to topic-grouped Markdown files (no PDF) |
| `--to-md PDF_FILE` | — | Convert an existing PDF to Markdown |
| `--clean` | off | Strip layout noise from converted Markdown (use with `--to-md`) |
| `--gui` | — | Launch the graphical interface |

---

## How it works

### Crawling
- Uses **Playwright** (headless Chromium) to render each page, including JavaScript-heavy sites
- Collects content from all page frames, including inline `srcdoc` iframes used by some help-centre platforms
- Stays within the original domain; filters known ad networks and tracker domains
- Deduplicates pages so each URL appears only once regardless of how many links point to it
- **Automatic navigation detection**: after crawling, any link appearing on more than 50% of pages is identified as site-wide navigation and excluded from chapter link lists — fully site-agnostic, no configuration required
- Chromium is downloaded automatically on first run if not already present

### Content extraction
- **trafilatura** identifies and extracts the main body text, discarding navigation, headers, footers, and sidebars
- **Google Translate** widget text (language selectors, "Rate this translation", etc.) is filtered at extraction time
- Links are captured as human-readable **anchor text** rather than raw URLs; the URL is only shown when it was explicitly visible on the page
- Frames identified as translation widgets or language selectors are skipped entirely

### PDF generation
- **reportlab** builds the PDF with a cover page, auto-generated table of contents, one chapter per crawled page, and running headers and page numbers

### Direct Markdown output (`--md-dir`)
- Pages are written directly from the crawled `Page` objects — no PDF step
- Grouped by URL path segment: pages under `/docs/api/` go into `api.md`, etc.
- Each group file gets a heading, source URL, and clean body text
- An `index.md` table of contents links all group files
- Inline cleaning removes Google Translate noise and collapses excessive blank lines

### PDF → Markdown conversion (`--to-md`)
- **PyMuPDF** extracts text from the PDF, using font size and bold flags to detect headings

### LLM cleaning pass (`--to-md --clean`)

| Pass | What it removes |
|---|---|
| TOC section | Everything between "Table of Contents" and first chapter |
| Page markers | `--- *Page N*` separators |
| Dot leaders | `. . . . . 3` lines from TOC |
| Boilerplate lines | Generated date, copyright notices, table-cell artefacts |
| Google Translate text | "Original text", "Rate this translation", feedback prompts |
| URL clusters | Lines that are nothing but URLs |
| Site navigation blocks | Merged navigation dumps (detected by URL-density heuristic) |
| Language selectors | `› Select Language › Abkhaz ...` blocks |
| Link dump sections | "Links on this page:" + following URL list |
| Repeated running headers | Short lines appearing 3+ times across chapters |
| Empty chapters | Sections with no real prose after cleaning |
| Duplicate headings | Same heading appearing twice in a row |
| Broken paragraphs | Lines split mid-sentence are rejoined |

---

## Project structure

```
contextcrawler.py      Entry point
url_to_pdf/
  cli.py               Argument parsing and mode dispatch
  crawler.py           BFS crawler, nav-frequency analysis, progress display
  extractor.py         Playwright fetch + trafilatura extraction + widget filtering
  pdf_builder.py       reportlab PDF generation
  pdf_converter.py     PyMuPDF PDF -> Markdown conversion
  pdf_cleaner.py       LLM-optimised Markdown cleaning pipeline
  md_writer.py         Direct crawl -> topic-grouped Markdown files
  utils.py             URL normalisation, domain checks, ad filtering
  gui.py               customtkinter graphical interface
```

---

## Dependencies

| Package | Purpose |
|---|---|
| `playwright` | Headless browser for JS-rendered pages |
| `beautifulsoup4` | HTML parsing for link extraction |
| `trafilatura` | Main-body text extraction |
| `reportlab` | PDF generation |
| `pymupdf` | PDF text extraction (for `--to-md`) |
| `customtkinter` | GUI framework |
| `lxml` | HTML parser backend |

---

## Limitations

- **JavaScript-gated content** — pages that require login or interaction beyond initial load may not render fully
- **Rate limiting** — some sites block automated crawlers; increase `--delay` if you encounter errors
- **Very large sites** — use `-d 1` or `-d 2` for large sites; unlimited depth can produce enormous outputs
- **Images** — actual images are never embedded in the PDF; only alt text and captions are optionally included
- **PDF cleaning** — the `--clean` pass is heuristic-based; results may vary across PDF layouts and site structures

---

> **Note:** The GitHub repository is currently named `url-to-pdf`. To rename it, go to **Settings → General → Repository name** in GitHub. The internal Python package directory is also named `url_to_pdf` for backwards compatibility.
