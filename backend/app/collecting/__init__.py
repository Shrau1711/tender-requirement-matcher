"""Collecting manufacturer documents from the web, and recording where each one came from.

crawl.py finds the catalogue PDFs a manufacturer links from its own site (pure logic, the fetcher is passed in);
download.py fetches politely (robots.txt, a pause between requests) and saves each PDF once by its hash;
sources.py records every saved file's address, page, date and hash, and lists any document whose source is not recorded;
add.py adds one document from the web app (uploaded, or fetched from an address) with the same code, and records it in sources.csv.
scripts/run/crawl_catalogues.py runs them from the command line.
"""
