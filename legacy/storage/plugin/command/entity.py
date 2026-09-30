from typing import Any, ClassVar, List

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import ExceptionCommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException


class StorageEntityCommand(CliCommandPort):
    """
    Command for looking up an entity of the storage by the name it is known by.

    Routing and argument binding are in place: the entity is declared here
    and bound by the parameter stage before ``check`` runs. The entity
    catalog has not been restored yet, so ``run`` reports that instead of
    answering with an entity.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="storage_entity",
        logical_component="storage",
        description="Look up an entity of the storage by name.",
        arguments=[
            {
                "accepts": [
                    "--entity",
                ],
                "valued": True,
                "parameter": "entity",
                "description": (
                    "The entity to look up, such as PurchaseOrder."
                ),
                "usage": "infobim storage --entity <entity>",
            },
        ],
    )

    ENTITY_FLAG: ClassVar[str] = "--entity"

    # Kept short on purpose: the widget adapter renders this value inside a
    # fenced block, which the terminal surface prints verbatim, without
    # wrapping it to the frame width.
    _PENDING_ERROR: ClassVar[str] = "Entity catalog not restored."
    _PENDING_REASON: ClassVar[str] = (
        "Looking up an entity is not available in this build: the entity "
        "catalog has not been restored yet."
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the storage entity command at the CLI routing stage.
        """
        return (
            len(args) == 3
            and args[0] == "storage"
            and args[1] == StorageEntityCommand.ENTITY_FLAG
            and bool(str(args[2]).strip())
        )

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request

    def check(self) -> bool:
        """
        Check if the command is valid.
        Returns True if the command is valid, False otherwise.
        """
        command_args: List[str] = self._request.command_args

        return (
            len(command_args) == 2
            and command_args[0] == self.ENTITY_FLAG
            and bool(command_args[1].strip())
        )

    def run(self) -> ExceptionCommandResponse:
        """
        Report that the entity catalog is not available yet.
        """
        entity: Any = self._request.context.get_parameter_value("entity")
        if not isinstance(entity, str) or not entity.strip():
            raise CliCommandArgumentException(
                "Required parameter is missing: entity"
            )

        return ExceptionCommandResponse(
            title="Entity Lookup Not Available",
            description=self._PENDING_REASON,
            content={
                "error": self._PENDING_ERROR,
                "entity": entity.strip(),
            },
        )
