from typing import Any, ClassVar, Dict, Optional, Tuple
from pathlib import Path

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.chain_worker import ChainOfResponsibilityWorkerAdapter
from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.domain.model.capability import CapabilityMetadata

from infobim.ifc.adapter.product import IfcProductAssembler
from infobim.ifc.domain.port.product import (
    IfcProductAssemblerPort,
    IfcProductCreateResponsibilityPort,
)
from infobim.ifc.domain.exception.creation import IfcCreationError
from infobim.ifc.plugin.machine.geometric_product_create.state import (
    GeometricProductCreateProcessState,
)


class GeometricProductCreatedCapability(TransactionCapability):
    """
    Creates the product the run names, carrying the geometry assembled for it.

    A class this run actually named is a decision about what the product
    is, and what a class carries is that class's own business, so the
    creation is delegated: the chain asks which capability can handle the
    named class, and the one that answers creates the element and fills
    what its class declares. A class nobody named is not a decision, and
    the product is created as the contract's default instead — the
    generic proxy, which says nothing about the element beyond it being
    one.

    The element is written into the project's state, beside the geometry
    it carries. Bringing it into the model the project federates is the
    state after this one.
    """

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id=(
            "org.infobim.ifc.plugin.capability.transformation.target."
            "geometric_product_created"
        ),
        version="0.1.0",
        name="Geometric Product Created",
        description="Create the IFC element that carries the created geometry.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "geometric-product", "geometric_product_created"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                "container_path": {
                    "type": "string",
                    "required": True,
                    "description": "The InfoBIM project the product belongs to.",
                },
                "title": {
                    "type": "string",
                    "required": True,
                    "description": "The title the product carries as its name.",
                },
            },
        },
        log_message={
            "info": {
                "en": "The IFC product carrying the created geometry exists.",
            },
            "debug_entry": {
                "en": "Creating the IFC product of the assembled geometry.",
            },
        },
    )

    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    TITLE_KEY: ClassVar[str] = "title"
    IFC_CLASS_KEY: ClassVar[str] = "ifc_class"
    GEOMETRIC_PRODUCT_KEY: ClassVar[str] = "geometric_product"
    RESULTING_STATE_KEY: ClassVar[str] = "resulting_state"

    IFC_CLASS_FLAG: ClassVar[str] = "--ifc-class"
    DEFAULT_IFC_CLASS: ClassVar[str] = "IfcBuildingElementProxy"

    ROOT_PACKAGES: ClassVar[Tuple[str, ...]] = ("infobim", "ontobdc")
    STATECHART_PACKAGE: ClassVar[str] = (
        "infobim.ifc.plugin.machine.ifc_product_chain"
    )
    STATECHART_FILE: ClassVar[str] = "standard_ifc_product_chain.yaml"

    def __init__(self, assembler: Optional[IfcProductAssemblerPort] = None) -> None:
        self._assembler: IfcProductAssemblerPort = assembler or IfcProductAssembler()

    def label(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_CREATED.label(lang)

    def description(self, lang: str = "en") -> str:
        return GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_CREATED.description(
            lang
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        ifc_class: Optional[str] = self._named_class(context)
        if ifc_class is None:
            return self._as_default(context)

        return self._through_chain(context, ifc_class)

    @classmethod
    def statechart_path(cls) -> Path:
        """
        Return the chain that resolves which capability creates a class.
        """
        return StatechartLocator.locate(
            cls.STATECHART_PACKAGE,
            cls.STATECHART_FILE,
        )

    @classmethod
    def _named_class(cls, context: CliContextPort) -> Optional[str]:
        """
        Return the IFC class this invocation named, or None when it named none.

        Only a class this run stated counts. The class parameter is bound
        on every run, because its strategy answers the absence of a
        choice with the default, and a default is not a caller saying
        which class the product is — it is a caller saying nothing.
        """
        if cls.IFC_CLASS_FLAG not in context.raw_args:
            return None

        value: Any = context.get_parameter_value(cls.IFC_CLASS_KEY)
        if not isinstance(value, str) or not value.strip():
            return None

        return value.strip()

    def _as_default(self, context: CliContextPort) -> Dict[str, Any]:
        """
        Create the product as the class a run that named none asks for.
        """
        global_id: str = self._assembler.assemble(
            self._container_path(context),
            self._title(context),
            self.DEFAULT_IFC_CLASS,
            {},
        )

        return self._bound(context, global_id, self.DEFAULT_IFC_CLASS)

    def _through_chain(
        self,
        context: CliContextPort,
        ifc_class: str,
    ) -> Dict[str, Any]:
        """
        Let the capability that answers for the named class create it.
        """
        worker: ChainOfResponsibilityWorkerAdapter = ChainOfResponsibilityWorkerAdapter(
            support=IfcProductCreateResponsibilityPort,
            context=context,
            logger=None,
            statechart_file_path=self.statechart_path(),
            root_packages=self.ROOT_PACKAGES,
            extra_data={self.IFC_CLASS_KEY: ifc_class},
        )
        results: Dict[str, Dict[str, Any]] = worker.work()
        if not results:
            raise IfcCreationError(
                f"No creation capability answers for the IFC class "
                f"'{ifc_class}', so the product it names cannot be created."
            )

        global_id: Any = context.get_parameter_value(self.GEOMETRIC_PRODUCT_KEY)
        if not isinstance(global_id, str) or not global_id.strip():
            raise IfcCreationError(
                f"The capability that created the product as '{ifc_class}' "
                f"left no identity for it."
            )

        return self._bound(context, global_id.strip(), ifc_class)

    def _bound(
        self,
        context: CliContextPort,
        global_id: str,
        ifc_class: str,
    ) -> Dict[str, Any]:
        """
        Bind the product this state created and report it.
        """
        context.set_parameter_value(self.GEOMETRIC_PRODUCT_KEY, global_id)

        return {
            self.RESULTING_STATE_KEY: (
                GeometricProductCreateProcessState.GEOMETRIC_PRODUCT_CREATED
            ),
            self.GEOMETRIC_PRODUCT_KEY: global_id,
            self.IFC_CLASS_KEY: ifc_class,
        }

    @classmethod
    def _container_path(cls, context: CliContextPort) -> Path:
        value: Any = context.get_parameter_value(cls.CONTAINER_PATH_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The InfoBIM project is missing from the command context, so "
                "the product has nowhere to be created."
            )

        return Path(value).expanduser().resolve()

    @classmethod
    def _title(cls, context: CliContextPort) -> str:
        value: Any = context.get_parameter_value(cls.TITLE_KEY)
        if not isinstance(value, str) or not value.strip():
            raise IfcCreationError(
                "The product title is missing from the command context, so "
                "the product cannot be named."
            )

        return value.strip()
