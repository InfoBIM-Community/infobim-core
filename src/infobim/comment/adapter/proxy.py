from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.comment.adapter.thread import CommentThread
from ontobdc.container.domain.model.entity_facade import EntityFacade
from ontobdc.shared.adapter.parameter import RequiredParameter

from infobim.ifc.adapter.element import IfcElementEntity
from infobim.project.adapter.contract import ProjectGuard
from infobim.project.adapter.proxy import ContainerCommandProxy


class CommentCommandProxy(ContainerCommandProxy):
    """
    Runs an OntoBDC comment command under the name InfoBIM gives it.

    Only the project selector changes: ``--global-id`` for the ``--container``
    the command reads. What a comment is, and where its thread is kept, is
    OntoBDC's.
    """

    COMPONENT: ClassVar[str] = "comment"
    TARGET_COMPONENT: ClassVar[str] = "comment"

    @classmethod
    def arguments_of(cls, target: type) -> List[Dict[str, Any]]:
        """The arguments of the target command, with the project selector in the place of its container's."""
        return [
            {
                "accepts": ["--global-id"],
                "valued": True,
                "parameter": "global_id",
                "description": (
                    "Select the project by the GlobalId carried by its "
                    "IfcProject or by the container storage identifier. "
                    "When omitted, resolve the project from the current "
                    "working directory."
                ),
                "type": "str",
            },
            *[argument for argument in target.METADATA.arguments if argument["accepts"] != ["--container"]],  # type: ignore[attr-defined]
        ]


class IfcElementCommentProxy(CommentCommandProxy):
    """
    A comment command that names the entity: the thread of an IFC element, which no dataset keeps
    and so no OntoBDC command finds, is kept in the reserved dataset of the project.
    """

    GUID_KEY: ClassVar[str] = "entity_guid"

    def run(self) -> CommandResponse:
        """
        Run the command for the entity a dataset keeps, or else for the IFC element with the GlobalId.
        """
        try:
            return super().run()
        except LookupError as not_kept:
            context: Any = self._request.context
            project_path: Path = Path(
                RequiredParameter.of(context, self.TARGET.CONTAINER_KEY)
            ).expanduser().resolve()
            guid: str = RequiredParameter.of(context, self.GUID_KEY)
            if IfcElementEntity.find(project_path, guid) is None:
                raise IfcElementEntity.absent(project_path, guid, not_kept)

            return self.run_on_element(CommentThread(IfcElementEntity.dataset_path(project_path), guid), guid)

    def run_on_element(self, thread: CommentThread, guid: str) -> CommandResponse:
        """What the command does on the thread of an IFC element."""
        raise NotImplementedError
