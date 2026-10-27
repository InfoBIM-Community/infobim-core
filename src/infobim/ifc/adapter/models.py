from pathlib import Path
from typing import ClassVar, List, Optional, Set

from ontobdc.storage.adapter.crate import ContainerRoCrate


class IfcProjectModels:
    """
    The IFC models a project holds, as its RO-Crate declares them.
    """

    IFC_FILE_SUFFIXES: ClassVar[Set[str]] = {".ifc", ".ifczip", ".ifcxml"}

    @classmethod
    def declared_paths(cls, project_path: Path) -> Optional[Set[str]]:
        """
        The path, relative to the project, of every file its RO-Crate declares, or None when the crate
        cannot be read. A file is named by its path or by an identifier whose node says the path in its
        history; the crate reader of OntoBDC knows both.
        """
        try:
            return set(ContainerRoCrate.file_paths(project_path))
        except (ValueError, OSError):
            return None

    @classmethod
    def paths(cls, project_path: Path) -> Optional[List[Path]]:
        """
        The IFC models the project's RO-Crate declares and that exist on
        disk, or None when the crate cannot be read.
        """
        declared: Optional[Set[str]] = cls.declared_paths(project_path)
        if declared is None:
            return None

        model_paths: List[Path] = []
        for file_path in declared:
            relative: Path = Path(file_path)
            if relative.is_absolute():
                continue
            if relative.suffix.lower() not in cls.IFC_FILE_SUFFIXES:
                continue
            absolute: Path = (project_path / relative).resolve()
            if absolute.is_file():
                model_paths.append(absolute)

        return model_paths
