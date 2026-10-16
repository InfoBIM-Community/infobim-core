import re
from typing import Any, ClassVar, Dict, Optional
from urllib.parse import urlsplit

from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.context.plugin.capability.transformation import entity_uri_resolved as _ontobdc_entity_uri_resolved
from ontobdc.shared.adapter.capability import TransformationCapability
from ontobdc.shared.adapter.parameter import RequiredParameter
from ontobdc.shared.domain.model.capability import CapabilityMetadata


class EntityUriResolvedCapability(TransformationCapability):
    """
    Resolve an entity name to its URI.

    An explicit URI is kept. A name that, in Pascal Case, starts with ``Ifc``
    is an IFC class: its URI is the class name in the IFC4 ifcOWL namespace, with
    the letter after ``Ifc`` in upper case.
    Any other name is left to the OntoBDC resolution.
    """

    INPUT_KEY: ClassVar[str] = "entity_id"
    OUTPUT_KEY: ClassVar[str] = "entity_uri"
    SOURCE_KEY: ClassVar[str] = "entity_uri_source"
    IFC4_OWL_NAMESPACE: ClassVar[str] = "https://standards.buildingsmart.org/IFC/DEV/IFC4/FINAL/OWL#"
    IFC_PREFIX: ClassVar[str] = "Ifc"
    METADATA: CapabilityMetadata = CapabilityMetadata(
        id="org.infobim.context.plugin.capability.transformation.target.entity_uri_resolved",
        version="1.0.0",
        name="Entity URI Resolved",
        description="Resolve an IFC class name to its IFC4 ifcOWL URI, preserving explicit URIs.",
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["context", "entity", "inspection", "ifc"],
        input_schema={"properties": {INPUT_KEY: {"type": ["string", "null"], "required": False}}},
        output_schema={"properties": {OUTPUT_KEY: {"type": ["string", "null"]}}},
    )

    def label(self, lang: str = "en") -> str:
        return self.METADATA.name

    def description(self, lang: str = "en") -> str:
        return self.METADATA.description

    @staticmethod
    def pascal_case(name: str) -> str:
        """``ifc_project``, ``ifc-project``, ``ifc project`` and ``ifcProject`` are all ``IfcProject``."""
        parts = [part for part in re.split(r"[^0-9A-Za-z]+", name.strip()) if part]
        return "".join(part[0].upper() + part[1:] for part in parts)

    @classmethod
    def resolve(cls, entity: Optional[str]) -> Optional[str]:
        if entity is None:
            return None  # No selector: the next state lists all entity facades.
        if urlsplit(entity).scheme and not any(char.isspace() for char in entity):
            return entity
        class_name = cls.pascal_case(entity)
        if class_name.startswith(cls.IFC_PREFIX) and len(class_name) > len(cls.IFC_PREFIX):
            # The letter after Ifc starts the next word: ``ifcproject`` is ``IfcProject``.
            rest = class_name[len(cls.IFC_PREFIX):]
            return cls.IFC4_OWL_NAMESPACE + cls.IFC_PREFIX + rest[0].upper() + rest[1:]
        return _ontobdc_entity_uri_resolved.EntityUriResolvedCapability.resolve(entity)

    def is_satisfied(self, context: CliContextPort) -> bool:
        entity = RequiredParameter.optional(context, self.INPUT_KEY)
        if context.get_parameter_value(self.SOURCE_KEY) != (entity or ""):
            return False
        try:
            return context.get_parameter_value(self.OUTPUT_KEY) == self.resolve(entity)
        except LookupError:
            return False

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        entity = RequiredParameter.optional(context, self.INPUT_KEY)
        uri = self.resolve(entity)
        context.set_parameter_value(self.OUTPUT_KEY, uri)
        context.set_parameter_value(self.SOURCE_KEY, entity or "")
        return {self.OUTPUT_KEY: uri}
