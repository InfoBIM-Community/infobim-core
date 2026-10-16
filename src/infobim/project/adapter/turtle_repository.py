from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF

from ontobdc.container.adapter.entity_listing import ContainerEntities
from ontobdc.container.domain.model.entity_facade import EntityFacade, EntityFacadeField
from ontobdc.container.domain.port.entity import EntityRepositoryPort

from infobim.project.domain.model.contract import ProjectContract


class TurtleEntityRepository(EntityRepositoryPort):
    """
    Keep the entities of a dataset as RDF in Turtle files.

    The entities of the project dataset (the IfcProject) are the subjects of
    the Turtle files under ``payload/triple`` of the dataset. A row is read
    through the facade of the entity the dataset holds: each field takes the
    value of the property its ``mapsToResource`` names, and ``global_id`` is
    the field that identifies the entity. Writing a row changes only the
    properties of the fields whose text differs; everything else the file
    says is kept as it was.
    """

    TRIPLE_DIRECTORY_NAME: ClassVar[str] = "triple"
    SUFFIX: ClassVar[str] = ".ttl"
    ENCODING: ClassVar[str] = "utf-8"
    IDENTIFIER_COLUMN: ClassVar[str] = "global_id"
    MULTIPLE_VALUES_SEPARATOR: ClassVar[str] = "|"

    def data_source_exists(self, dataset_path: Path) -> bool:
        return bool(self._files(dataset_path)) and self._facade(dataset_path) is not None

    def create_data_source(self, dataset_path: Path) -> Path:
        raise NotImplementedError(
            "The Turtle files of a dataset are made by the process that models "
            "its entities, not by the repository."
        )

    def data_source_path(self, dataset_path: Path) -> Path:
        files: List[Path] = self._files(dataset_path)
        if not files:
            raise FileNotFoundError(f"The dataset at {dataset_path} has no Turtle data source.")

        return files[0]

    def columns(self, dataset_path: Path) -> List[str]:
        return [field.identifier for field in self._require_facade(dataset_path).fields]

    def add_columns(self, dataset_path: Path, columns: List[str]) -> None:
        missing: List[str] = [column for column in columns if column not in self.columns(dataset_path)]
        if missing:
            raise ValueError(f"The facade of the entity declares no field {missing}.")

    def rows(self, dataset_path: Path) -> Dict[str, Dict[str, str]]:
        facade: EntityFacade = self._require_facade(dataset_path)
        rows: Dict[str, Dict[str, str]] = {}
        file: Path
        for file in self._files(dataset_path):
            graph: Graph = self._parse(file)
            subject: Any
            for subject in graph.subjects(RDF.type, URIRef(facade.entity_iri)):
                row: Dict[str, str] = self._row(graph, subject, facade)
                if row.get(self.IDENTIFIER_COLUMN):
                    rows[row[self.IDENTIFIER_COLUMN]] = row

        return rows

    def upsert_rows(self, dataset_path: Path, rows: List[Dict[str, Any]]) -> None:
        facade: EntityFacade = self._require_facade(dataset_path)
        fields: Dict[str, EntityFacadeField] = {field.identifier: field for field in facade.fields}
        row: Dict[str, Any]
        for row in rows:
            identifier: str = "" if row.get(self.IDENTIFIER_COLUMN) is None else str(row[self.IDENTIFIER_COLUMN])
            unknown: List[str] = sorted(key for key in row if key not in fields)
            if unknown:
                raise ValueError(f"The facade of the entity declares no field {unknown}.")

            located: Optional[Tuple[Path, Graph, Any]] = self._locate(dataset_path, facade, identifier)
            if located is None:
                raise LookupError(
                    f"The Turtle data source has no entity {identifier}; the repository changes entities, it does not create them."
                )

            file, graph, subject = located
            current: Dict[str, str] = self._row(graph, subject, facade)
            changed: bool = False
            name: str
            for name, value in row.items():
                text: str = "" if value is None else str(value)
                if name == self.IDENTIFIER_COLUMN or text == current.get(name, ""):
                    continue

                self._set(graph, subject, URIRef(fields[name].maps_to_resource), text)
                changed = True

            if changed:
                self._write(file, graph)

    def delete_rows(self, dataset_path: Path, global_ids: List[str]) -> None:
        raise ValueError("The entities kept in the Turtle files of a dataset cannot be removed.")

    def _files(self, dataset_path: Path) -> List[Path]:
        directory: Path = dataset_path / ProjectContract.PAYLOAD_DIRECTORY_NAME / self.TRIPLE_DIRECTORY_NAME
        return sorted(directory.glob(f"*{self.SUFFIX}"))

    @staticmethod
    def _facade(dataset_path: Path) -> Optional[EntityFacade]:
        return ContainerEntities.facade_of(dataset_path)

    def _require_facade(self, dataset_path: Path) -> EntityFacade:
        facade: Optional[EntityFacade] = self._facade(dataset_path)
        if facade is None:
            raise ValueError(f"The dataset at {dataset_path} has no facade, so its fields are not known.")

        return facade

    def _parse(self, file: Path) -> Graph:
        return Graph().parse(str(file), format="turtle")

    def _row(self, graph: Graph, subject: Any, facade: EntityFacade) -> Dict[str, str]:
        return {
            field.identifier: self.MULTIPLE_VALUES_SEPARATOR.join(
                sorted(str(value) for value in graph.objects(subject, URIRef(field.maps_to_resource)))
            )
            for field in facade.fields
        }

    def _locate(self, dataset_path: Path, facade: EntityFacade, identifier: str) -> Optional[Tuple[Path, Graph, Any]]:
        file: Path
        for file in self._files(dataset_path):
            graph: Graph = self._parse(file)
            subject: Any
            for subject in graph.subjects(RDF.type, URIRef(facade.entity_iri)):
                if self._row(graph, subject, facade).get(self.IDENTIFIER_COLUMN) == identifier:
                    return file, graph, subject

        return None

    @staticmethod
    def _set(graph: Graph, subject: Any, predicate: URIRef, text: str) -> None:
        """Replace what the entity says through the property; an empty text says nothing."""
        previous: List[Any] = list(graph.objects(subject, predicate))
        value: Any
        for value in previous:
            graph.remove((subject, predicate, value))
        if text == "":
            return

        template: Any = next((value for value in previous if isinstance(value, Literal)), None)
        graph.add((
            subject,
            predicate,
            Literal(text, lang=template.language, datatype=template.datatype) if template is not None and (template.language or template.datatype) else Literal(text),
        ))

    def _write(self, file: Path, graph: Graph) -> None:
        temporary: Path = file.with_name(f"{file.name}.tmp")
        temporary.write_bytes(graph.serialize(format="turtle", encoding=self.ENCODING))
        temporary.replace(file)
