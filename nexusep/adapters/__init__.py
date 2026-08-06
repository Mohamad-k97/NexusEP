"""Strict adapters between canonical contracts and experimental backends."""

from nexusep.adapters.array_engine import ArrayEngineAdapter
from nexusep.adapters.object_engine import ObjectEngineAdapter

__all__ = ["ArrayEngineAdapter", "ObjectEngineAdapter"]
