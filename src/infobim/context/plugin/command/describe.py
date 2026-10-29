from typing import Any, ClassVar, Dict, List, Optional

from brasidatacenter.tool.adapter.class_definition import class_definition
from brasidatacenter.tool.adapter.entity_info import entity_info
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse

from infobim.context.plugin.capability.transformation.entity_uri_resolved import EntityUriResolvedCapability


class ContextEntityDescribeCommand(CliCommandPort):
    """
    Say what the ontologies know about a modelling term: ``infobim context --entity <term> --describe``.

    The term is resolved to the IRI of an entity (an IFC class name is a class of the IFC4 ontology). When BrasidataCenter
    publishes a facade of the entity, that is the answer (``kind`` is ``facade``); when it does not, and the entity is a
    class of the IFC4 ontology, the answer is the definition of the class (``kind`` is ``definition``): its place in the
    hierarchy, its attributes and its types. Any other term is a ``LookupError`` that says why.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="context_entity_describe",
        logical_component="context",
        description="Describe a modelling term: the facade published for it, or else the definition of its IFC class.",
        arguments=[
            {
                "accepts": ["--entity"],
                "valued": True,
                "parameter": "entity_id",
                "description": "Name or IRI of the entity to describe.",
                "type": "str",
            },
            {
                "accepts": ["--describe"],
                "description": "Describe the entity by its facade, or else by the definition of its IFC class.",
            },
        ],
    )

    COMPONENT: ClassVar[str] = "context"
    ENTITY_FLAG: ClassVar[str] = "--entity"
    DESCRIBE_FLAG: ClassVar[str] = "--describe"
    ENTITY_CONTEXT_KEY: ClassVar[str] = "entity_id"

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != ContextEntityDescribeCommand.COMPONENT:
            return False
        return ContextEntityDescribeCommand._extract_entity(args[1:]) is not None

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        entity: Optional[str] = self._extract_entity(self._request.command_args)
        if entity is None:
            return False
        self._request.context.set_parameter_value(self.ENTITY_CONTEXT_KEY, entity)
        return True

    @staticmethod
    def _extract_entity(scoped_args: List[str]) -> Optional[str]:
        """The term of ``--entity <term> --describe``, in either order; none when the arguments are anything else."""
        remaining: List[str] = list(scoped_args)
        if ContextEntityDescribeCommand.DESCRIBE_FLAG not in remaining:
            return None
        remaining.remove(ContextEntityDescribeCommand.DESCRIBE_FLAG)
        if (
            len(remaining) == 2
            and remaining[0] == ContextEntityDescribeCommand.ENTITY_FLAG
            and remaining[1].strip()
            and not remaining[1].startswith("--")
        ):
            return remaining[1].strip()
        return None

    def run(self) -> CommandResponse:
        term: str = str(self._request.context.get_parameter_value(self.ENTITY_CONTEXT_KEY))
        uri: Optional[str] = EntityUriResolvedCapability.resolve(term)
        if uri is None:
            raise LookupError(f"No entity is named {term!r}.")

        facade: Optional[Dict[str, Any]] = entity_info(uri)
        if facade is not None:
            return CommandResponse(
                title="Entity Described",
                description=f"Facade of the entity <{term}>.",
                content={"kind": "facade", "facade": facade},
            )
        definition: Optional[Dict[str, Any]] = class_definition(uri)
        if definition is not None:
            return CommandResponse(
                title="Entity Described",
                description=f"Definition of the class <{term}> in the IFC4 ontology.",
                content={"kind": "definition", "definition": definition},
            )

        raise LookupError(f"No ontology publishes a facade or a definition of the entity <{uri}>.")
