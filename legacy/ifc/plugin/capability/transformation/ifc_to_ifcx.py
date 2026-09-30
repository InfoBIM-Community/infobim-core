from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Type

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.adapter.capability import Capability, CapabilityExecutor
from ontobdc.shared.adapter.capability import TransactionCapability
from ontobdc.shared.adapter.loader import ResolverLoader
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.adapter.resolver import StrategyParamResolver
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import CapabilityPort
from ontobdc.shared.domain.port.resolver import DynamicParamResolverPort

from infobim.ifc.adapter.composition import CanonicalIfcxModel
from infobim.ifc.adapter.element import IfcElementClassResolver
from infobim.ifc.adapter.etl import IfcConversionState
from infobim.ifc.adapter.loader import IfcWriterCapabilityLoader
from infobim.ifc.adapter.schema import IfcProjectSchemaResolver
from infobim.ifc.adapter.schema_loader import IfcSchemaLoaderResolver
from infobim.ifc.domain.port.composition import (
    CanonicalIfcxModelPort,
    IfcConversionStatePort,
)
from infobim.ifc.domain.port.loader import IfcCapabilityPackageLoaderPort
from infobim.ifc.domain.port.schema import (
    IfcElementClassResolverPort,
    IfcProjectSchemaResolverPort,
    IfcSchemaLoaderPort,
    IfcSchemaLoaderResolverPort,
)


class IfcToIfcxCapability(TransactionCapability):
    """
    Converts one IFC element of a project into the project's IFCX model.

    Nothing here knows how any IFC class is read or how it is written as
    IFCX. The conversion of a class is owned by two capabilities that
    declare which schema and which class they answer for — a Loader
    Capability that returns the element as ifcOWL JSON-LD, and a Writer
    Capability that turns that JSON-LD into an IFCX contribution — and this
    capability resolves them, runs them, and composes what comes back.

    The pipeline is therefore the same for every IFC class, and supporting a
    new one means shipping the two capabilities for it, never editing a
    dispatcher here:

    1. the schema the project declares decides which schema loader answers;
    2. the schema loader resolves the Loader Capability of the element's
       class inside the IFC loader package;
    3. the Writer Capability of the same class is resolved for the current
       target schema inside the IFC writer package;
    4. the contribution the Writer returns is merged into the project's
       canonical IFCX model and the conversion is recorded.

    Both children run through ``CapabilityExecutor``, so a child capability
    keeps the parameter resolution, input checking and logging every other
    capability gets, instead of the reduced contract a direct ``execute``
    call would give it.
    """

    GLOBAL_ID_KEY: ClassVar[str] = "global_id"
    ELEMENT_ID_KEY: ClassVar[str] = "element_id"
    CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
    JSON_LD_KEY: ClassVar[str] = "json_ld"
    IFCX_KEY: ClassVar[str] = "ifcx"

    WRITER_SCHEMA: ClassVar[str] = "IFC5-Alpha"
    RESOLVER_ROOT_PACKAGES: ClassVar[tuple] = ("ontobdc", "infobim")

    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.ifc.plugin.capability.transformation.ifc_to_ifcx",
        version="0.2.0",
        name="IFC to IFCX",
        description=(
            "Convert an IFC element identified by Project GlobalId and "
            "element GlobalId into the project's canonical IFCX model."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "ifc", "ifcx", "transformation"],
        supported_languages=["en", "pt-br"],
        input_schema={
            "type": "object",
            "properties": {
                GLOBAL_ID_KEY: {
                    "type": "string",
                    "required": True,
                    "description": "GlobalId of the Project that owns the IFC element.",
                },
                ELEMENT_ID_KEY: {
                    "type": "string",
                    "required": True,
                    "description": "GlobalId of the IFC element to convert.",
                },
            },
        },
        output_schema={
            "type": "object",
            "properties": {
                "ifc_class": {"type": "string"},
                "schema_uri": {"type": "string"},
                "loader_capability": {"type": "string"},
                "writer_capability": {"type": "string"},
                "model_path": {"type": "string"},
                "state_path": {"type": "string"},
                "nodes": {"type": "array"},
            },
        },
        log_message={
            "info": {
                "en": (
                    "The IFC element was converted to IFCX and merged into "
                    "the project's canonical model."
                ),
            },
            "debug_entry": {
                "en": (
                    "Converting an IFC element into the project's canonical "
                    "IFCX model."
                ),
            },
        },
    )

    def __init__(
        self,
        schema_resolver: Optional[IfcProjectSchemaResolverPort] = None,
        element_class_resolver: Optional[IfcElementClassResolverPort] = None,
        schema_loader_resolver: Optional[IfcSchemaLoaderResolverPort] = None,
        writer_loader: Optional[IfcCapabilityPackageLoaderPort] = None,
        model: Optional[CanonicalIfcxModelPort] = None,
        state: Optional[IfcConversionStatePort] = None,
    ) -> None:
        self._schema_resolver: IfcProjectSchemaResolverPort = (
            schema_resolver or IfcProjectSchemaResolver()
        )
        self._element_class_resolver: IfcElementClassResolverPort = (
            element_class_resolver or IfcElementClassResolver()
        )
        self._schema_loader_resolver: IfcSchemaLoaderResolverPort = (
            schema_loader_resolver or IfcSchemaLoaderResolver()
        )
        self._writer_loader: IfcCapabilityPackageLoaderPort = (
            writer_loader or IfcWriterCapabilityLoader()
        )
        self._model: CanonicalIfcxModelPort = model or CanonicalIfcxModel()
        self._state: IfcConversionStatePort = state or IfcConversionState()

    def label(self, lang: str = "en") -> str:
        return "IFC to IFCX"

    def description(self, lang: str = "en") -> str:
        return (
            "Converts an IFC element identified by Project GlobalId and "
            "element GlobalId into the project's canonical IFCX model."
        )

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        global_id: str = RequiredParameter.of(context, self.GLOBAL_ID_KEY)
        element_id: str = RequiredParameter.of(context, self.ELEMENT_ID_KEY)
        project_path: Path = Path(
            RequiredParameter.of(context, self.CONTAINER_PATH_KEY)
        ).expanduser().resolve()

        schema_uri: str = self._schema_resolver.resolve(project_path)
        ifc_class: str = self._element_class_resolver.resolve(
            project_path,
            schema_uri,
            element_id,
        )

        schema_loader: IfcSchemaLoaderPort = self._schema_loader_resolver.resolve(
            schema_uri
        )
        loader_capability: Type[CapabilityPort] = schema_loader.loader_capability(
            schema_uri,
            ifc_class,
        )
        writer_capability: Type[CapabilityPort] = self._writer_loader.resolve(
            self.WRITER_SCHEMA,
            ifc_class,
        )

        json_ld: Dict[str, Any] = self._load(loader_capability, context, element_id)
        contribution: Dict[str, Any] = self._write(
            writer_capability,
            context,
            json_ld,
            element_id,
        )

        recorded: Optional[Dict[str, Any]] = self._state.read(
            project_path,
            element_id,
        )
        nodes: List[str] = self._model.merge(
            project_path,
            global_id,
            element_id,
            contribution,
            self._superseded_nodes(recorded),
        )
        state_path: Path = self._state.write(
            project_path,
            element_id,
            {
                self.GLOBAL_ID_KEY: global_id,
                self.ELEMENT_ID_KEY: element_id,
                "ifc_class": ifc_class,
                "schema_uri": schema_uri,
                "target_schema": self.WRITER_SCHEMA,
                "loader_capability": loader_capability.METADATA.id,
                "writer_capability": writer_capability.METADATA.id,
                "model_path": str(self._model.path(project_path, global_id)),
                IfcConversionState.NODES_KEY: nodes,
                "converted_at": datetime.now(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z"),
            },
        )

        return {
            self.GLOBAL_ID_KEY: global_id,
            self.ELEMENT_ID_KEY: element_id,
            "ifc_class": ifc_class,
            "schema_uri": schema_uri,
            "loader_capability": loader_capability.METADATA.id,
            "writer_capability": writer_capability.METADATA.id,
            "model_path": str(self._model.path(project_path, global_id)),
            "state_path": str(state_path),
            IfcConversionState.NODES_KEY: nodes,
        }

    def _load(
        self,
        loader_capability: Type[CapabilityPort],
        context: CliContextPort,
        element_id: str,
    ) -> Dict[str, Any]:
        """
        Run the Loader Capability and return the ifcOWL JSON-LD it produced.
        """
        result: Dict[str, Any] = CapabilityExecutor.execute(
            self._instance_of(loader_capability),
            context,
            self._resolver(),
        )
        json_ld: Any = result.get(self.JSON_LD_KEY)
        if not isinstance(json_ld, dict):
            raise ValueError(
                f"The Loader Capability {loader_capability.METADATA.id} must "
                f"return the ifcOWL JSON-LD of {element_id} under "
                f"'{self.JSON_LD_KEY}'."
            )

        return json_ld

    def _write(
        self,
        writer_capability: Type[CapabilityPort],
        context: CliContextPort,
        json_ld: Dict[str, Any],
        element_id: str,
    ) -> Dict[str, Any]:
        """
        Run the Writer Capability over the JSON-LD and return its IFCX.

        The JSON-LD reaches the Writer as a parameter of the shared context,
        and it is this conversion's own value: it is removed once the Writer
        has run, so a capability running later in the same command never
        sees the JSON-LD of an element it knows nothing about.
        """
        context.set_parameter_value(self.JSON_LD_KEY, json_ld)
        try:
            result: Dict[str, Any] = CapabilityExecutor.execute(
                self._instance_of(writer_capability),
                context,
                self._resolver(),
            )
        finally:
            context.delete_parameter(self.JSON_LD_KEY)

        contribution: Any = result.get(self.IFCX_KEY)
        if not isinstance(contribution, dict):
            raise ValueError(
                f"The Writer Capability {writer_capability.METADATA.id} must "
                f"return the IFCX contribution of {element_id} under "
                f"'{self.IFCX_KEY}'."
            )

        return contribution

    @staticmethod
    def _instance_of(capability: Type[CapabilityPort]) -> Capability:
        """
        Instantiate a resolved capability class for execution.
        """
        instance: Any = capability()
        if not isinstance(instance, Capability):
            raise ValueError(
                f"{capability.__name__} is not an executable capability."
            )

        return instance

    @classmethod
    def _resolver(cls) -> DynamicParamResolverPort:
        """
        Build the resolver the child capabilities resolve their inputs with.

        A child declares its inputs by URI like any other capability, and the
        strategies answering for InfoBIM's own URIs are shipped in InfoBIM's
        plugin packages. The resolver the generic run command builds looks
        only at OntoBDC's, so this pipeline composes its own rather than
        changing what that command does for every capability.
        """
        return StrategyParamResolver(
            ResolverLoader(root_packages=cls.RESOLVER_ROOT_PACKAGES)
        )

    @staticmethod
    def _superseded_nodes(recorded: Optional[Dict[str, Any]]) -> List[str]:
        """
        Return the canonical-model nodes the element's last conversion left.
        """
        if not isinstance(recorded, dict):
            return []

        nodes: Any = recorded.get(IfcConversionState.NODES_KEY)
        if not isinstance(nodes, list):
            return []

        return [node for node in nodes if isinstance(node, str)]
