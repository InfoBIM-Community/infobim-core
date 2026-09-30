"""Shared file-layout contract for cached drawing transformation payloads."""

from typing import ClassVar, Tuple
import hashlib
from pathlib import Path

from infobim.project.domain.model.contract import ProjectContract


class TransformationPayloadPath:
    """Resolve where a transformation's cached output belongs on disk.

    Each output is addressed by the SHA-256 of its source file's bytes, so
    converting the same content again reuses the same identifier and the
    same path instead of writing a fresh one: the digest itself is the
    identifier, not a UUID derived from it, so the cached file can be
    verified against its source without any separate manifest.
    """

    ROOT_SEGMENTS: ClassVar[Tuple[str, ...]] = ("payload", "document", "etl", "format")

    @classmethod
    def identifier_for(cls, source: Path) -> str:
        return hashlib.sha256(source.read_bytes()).hexdigest()

    @classmethod
    def resolve(
        cls,
        container: Path,
        source_format: str,
        target_format: str,
        identifier: str,
        suffix: str,
    ) -> Path:
        return cls.directory_for(container, source_format, target_format) / (
            f"{identifier}{suffix}"
        )

    @classmethod
    def directory_for(
        cls,
        container: Path,
        source_format: str,
        target_format: str,
    ) -> Path:
        """Return the directory a source/target pair's cached outputs live in."""
        return container.joinpath(
            ProjectContract.DATASET_NAME,
            *cls.ROOT_SEGMENTS,
            source_format,
            target_format,
        )


class DrawingViewPayloadPath:
    """Resolve where the Drawing Views extracted from a drawing belong on disk.

    Views are a transformation of their drawing, so they sit in the same
    payload tree as the other drawing transformations, in a directory
    addressed by the SHA-256 of the drawing's bytes: extracting the views of
    the same content again addresses the same directory.
    """

    ROOT_SEGMENTS: ClassVar[Tuple[str, ...]] = ("payload", "document", "etl", "view")

    @classmethod
    def directory_for(cls, container: Path, drawing: Path) -> Path:
        return container.joinpath(
            ProjectContract.DATASET_NAME,
            *cls.ROOT_SEGMENTS,
            TransformationPayloadPath.identifier_for(drawing),
        )
