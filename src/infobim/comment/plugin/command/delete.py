from typing import ClassVar, List, Type

from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.comment.plugin.command import delete as ontobdc_comment_delete

from infobim.comment.adapter.proxy import CommentCommandProxy


class CommentDeleteCommand(CommentCommandProxy):
    """
    Delete a comment of an InfoBIM project.

    The command is OntoBDC's own. The comment is found in the threads of
    every dataset of the project, the reserved one included, where the
    threads of IFC elements are kept.
    """

    METADATA: CliCommandMetadata = CliCommandMetadata(
        id="infobim_comment_delete",
        logical_component="comment",
        description="Delete a comment of an InfoBIM project.",
        arguments=CommentCommandProxy.arguments_of(ontobdc_comment_delete.CommentDeleteCommand),
    )

    # Reached through its module: a class imported by name would be found by the
    # command loader as a command of this package, too.
    TARGET: ClassVar[Type[CliCommandPort]] = ontobdc_comment_delete.CommentDeleteCommand

    @staticmethod
    def accepts(args: List[str]) -> bool:
        """
        Match the comment command at the CLI routing stage.
        """
        return CommentDeleteCommand.accepts_as_target(CommentDeleteCommand.TARGET, args)
