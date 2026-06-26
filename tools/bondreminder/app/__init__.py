"""Core BondReminder business package.

HTTP handling now lives in ``tools.bondreminder.django_app``.  The original
business modules in this package are intentionally kept importable without
Flask so Django can reuse the existing reminder logic directly.
"""
