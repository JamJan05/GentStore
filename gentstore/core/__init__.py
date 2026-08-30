"""Domain logic — everything Gentstore knows about Portage.

This package is deliberately free of any Qt import. Every function here is
synchronous and knows nothing about threads; the graphical layer wraps the calls
it needs in :mod:`gentstore.ui.tasks`, and the diagnostic tool
(``python -m gentstore.core.cli``) calls exactly the same functions directly.
"""
