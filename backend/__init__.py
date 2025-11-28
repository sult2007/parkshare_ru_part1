"""
Top-level package marker for the Django project.
Ensures the project package has a concrete module file so multiprocessing
on Windows (used by Celery's prefork pool) can resolve the project
location without raising errors when __file__ is missing.
"""

# Expose Celery app for shared imports
from backend.backend.config.celery import app as celery_app

__all__ = ("celery_app",)
