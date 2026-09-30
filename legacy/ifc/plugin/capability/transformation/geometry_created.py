from pathlib import Path
from typing import Any, ClassVar, Dict, Optional, Tuple

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.chain_worker import ChainOfResponsibilityWorkerAdapter
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.domain.exception.creation import (
    GeometryDefinitionInvalidError,
    IfcCreationError,
)
from infobim.ifc.domain.model.geometry import GeometryDefinition
from infobim.ifc.domain.port.geometry import GeometryCreateResponsibilityPort
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class GeometryCreatedCapability(TransactionCapability):
    """
    Materialize the current geometry definition through its responsibility chain.

    This state owns no primitive-specific IFC code. It only hands the geometry
    parameters to the chain; each responsibility decides whether it can handle
    them and owns the corresponding IFC creation logic.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometry_created"
        ),
        version="0.1.0",
        name="Geometry Created",
        description="Create the defined geometry through the geometry chain.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "geometry_created"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "geometry": {
                    "type": "object",
                    "required": True,
                    "description": "The GeometryDefinition produced for this run.",
                    "uri": "org.infobim.ifc.geometry",
                },
                "position": {
                    "type": "object",
                    "required": True,
                    "description": "The position this run places the geometry at.",
                    "uri": "org.infobim.ifc.position",
                },
            },
        },
        log_message={
            "info": {"en": "The defined geometry exists in the target IFC model."},
            "debug_entry": {"en": "Resolving the geometry creation chain."},
        },
    )

    GEOMETRY_KEY: ClassVar[str] = "geometry"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"
    RESPONSIBILITIES_KEY: ClassVar[str] = "responsibilities"
    ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")
    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.ifc.plugin.machine.geometric_resolver_chain"
    )
    STATECHART_FILE: ClassVar[str] = "standard_geometric_resolver_chain.yaml"

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.GEOMETRY_CREATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.GEOMETRY_CREATED.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        definition: GeometryDefinition = self._definition(context)
        # The kind travels with the measurements, because the
        # measurements alone do not say which solid this is: a cylinder
        # is measured by a radius as much as a sphere is, and a
        # responsibility answering by parameters alone answers for
        # another primitive's and creates the wrong solid.
        extra_data: Dict[str, Any] = {
            GeometryDefinition.KIND_KEY: definition.kind,
            **dict(definition.parameters),
        }

        worker = ChainOfResponsibilityWorkerAdapter(
            support=GeometryCreateResponsibilityPort,
            context=context,
            logger=None,
            statechart_file_path=self.statechart_path(),
            root_packages=self.ROOT_PACKAGES,
            extra_data=extra_data,
        )
        results: Dict[str, Dict[str, Any]] = worker.work()
        if not results:
            raise IfcCreationError(
                f"No geometry creation responsibility can handle "
                f"'{definition.kind}' with parameters {extra_data}."
            )

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductCreateProcessState.GEOMETRY_CREATED
            ),
            self.RESPONSIBILITIES_KEY: results,
        }

    @classmethod
    def _definition(cls, context: CliContextPort) -> GeometryDefinition:
        if not context.has_parameter(cls.GEOMETRY_KEY):
            raise GeometryDefinitionInvalidError(
                "No geometry definition is present in the command context."
            )

        value: Any = context.get_parameter_value(cls.GEOMETRY_KEY)
        if isinstance(value, GeometryDefinition):
            return value
        if isinstance(value, dict):
            definition: Optional[GeometryDefinition] = GeometryDefinition.from_dict(
                value
            )
            if definition is not None:
                return definition

        raise GeometryDefinitionInvalidError(
            "The geometry definition in the command context is invalid."
        )

    @classmethod
    def statechart_path(cls) -> Path:
        return StatechartLocator.locate(
            cls.STATECHART_PACKAGE,
            cls.STATECHART_FILE,
        )
