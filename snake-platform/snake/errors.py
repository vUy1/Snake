"""Exceptions raised by the SDK."""

from __future__ import annotations


class SnakeError(Exception):
    """Base class for everything this package raises."""


class SubmissionError(SnakeError):
    """A submission file could not be loaded or does not meet the contract."""


class PolicyError(SnakeError):
    """A controller raised while deciding a move."""
