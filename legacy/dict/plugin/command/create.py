from typing import Any, ClassVar, List, Optional, Tuple
from pathlib import Path

from ontobdc.cli.adapter.logger import NullLogRepository
from ontobdc.cli.domain.model.logger import LogStrategyConfig
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.port.logger import LoggerAwarePort, LogRepositoryPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.container.plugin.check.is_container_manifest_synced.hotfix import (
    main as hotfix_container_manifest_synced,
)

from infobim.project.adapter.contract import ProjectGuard
from infobim.dict.plugin.machine.dictionary_entity_create.state import (
    DictionaryEntityContextKeys,
)
from infobim.dict.plugin.machine.dictionary_entity_create.machine import (
    DictionaryEntityCreateStateTransitionHandler,
)


class DictCreateCommand(CliCommandPort, LoggerAwarePort):
    """
    Defines one element of the project from a dictionary entry.

    This is the sibling of ``infobim ifc --create``, and the difference is
    what decides what the element is. There, the caller states the class
    and the geometry, and the machine resolves both. Here neither is
    resolved: the dictionary the URI names is what says what the element
    is — the IFC class, the predefined type that class is restricted to,
    the domain classes it belongs to — and this command's job is to go
    there, bring the entry back and read it.

    ``--uri`` takes the entry named in full, as a URL or a path, or the
    prefix it is already called by everywhere else in this stack. Which
    of the two arrived is settled before this command is checked, by the
    strategy that owns the flag.

    ``--global-id`` is this executable's Project selector and means here
    exactly what it means everywhere else: the Project whose IfcProject
    carries that identity, resolved by the parameter strategy that owns
    the flag, and the Project of the current directory when it is left
    out. The element being defined is identified by the machine, from the
    Project and the title, by the same rule the IFC creation flow derives
    a product's identity by — so an element defined here and the product
    assembled there under one title are one element.

    What the entry says is then built: the shape it describes becomes the
    element's geometry, and the class and predefined type it states become
    the element the project's model carries, placed where this run put it.
    From the shape onwards those are the IFC creation flow's own states,
    reached through its own capabilities — by then an element defined from
    a dictionary and one created by a command are the same kind of thing,
    and the only difference worth keeping is who said what it is.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="dict_create",
        logical_component="dict",
        description=(
            "Define an element of the project from a dictionary entry."
        ),
        arguments=[
            {
                "accepts": ["--create"],
                "valued": True,
                "parameter": "title",
                "description": "Title of the element the entry defines.",
                "usage": (
                    "infobim dict --create <title> --uri <dictionary entry> "
                    "[--global-id <GlobalId>] [--x <x>] [--y <y>] [--z <z>] "
                    "[--ifc-model-path <path>]"
                ),
            },
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Define in the Project whose IfcProject carries the given "
                    "GlobalId; the Project of the current directory when it is "
                    "not given."
                ),
            },
            {
                "accepts": ["--uri"],
                "valued": True,
                "parameter": "dictionary_uri",
                "description": (
                    "Dictionary entry the element's definitions are read "
                    "from: a declared ontology prefix, or the entry named in "
                    "full as a URL or a path."
                ),
            },
            {
                "accepts": ["--x"],
                "valued": True,
                "parameter": "x",
                "description": "Placement X coordinate; origin when not given.",
            },
            {
                "accepts": ["--y"],
                "valued": True,
                "parameter": "y",
                "description": "Placement Y coordinate; origin when not given.",
            },
            {
                "accepts": ["--z"],
                "valued": True,
                "parameter": "z",
                "description": "Placement Z coordinate; origin when not given.",
            },
            {
                "accepts": ["--ifc-model-path"],
                "valued": True,
                "parameter": "ifc_model_path",
                "description": (
                    "IFC model the element belongs to; resolved from the "
                    "project when it is not given."
                ),
            },
        ],
    )

    COMPONENT: ClassVar[str] = "dict"
    FLAG: ClassVar[str] = "--create"
    GLOBAL_ID_FLAG: ClassVar[str] = "--global-id"
    URI_FLAG: ClassVar[str] = "--uri"
    X_FLAG: ClassVar[str] = "--x"
    Y_FLAG: ClassVar[str] = "--y"
    Z_FLAG: ClassVar[str] = "--z"
    IFC_MODEL_PATH_FLAG: ClassVar[str] = "--ifc-model-path"
    FLAGS: ClassVar[List[str]] = [
        FLAG,
        GLOBAL_ID_FLAG,
        URI_FLAG,
        X_FLAG,
        Y_FLAG,
        Z_FLAG,
        IFC_MODEL_PATH_FLAG,
    ]

    OPTIONAL_FLAGS: ClassVar[Tuple[str, ...]] = (
        GLOBAL_ID_FLAG,
        X_FLAG,
        Y_FLAG,
        Z_FLAG,
        IFC_MODEL_PATH_FLAG,
    )

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the dictionary definition command at the CLI routing stage.
        """
        if not args or args[0] != DictCreateCommand.COMPONENT:
            return False

        return DictCreateCommand._names_a_definition(args[1:])

    def __init__(self, request: CliCommandRequest) -> None:
        self._request: CliCommandRequest = request
        self._logger: LogRepositoryPort = NullLogRepository()
        self._log_strategy: Any = None

    @property
    def log_strategy(self) -> Any:
        return self._log_strategy

    def set_log_strategy(self, log_strategy: LogStrategyConfig) -> None:
        self._log_strategy = log_strategy
        self._logger = log_strategy.log_repository

    def check(self) -> bool:
        """
        Check that the arguments name a definition, inside a Project.

        What this binds is the title and nothing else. Every other value
        this command takes is already owned by something that ran before
        it: the flags a command declares are copied into the context by
        the parameter pipeline, and the dictionary, the target model and
        the Project each then have a strategy that resolves what was
        copied into what it actually means. Writing any of them again
        here would put the raw token back over the resolution — which is
        how a prefix would arrive at the machine unexpanded, and a model
        resolved for this project would be replaced by whatever relative
        path was typed.

        The coordinates are left as they were written for the same kind
        of reason: what a position is, and what an unstated axis means,
        belongs to the state that defines it.
        """
        if not self._names_a_definition(self._request.command_args):
            return False

        container_value: Any = self._request.context.get_parameter_value(
            DictionaryEntityContextKeys.CONTAINER_PATH_KEY
        )
        if not isinstance(container_value, str) or not container_value.strip():
            raise CliCommandArgumentException(
                "No InfoBIM Project was resolved. Run this command inside one."
            )

        container_path: Path = Path(container_value).expanduser().resolve()
        ProjectGuard.guard(container_path, self._request.context.root_path)

        return True

    def run(self) -> CommandResponse:
        """
        Drive the element through the dictionary definition state machine.

        The container states what it holds, and the machine reads that
        statement rather than the disk, so the statement is brought up to
        date first — the same precondition the IFC creation command
        establishes before its own machine runs.
        """
        container_path: Path = Path(
            str(
                self._request.context.get_parameter_value(
                    DictionaryEntityContextKeys.CONTAINER_PATH_KEY
                )
            )
        ).expanduser().resolve()
        root_path: str = self._request.context.root_path
        if hotfix_container_manifest_synced(
            container_path=str(container_path),
            root_path=str(root_path),
        ) != 0:
            raise CliCommandArgumentException(
                f"The RO-Crate of the project at {container_path} could not "
                f"be brought up to date, so what the project holds is not "
                f"stated."
            )

        handler: DictionaryEntityCreateStateTransitionHandler = (
            DictionaryEntityCreateStateTransitionHandler(
                context=self._request.context,
                logger=self._logger,
            )
        )

        return handler.execute()

    @staticmethod
    def _names_a_definition(scoped_args: List[str]) -> bool:
        """
        Report whether these arguments name a dictionary definition.

        The title and the dictionary are what this command is, and both
        have to carry a value. Every flag is taken out of the arguments
        as it is read but none of the values is kept: what each one means
        is settled by the parameter pipeline before this command is
        checked, and reading them a second time here would be a second
        opinion about the same tokens. Which flag a user writes first is
        not part of the command's meaning, so they are read in any order,
        and an argument left over means the args name something else —
        this command never guesses what.
        """
        remaining: List[str] = list(scoped_args)
        title: Optional[str] = DictCreateCommand._extract(
            remaining,
            DictCreateCommand.FLAG,
        )
        uri: Optional[str] = DictCreateCommand._extract(
            remaining,
            DictCreateCommand.URI_FLAG,
        )
        if title is None or uri is None:
            return False

        optional_flag: str
        for optional_flag in DictCreateCommand.OPTIONAL_FLAGS:
            DictCreateCommand._extract(remaining, optional_flag)

        return not remaining

    @staticmethod
    def _extract(remaining: List[str], flag: str) -> Optional[str]:
        """
        Remove and return the value the flag carries, or None when it
        carries none.

        A value is what the user wrote for that flag, not whatever token
        happens to sit after it: another flag of this command found there
        means this one was left without a value.
        """
        if flag not in remaining:
            return None

        index: int = remaining.index(flag)
        if index + 1 >= len(remaining):
            return None

        value: str = remaining[index + 1]
        if not value.strip() or value in DictCreateCommand.FLAGS:
            return None

        del remaining[index:index + 2]

        return value.strip()
