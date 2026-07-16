"""Email-source parsers package."""

from src.parsers.base import EmailParser
from src.parsers.daily_dev import DailyDevParser
from src.parsers.generic import GenericParser

__all__ = ["EmailParser", "DailyDevParser", "GenericParser"]
