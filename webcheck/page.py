#!/bin/env python3

"""
Collect metrics from arbitrary URLs
"""

import logging
import re
from time import time
from typing import Dict, Optional

import aiohttp

from webcheck.schema import PageMetrics

# using root logger for all modules
log = logging.getLogger()


def check_regex(text: str, regex: Optional[str] = None) -> Optional[bool]:
    """applies regex check on page text"""
    if not regex:
        return None
    return bool(re.search(regex, text))


class PageCheck:
    """check webpage

    For this application setup up new session per request.

    - instantiate a PageCheck per url
    - call check, response is returned as PageMetrics instance
    """

    def __init__(
        self,
        url: str,
        query_parms: Optional[Dict] = None,
        regex: Optional[str] = None,
        http_timeout: int = 30,
    ):
        """
        Args:

            url: page to check
            query_parms: optional query parameters
            regex: optional regex pattern
            http_timeout: end to end timeout in seconds
        """
        self.url = url
        self.query_parms = query_parms
        self.regex = regex
        self.http_timeout = http_timeout
        self.timeout = aiohttp.ClientTimeout(total=self.http_timeout)

    async def check(self) -> PageMetrics:
        """check page and return metrics

        This takes no args and is designed to be passed to consumer_loop as a writer.
        """
        metrics: PageMetrics
        start_time = time()
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            try:
                async with session.get(
                    self.url,
                    timeout=self.timeout,
                    params=self.query_parms,
                ) as response:
                    text = await response.text()
                    end_time = time()
                    regex_matched = check_regex(text, self.regex)
                    metrics = PageMetrics(
                        time=int(end_time),
                        url=self.url,
                        status=response.status,
                        response_time=round(end_time - start_time, 3),
                        regex_matched=regex_matched,
                    )
                    log.debug(f"response text: `{text}``")
                    return metrics
            except Exception:
                log.exception("PageCheck: exception - exiting")
                raise
