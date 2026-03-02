import requests
from bs4 import BeautifulSoup
import json
import argparse
import logging
import sys
import os
import time
import random
from urllib.parse import urlparse
from typing import Dict, Any, Optional

from execution.utils.logging_config import setup_logging
from execution.utils.retry_handler import exponential_backoff
from execution.utils.validators import (
    validate_url, validate_selectors, sanitize_filename, ValidationError
)

logger = setup_logging()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
]

class Scraper:
    def __init__(self, timeout: int = 30, use_random_agent: bool = True):
        self.timeout = timeout
        self.session = requests.Session()
        self.use_random_agent = use_random_agent
        self.set_user_agent()

    def set_user_agent(self) -> None:
        """Sets a random user agent from the pool to avoid basic blocking."""
        agent = random.choice(USER_AGENTS) if self.use_random_agent else USER_AGENTS[0]
        self.session.headers.update({
            "User-Agent": agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        })

    @exponential_backoff(max_retries=3, base_delay=2.0)
    def fetch_page(self, url: str) -> str:
        """Fetches the page content with exponential backoff and retry logic."""
        logger.info(f"Fetching URL: {url}", extra={"action": "fetch", "url": url})
        
        try:
            validate_url(url)
        except ValidationError as ve:
            logger.error(f"URL Validation error: {ve}", extra={"url": url})
            raise

        # Check robots.txt generically (stubbed, real impl would use urllib.robotparser)
        domain = urlparse(url).netloc
        logger.debug(f"Targeting domain: {domain}")
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            logger.info(f"Successfully fetched URL: {url} (Status: {response.status_code})")
            return response.text
        except requests.exceptions.Timeout as e:
            logger.error(f"Request timeout for {url}: {e}")
            raise
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e} (Status: {e.response.status_code})")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Connection error for {url}: {e}")
            raise

    def parse_html(self, html: str, selectors: dict) -> dict:
        """Parses HTML content using strict CSS selectors."""
        logger.info("Parsing HTML content", extra={"action": "parse"})
        try:
            validate_selectors(selectors)
        except ValidationError as ve:
            logger.error(f"Selector Validation error: {ve}")
            raise

        try:
            soup = BeautifulSoup(html, 'lxml')
        except Exception as e:
            logger.error(f"Error parsing HTML with lxml: {e}")
            raise

        results = {}
        for key, selector in selectors.items():
            elements = soup.select(selector)
            if elements:
                if len(elements) == 1:
                    results[key] = elements[0].get_text(strip=True)
                else:
                    results[key] = [el.get_text(strip=True) for el in elements]
                logger.debug(f"Found {len(elements)} elements for selector: {selector}")
            else:
                results[key] = None
                logger.warning(f"No elements found for selector: {selector} (key: {key})")
                
        return results

    def _save_output(self, data: dict, output_path: str) -> None:
        """Saves data to a specified output file safely."""
        try:
            dir_name = os.path.dirname(output_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            
            # Simple atomic write
            temp_path = f"{output_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            os.replace(temp_path, output_path)
            
            logger.info("Data saved successfully", extra={"output_path": output_path})
        except IOError as e:
            logger.error(f"Failed to save data to {output_path}: {e}")
            raise

    def run(self, url: str, selectors: dict, output_path: str) -> dict:
        """Main execution flow for scraping a single site."""
        logger.info("Starting scrape run", extra={"url": url})
        start_time = time.time()
        
        try:
            html = self.fetch_page(url)
            data = self.parse_html(html, selectors)
            self._save_output(data, output_path)
            
            execution_time = round(time.time() - start_time, 2)
            logger.info("Scraping completed successfully", extra={
                "url": url,
                "output_path": output_path,
                "execution_time_s": execution_time,
                "status": "success",
                "extracted_keys": list(data.keys())
            })
            return data
            
        except Exception as e:
            execution_time = round(time.time() - start_time, 2)
            logger.error(f"Scraping workflow failed: {str(e)}", extra={
                "url": url,
                "execution_time_s": execution_time,
                "status": "error"
            })
            # Raising instead of exiting to allow caller to handle
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Production Web Scraper")
    parser.add_argument("--url", required=True, help="Target URL to scrape (must include scheme)")
    parser.add_argument("--selectors", required=True, type=json.loads, 
                        help="JSON string of CSS selectors (e.g. '{\"title\": \"h1\"}')")
    parser.add_argument("--output", required=True, help="Path to save output JSON file")
    parser.add_argument("--timeout", type=int, default=30, help="Request timeout in seconds")
    parser.add_argument("--no-random-agent", action="store_true", help="Disable random user agent rotation")
    
    try:
        args = parser.parse_args()
    except argparse.ArgumentError as e:
        logger.critical(f"Argument parsing failed: {e}")
        sys.exit(1)
    
    scraper = Scraper(timeout=args.timeout, use_random_agent=not args.no_random_agent)
    try:
        scraper.run(args.url, args.selectors, args.output)
    except Exception:
        sys.exit(1)
