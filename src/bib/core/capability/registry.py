
from typing import Dict, Type, Optional
import sys
import os
from stack.src.bib.core.capability import Capability


class CapabilityRegistry:
    """
    Singleton registry for all available capabilities in the system.
    """
    _instance = None
    _capabilities: Dict[str, Type[Capability]] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CapabilityRegistry, cls).__new__(cls)
        return cls._instance

    @classmethod
    def register(cls, capability_cls: Type[Capability]):
        """
        Registers a capability class.
        The capability must have a METADATA class attribute with a unique ID.
        """
        if not issubclass(capability_cls, Capability):
             raise ValueError(f"Class {capability_cls} must inherit from Capability")
        
        # Access metadata from the class directly
        if not hasattr(capability_cls, 'METADATA'):
            raise ValueError(f"Capability {capability_cls.__name__} must have METADATA class attribute")
            
        metadata = capability_cls.METADATA
        cls._capabilities[metadata.id] = capability_cls

    @classmethod
    def register_from(cls, repository):
        """Registers all capabilities from a repository."""
        for cap_cls in repository.get_capabilities():
            cls.register(cap_cls)

    @classmethod
    def get(cls, capability_id: str) -> Optional[Type[Capability]]:
        """Retrieves a capability class by ID."""
        return cls._capabilities.get(capability_id)

    @classmethod
    def get_all(cls) -> Dict[str, Type[Capability]]:
        """Returns all registered capabilities."""
        return cls._capabilities.copy()
    
    @classmethod
    def filter(cls, query: str = None) -> Dict[str, Type[Capability]]:
        """
        Returns capabilities. If query is provided, filters by ID.
        """
        if not query:
            return cls.get_all()
            
        return {
            cid: cap_cls for cid, cap_cls in cls._capabilities.items() 
            if query.lower() in cid.lower()
        }
