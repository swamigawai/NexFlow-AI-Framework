# Directive: Web Scraping Website

## Objective
Extract structured data from a target website reliably and ethically.

## Requirements
- Target URL
- CSS Selectors for data points
- Output format (JSON/CSV)

## Process
1. Validate the target URL.
2. Identify CSS selectors using browser developer tools.
3. Configure the `scrape_single_site.py` script.
4. Run the scraper and verify output.

## Guidelines
- Respect `robots.txt`
- Use reasonable timeouts and retries
- Do not overwhelm the target server
- Sanitize all extracted data
