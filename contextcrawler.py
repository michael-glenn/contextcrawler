"""ContextCrawler — entry point.

Usage:
    py contextcrawler.py <url> [options]
    py contextcrawler.py --gui
    py contextcrawler.py --to-md my_file.pdf [--clean]
    py contextcrawler.py <url> --md-dir [output_dir]
"""
from url_to_pdf.cli import main

if __name__ == "__main__":
    main()
