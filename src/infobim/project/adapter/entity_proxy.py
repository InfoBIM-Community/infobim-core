from pathlib import Path
from typing import Any, Dict, List

from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.container.domain.port.entity import EntityRepositoryPort

from infobim.annotate.adapter.csv_repository import AnnotationCsvRepository
from infobim.project.adapter.proxy import ContainerCommandProxy
from infobim.project.adapter.turtle_repository import TurtleEntityRepository


class ProjectEntityRepository(EntityRepositoryPort):
    """
    The repository of the entities of a project: each dataset is kept the way
    it has its data, as the CSV spreadsheet of annotations or as the Turtle
    files of its entities. The CSV is preferred when a dataset has both.
    """

    def __init__(self) -> None:
        self._csv: EntityRepositoryPort = AnnotationCsvRepository()
        self._turtle: EntityRepositoryPort = TurtleEntityRepository()

    def _of(self, dataset_path: Path) -> EntityRepositoryPort:
        return self._turtle if not self._csv.data_source_exists(dataset_path) and self._turtle.data_source_exists(dataset_path) else self._csv

    def data_source_exists(self, dataset_path: Path) -> bool:
        return self._csv.data_source_exists(dataset_path) or self._turtle.data_source_exists(dataset_path)

    def create_data_source(self, dataset_path: Path) -> Path:
        return self._csv.create_data_source(dataset_path)

    def data_source_path(self, dataset_path: Path) -> Path:
        return self._of(dataset_path).data_source_path(dataset_path)

    def columns(self, dataset_path: Path) -> List[str]:
        return self._of(dataset_path).columns(dataset_path)

    def add_columns(self, dataset_path: Path, columns: List[str]) -> None:
        self._of(dataset_path).add_columns(dataset_path, columns)

    def rows(self, dataset_path: Path) -> Dict[str, Dict[str, str]]:
        return self._of(dataset_path).rows(dataset_path)

    def upsert_rows(self, dataset_path: Path, rows: List[Dict[str, Any]]) -> None:
        self._of(dataset_path).upsert_rows(dataset_path, rows)

    def delete_rows(self, dataset_path: Path, global_ids: List[str]) -> None:
        self._of(dataset_path).delete_rows(dataset_path, global_ids)


class EntityRepositoryProxy(ContainerCommandProxy):
    """
    A project command that changes entities: it hands OntoBDC's command the
    repository that keeps the entities of a project, through the context,
    and takes it back when the command ends.
    """

    def run(self) -> CommandResponse:
        context: Any = self._request.context
        context.set_parameter_value("entity_repository", ProjectEntityRepository())
        try:
            return self._target.run()
        finally:
            context.delete_parameter("entity_repository")
