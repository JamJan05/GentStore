"""Qt models — the adaptation layer between ``core`` and the widgets.

Nothing here computes anything about packages; it takes what ``core`` returns
and presents it the way Qt's item views expect. The direction of dependency is
one-way: ``ui → models → core``.
"""

from .packages import PackageListModel
from .update import MergePreviewModel

__all__ = ["MergePreviewModel", "PackageListModel"]
