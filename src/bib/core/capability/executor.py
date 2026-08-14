from typing import Dict, Any, Type
from .base import Capability
from .metadata import CapabilityMetadata

class CapabilityExecutor:
    """
    The Runtime Engine responsible for executing Capabilities.
    
    It handles:
    - Discovery (optional)
    - Instantiation
    - Execution safety/logging (placeholder)
    - Result standardization
    """
    
    def __init__(self):
        self._registry: Dict[str, Type[Capability]] = {}

    def register(self, capability_cls: Type[Capability]) -> None:
        """Register a capability class."""
        # In a real scenario, we might instantiate to check ID, or use a class attribute
        # For now, we assume the class can be instantiated with metadata later,
        # or we register instances. Let's register classes and assume they define metadata.
        # This is a simplified implementation.
        pass

    def execute(self, capability: Capability, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a capability instance safely with full lifecycle (check -> execute -> validate).
        """
        # Here we would add logging, error handling, context setup, etc.
        print(f"Running capability: {capability.metadata.name} ({capability.metadata.id})")
        
        try:
            # 1. Lifecycle: Check inputs
            if not capability.check(inputs):
                raise ValueError(f"Invalid inputs for capability {capability.metadata.id}")

            # 2. Lifecycle: Execute
            results = capability.execute(inputs)

            # 3. Lifecycle: Validate outputs
            capability.validate(results)

            return results
        except Exception as e:
            # Wrap error or log it
            print(f"Error executing capability {capability.metadata.id}: {e}")
            raise e
