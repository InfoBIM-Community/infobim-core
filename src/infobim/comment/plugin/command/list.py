from typing import Any, ClassVar, Dict, List, Type

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.comment.adapter.thread import CommentThread
from ontobdc.comment.plugin.command import list as ontobdc_comment_list

from infobim.comment.adapter.proxy import CommentCommandProxy, IfcElementCommentProxy


class CommentListCommand(IfcElementCommentProxy):
    """
    List the comments on an entity of an InfoBIM project.

    The command is OntoBDC's own comment listing, and the entity may be an
    IFC element, as it may for ``infobim comment --guid <id> --create``.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="infobim_comment_list",
        logical_component="comment",
        description="List the comments on an entity of an InfoBIM project.",
        arguments=CommentCommandProxy.arguments_of(ontobdc_comment_list.CommentListCommand),
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_comment_list.CommentListCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the comment listing at the CLI routing stage.
        """
        return CommentListCommand.accepts_as_target(CommentListCommand.TARGET, args)

    def run_on_element(self, thread: CommentThread, guid: str) -> CommandResponse:
        comments: List[Dict[str, Any]] = thread.comments()

        return CommandResponse(
            title="Comments",
            description=f"{len(comments)} comments on the entity {guid}.",
            content={"entity": guid, "comments": comments},
        )
