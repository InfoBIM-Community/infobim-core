from typing import Any, List
from pathlib import Path


class IfcTargetModelReader:
    """Read what creating products in a target model depends on."""

    @staticmethod
    def metres_per_length_unit(model_path: Path) -> float:
        """
        Return how many metres one length unit of the model measures.

        A model that assigns no length unit yet is given the SI metre by
        the unit state of the creation machine, so it measures in metres.
        """
        import ifcopenshell
        import ifcopenshell.util.unit

        model: Any = ifcopenshell.open(str(model_path))
        return float(ifcopenshell.util.unit.calculate_unit_scale(model))

    @staticmethod
    def product_names(model_path: Path) -> List[str]:
        import ifcopenshell

        model: Any = ifcopenshell.open(str(model_path))
        return [
            product.Name
            for product in model.by_type("IfcProduct")
            if isinstance(product.Name, str)
        ]
