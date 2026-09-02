"""The GentStore website — a small FastAPI application serving a static landing page.

The page has no database and no outbound calls: everything it shows is read from
``website/content/*.json`` and from the screenshots and the icon that already live
in the repository.
"""

__all__ = ["__version__"]

__version__ = "1.0.0"
