#!/bin/env python3


"""
Schema for data we collect and write
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PageMetrics:
    """schema for page result"""

    time: float
    url: str
    status: int
    response_time: float
    regex_matched: Optional[bool]
