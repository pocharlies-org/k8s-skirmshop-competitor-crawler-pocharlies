"Adapter registry for competitor site scrapers."
from .base import BaseSiteAdapter
from .generic_html import GenericHtmlAdapter

__all__ = ["BaseSiteAdapter", "GenericHtmlAdapter"]
