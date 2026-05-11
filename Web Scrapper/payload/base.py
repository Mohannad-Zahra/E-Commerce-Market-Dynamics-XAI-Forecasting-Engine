"""
payload/base.py
─────────────────────────────────────────────────────────────────────
Abstract base class for retailer scrapers.

Defines the required interface and generic helpers, enforcing the
hardcoded 5.0-7.0 second randomized delay required by compliance rules.
─────────────────────────────────────────────────────────────────────
"""

import abc
import random
import time
import requests
import logging

logger = logging.getLogger("payload.base")

class ScraperPayload(abc.ABC):
    """
    Abstract interface that all retailer scrapers must implement.
    """
    
    @abc.abstractmethod
    def run(self) -> list[dict]:
        """
        Execute the scraping operations.
        
        Returns:
            list[dict]: A list of records complying with the Bronze schema.
        """
        pass
    
    def polite_delay(self):
        """
        HARDCODED compliance delay.
        Enforces a 5.0 to 7.0 second randomly distributed delay between requests.
        """
        delay = random.uniform(5.0, 7.0)
        logger.debug("Applying polite delay of %.2f seconds.", delay)
        time.sleep(delay)
        
    def fetch_page(self, url: str, **kwargs) -> requests.Response:
        """
        Fetch a URL with User-Agent rotation and mandatory polite delay.
        """
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/114.0"
        ]
        headers = kwargs.pop("headers", {})
        if "User-Agent" not in headers and "user-agent" not in headers:
            headers["User-Agent"] = random.choice(user_agents)
            
        self.polite_delay()
        logger.info("Fetching: %s", url)
        
        response = requests.get(url, headers=headers, timeout=15, **kwargs)
        response.raise_for_status()
        return response

    def validate_record(self, record: dict) -> bool:
        """
        Validate that a record matches the mandatory Bronze layer schema.
        """
        required = [
            "scrape_timestamp", "retailer_id", "raw_title", 
            "raw_current_price", "product_url", "category",
        ]
        for field in required:
            if field not in record or not record[field]:
                logger.warning("Record failed validation. Missing/empty '%s'.", field)
                return False
        return True
