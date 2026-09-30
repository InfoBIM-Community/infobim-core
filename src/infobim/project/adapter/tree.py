from pathlib import Path
from typing import Any, ClassVar, Dict, FrozenSet, List, Optional

from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from infobim.project.adapter.contract import ProjectGuard
from infobim.shared.adapter.tree import FileTree


class ModelTree:
    """Build the IFC-model branch shown when inspecting a project."""

    ROOT_NAME_BY_LANGUAGE: ClassVar[Dict[str, str]] = {
        "en": "Models",
        "pt-br": "Modelos",
    }
    DEFAULT_LANGUAGE: ClassVar[str] = "en"
    ROOT_KIND: ClassVar[str] = "model"
    MODEL_KIND: ClassVar[str] = "model"

    @classmethod
    def of(cls, model_paths: List[str], lang: str = DEFAULT_LANGUAGE) -> Dict[str, Any]:
        return FileTree.of(
            file_paths=model_paths,
            root_name=cls._root_name_of(lang),
            root_kind=cls.ROOT_KIND,
            file_kind=cls.MODEL_KIND,
        )

    @classmethod
    def _root_name_of(cls, lang: str) -> str:
        if lang in cls.ROOT_NAME_BY_LANGUAGE:
            return cls.ROOT_NAME_BY_LANGUAGE[lang]
        return cls.ROOT_NAME_BY_LANGUAGE[cls.DEFAULT_LANGUAGE]


class ProjectTree:
    """
    Builds the tree a reader sees when inspecting an InfoBIM project.

    A project is read from its IfcProject down. The container underneath it
    is what OntoBDC inspects, and says nothing an InfoBIM reader is looking
    for, so nothing of it is repeated here: the root is the IfcProject, and
    what hangs from it is what the project holds.

    Callers may supply loaded branches. Without them, the tree retains the
    default project outline. Structural category nodes are kept non-openable
    without rewriting their semantic ``kind``.
    """

    ROOT_KIND: ClassVar[str] = "root"
    OPENABLE_KEY: ClassVar[str] = "openable"
    MODELS_NAME_BY_LANGUAGE: ClassVar[Dict[str, str]] = {
        "en": "Models",
        "pt-br": "Modelos",
    }
    MODELS_KIND: ClassVar[str] = "model"
    DRAWINGS_NAME_BY_LANGUAGE: ClassVar[Dict[str, str]] = {
        "en": "Drawings",
        "pt-br": "Pranchas e Desenhos",
    }
    DRAWINGS_KIND: ClassVar[str] = "drawing"
    MODELS_SECTION_NAMES: ClassVar[FrozenSet[str]] = frozenset(
        MODELS_NAME_BY_LANGUAGE.values()
    )
    DRAWINGS_SECTION_NAMES: ClassVar[FrozenSet[str]] = frozenset(
        DRAWINGS_NAME_BY_LANGUAGE.values()
    )
    IFC_PROJECT_LABEL: ClassVar[str] = "IfcProject"
    DEFAULT_LANGUAGE: ClassVar[str] = "en"

    @classmethod
    def of(
        cls,
        project_path: Path,
        branches: Optional[List[Dict[str, Any]]] = None,
        lang: str = DEFAULT_LANGUAGE,
    ) -> Dict[str, Any]:
        raw_branches: List[Dict[str, Any]] = (
            cls._branches(lang) if branches is None else branches
        )
        normalised: List[Dict[str, Any]] = [
            cls._normalise_section_branch(branch)
            for branch in raw_branches
            if isinstance(branch, dict)
        ]
        return {
            "name": cls.root_name(project_path),
            "kind": cls.ROOT_KIND,
            "children": normalised,
        }

    @classmethod
    def _normalise_section_branch(cls, branch: Dict[str, Any]) -> Dict[str, Any]:
        name_value: Any = branch.get("name")
        if not isinstance(name_value, str):
            return branch
        if not (
            name_value in cls.MODELS_SECTION_NAMES
            or name_value in cls.DRAWINGS_SECTION_NAMES
        ):
            return branch
        if branch.get(cls.OPENABLE_KEY) is False:
            return branch

        rewritten: Dict[str, Any] = dict(branch)
        rewritten[cls.OPENABLE_KEY] = False
        return rewritten

    @classmethod
    def root_name(cls, project_path: Path) -> str:
        global_id: Optional[str] = ProjectGuard.ifc_project_global_id(project_path)
        if global_id is None:
            raise CliCommandArgumentException(
                f"{project_path} declares no single IfcProject, so there is "
                f"no project to inspect. Run `infobim project --health` to "
                f"see what is missing."
            )

        return f"{cls.IFC_PROJECT_LABEL} ({global_id})"

    @classmethod
    def _branches(cls, lang: str = DEFAULT_LANGUAGE) -> List[Dict[str, Any]]:
        models_name: str = (
            cls.MODELS_NAME_BY_LANGUAGE[lang]
            if lang in cls.MODELS_NAME_BY_LANGUAGE
            else cls.MODELS_NAME_BY_LANGUAGE[cls.DEFAULT_LANGUAGE]
        )
        drawings_name: str = (
            cls.DRAWINGS_NAME_BY_LANGUAGE[lang]
            if lang in cls.DRAWINGS_NAME_BY_LANGUAGE
            else cls.DRAWINGS_NAME_BY_LANGUAGE[cls.DEFAULT_LANGUAGE]
        )
        return [
            {
                "name": models_name,
                "kind": cls.MODELS_KIND,
                cls.OPENABLE_KEY: False,
                "children": [],
            },
            {
                "name": drawings_name,
                "kind": cls.DRAWINGS_KIND,
                cls.OPENABLE_KEY: False,
                "children": [],
            },
        ]
