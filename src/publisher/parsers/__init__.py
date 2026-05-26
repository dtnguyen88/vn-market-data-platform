"""SSI v3 wire-dict parsers — one per topic prefix.

Each parser consumes the raw `data` dict from a `{channel, topic, data}`
frame and returns a Pydantic schema instance ready for Pub/Sub publish.

Existing `parse_index` removed: index values come from REST polling, not
the stream. See src/publisher/index_poller.py (TODO).
"""

from .foreign_room import parse_foreign_room
from .odd_lot import parse_odd_lot
from .put_through import parse_put_through
from .quotes_l1 import parse_quote_l1
from .quotes_l2 import parse_quote_l2
from .ticks import parse_tick

__all__ = [
    "parse_foreign_room",
    "parse_odd_lot",
    "parse_put_through",
    "parse_quote_l1",
    "parse_quote_l2",
    "parse_tick",
]
