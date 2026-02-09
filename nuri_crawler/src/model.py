
from dataclasses import dataclass
from typing import Optional

@dataclass
class BidItem:
    """Data model for a single bid announcement"""
    bid_no: str
    bid_name: str
    url: Optional[str] = None
    raw_data: Optional[dict] = None  # Store all extracted key-value pairs
    
    # Metadata
    crawled_at: Optional[str] = None

    def to_dict(self):
        return self.__dict__
