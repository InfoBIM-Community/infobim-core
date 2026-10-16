import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Dict, List

from ontobdc.container.domain.port.entity import EntityRepositoryPort

from infobim.project.domain.model.contract import ProjectContract


class AnnotationCsvRepository(EntityRepositoryPort):
    """
    Keep the annotations of a dataset as a CSV spreadsheet.

    InfoBIM's database of entities is made of spreadsheets: the data source
    of the annotations is ``payload/document/Annotation_Dataset_<timestamp>.csv``
    of the dataset. It is created with the ``global_id`` column only; the
    other columns are added as the annotation facade declares them. A
    dataset that holds several of them is read and written in the newest,
    the one whose timestamp is the latest.
    """

    DOCUMENT_DIRECTORY_NAME: ClassVar[str] = "document"
    FILE_PREFIX: ClassVar[str] = "Annotation_Dataset_"
    FILE_SUFFIX: ClassVar[str] = ".csv"
    TIMESTAMP_FORMAT: ClassVar[str] = "%Y%m%d%H%M%S"
    ENCODING: ClassVar[str] = "utf-8"
    IDENTIFIER_COLUMN: ClassVar[str] = "global_id"

    def data_source_exists(self, dataset_path: Path) -> bool:
        return self._newest(dataset_path) is not None

    def create_data_source(self, dataset_path: Path) -> Path:
        timestamp: str = datetime.now().strftime(self.TIMESTAMP_FORMAT)
        path: Path = self._directory(dataset_path) / (
            f"{self.FILE_PREFIX}{timestamp}{self.FILE_SUFFIX}"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        # "x": a data source that is already there is never overwritten.
        with path.open("x", encoding=self.ENCODING, newline="") as handle:
            csv.writer(handle).writerow([self.IDENTIFIER_COLUMN])

        return path

    def data_source_path(self, dataset_path: Path) -> Path:
        path: Path | None = self._newest(dataset_path)
        if path is None:
            raise FileNotFoundError(
                f"The dataset at {dataset_path} has no annotation data source."
            )

        return path

    def columns(self, dataset_path: Path) -> List[str]:
        return self._read(dataset_path)[0]

    def add_columns(self, dataset_path: Path, columns: List[str]) -> None:
        present, rows = self._read(dataset_path)
        added: List[str] = [column for column in columns if column not in present]
        self._write(dataset_path, present + added, rows)

    def rows(self, dataset_path: Path) -> Dict[str, Dict[str, str]]:
        return {
            row[self.IDENTIFIER_COLUMN]: {
                column: value or "" for column, value in row.items()
            }
            for row in self._read(dataset_path)[1]
            if row.get(self.IDENTIFIER_COLUMN)
        }

    def upsert_rows(self, dataset_path: Path, rows: List[Dict[str, Any]]) -> None:
        columns, existing = self._read(dataset_path)

        unknown: List[str] = sorted(
            {key for row in rows for key in row if key not in columns}
        )
        if unknown:
            raise ValueError(
                f"The data source has no column for {unknown}; add them first."
            )

        positions: Dict[str, int] = {
            row[self.IDENTIFIER_COLUMN]: index for index, row in enumerate(existing)
        }
        row: Dict[str, Any]
        for row in rows:
            written: Dict[str, str] = {
                column: self._text(row.get(column)) for column in columns
            }
            identifier: str = written[self.IDENTIFIER_COLUMN]
            if not identifier:
                raise ValueError("A row of the data source needs a global_id.")
            if identifier in positions:
                existing[positions[identifier]] = written
            else:
                positions[identifier] = len(existing)
                existing.append(written)

        self._write(dataset_path, columns, existing)

    def delete_rows(self, dataset_path: Path, global_ids: List[str]) -> None:
        columns, existing = self._read(dataset_path)
        removed: set[str] = set(global_ids)
        self._write(
            dataset_path,
            columns,
            [row for row in existing if row[self.IDENTIFIER_COLUMN] not in removed],
        )

    def _directory(self, dataset_path: Path) -> Path:
        return (
            dataset_path
            / ProjectContract.PAYLOAD_DIRECTORY_NAME
            / self.DOCUMENT_DIRECTORY_NAME
        )

    def _newest(self, dataset_path: Path) -> Path | None:
        sources: List[Path] = sorted(
            self._directory(dataset_path).glob(
                f"{self.FILE_PREFIX}*{self.FILE_SUFFIX}"
            )
        )
        return sources[-1] if sources else None

    def _read(self, dataset_path: Path) -> tuple[List[str], List[Dict[str, str]]]:
        with self.data_source_path(dataset_path).open(
            encoding=self.ENCODING, newline=""
        ) as handle:
            reader: csv.DictReader = csv.DictReader(handle)
            columns: List[str] = list(reader.fieldnames or [])
            if self.IDENTIFIER_COLUMN not in columns:
                raise ValueError(
                    f"The annotation data source has no {self.IDENTIFIER_COLUMN} column."
                )
            return columns, [dict(row) for row in reader]

    def _write(
        self,
        dataset_path: Path,
        columns: List[str],
        rows: List[Dict[str, str]],
    ) -> None:
        path: Path = self.data_source_path(dataset_path)
        temporary: Path = path.with_name(f"{path.name}.tmp")
        with temporary.open("w", encoding=self.ENCODING, newline="") as handle:
            writer: csv.DictWriter = csv.DictWriter(
                handle, fieldnames=columns, restval=""
            )
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)

    @staticmethod
    def _text(value: Any) -> str:
        return "" if value is None else str(value)
