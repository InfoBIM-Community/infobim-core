from typing import Any, ClassVar, Dict, List, Type

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.comment.adapter.thread import CommentThread
from ontobdc.comment.plugin.command import create as ontobdc_comment_create
from ontobdc.shared.adapter.parameter import RequiredParameter

from infobim.comment.adapter.proxy import CommentCommandProxy, IfcElementCommentProxy


class CommentCreateCommand(IfcElementCommentProxy):
    """
    Comment on an entity of an InfoBIM project.

    The command is OntoBDC's own comment creation. What InfoBIM adds is the
    project selector (``--global-id``, or the current directory), the check
    that the container is a project, and the IFC elements: an entity no
    dataset keeps may be one, and its facade says it can be commented on.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="infobim_comment_create",
        logical_component="comment",
        description="Comment on an entity of an InfoBIM project.",
        arguments=CommentCommandProxy.arguments_of(ontobdc_comment_create.CommentCreateCommand),
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_comment_create.CommentCreateCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the comment creation at the CLI routing stage.
        """
        return CommentCreateCommand.accepts_as_target(CommentCreateCommand.TARGET, args)

    def run_on_element(self, thread: CommentThread, guid: str) -> CommandResponse:
        context: Any = self._request.context
        text: str = RequiredParameter.of(context, self.TARGET.TEXT_KEY).strip()
        if not text:
            raise ValueError("The comment has no text.")

        comment: Dict[str, Any] = thread.add(
            text,
            author=RequiredParameter.optional(context, self.TARGET.AUTHOR_KEY) or "",
            reply_of=RequiredParameter.optional(context, self.TARGET.REPLY_KEY),
        )

        return CommandResponse(
            title="Comment Created",
            description=f"Commented on the entity {guid}.",
            content={"entity": guid, **comment},
        )
