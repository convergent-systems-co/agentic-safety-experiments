"""Persistent multi-agent debate experiment."""

from .harness import PersistentDebate
from .repository import SQLiteDebateRepository

__all__ = ["PersistentDebate", "SQLiteDebateRepository"]
