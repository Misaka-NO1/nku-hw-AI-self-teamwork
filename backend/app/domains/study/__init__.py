"""Public study catalog domain. D owns authentication and transport adapters."""

from .service import get_material, load_catalog, resolve_download, search_materials

__all__ = ["get_material", "load_catalog", "resolve_download", "search_materials"]
