"""Public, read-only scenic catalog domain. D owns REST/MCP adapters."""

from .service import get_spot, load_catalog, search_spots

__all__ = ["get_spot", "load_catalog", "search_spots"]
