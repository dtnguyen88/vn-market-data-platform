"""SSI WebSocket message parsers.

Exports parse functions that convert raw SSI dict payloads to validated Pydantic models.
"""

from .indices import parse_index
from .quotes_l1 import parse_quote_l1
from .quotes_l2 import parse_quote_l2
from .ticks import parse_tick

__all__ = ["parse_index", "parse_quote_l1", "parse_quote_l2", "parse_tick"]
