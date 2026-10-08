from typing import Any

from ontobdc.cli.domain.response.command import CommandResponse

from infobim.annotation.adapter.csv_repository import AnnotationCsvRepository
from infobim.project.adapter.proxy import ContainerCommandProxy


class EntityRepositoryProxy(ContainerCommandProxy):
    """
    A project command that changes entities: it hands OntoBDC's command the
    CSV repository that keeps the entities of a project, through the context,
    and takes it back when the command ends.
    """

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        context.set_parameter_value("entity_repository", AnnotationCsvRepository())
        try:
            return self._target.run()
        finally:
            context.delete_parameter("entity_repository")
