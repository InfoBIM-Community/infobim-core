import json
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Tuple, Optional

from ontobdc.container.adapter.dataset import RegisteredDatasets

from infobim.project.domain.model.contract import ProjectContract
from infobim.drawing.adapter.dxf_ifcx_linkset import DxfIfcxLinksetWriter
from infobim.drawing.adapter.transformation_payload import (
    TransformationPayloadPath,
)
from infobim.drawing.domain.exception.repair import (
    DrawingDwgLinkUnrecoverableError,
    IfcxTitleUnrecoverableError,
)
from infobim._3d.plugin.check.is_drawing_linked_to_project.check import (
    main as check_drawing_linked_to_project,
)
from infobim._3d.plugin.check.is_drawing_linked_to_project.hotfix import (
    main as hotfix_drawing_linked_to_project,
)
from infobim._3d.plugin.check.is_ifcx_header_title_present.check import (
    main as check_ifcx_header_title_present,
)
from infobim._3d.plugin.check.is_ifcx_header_title_present.hotfix import (
    main as hotfix_ifcx_header_title_present,
)

from .tree import ThreeDElementTree


class ThreeDElementDiscovery:
    """
    Finds every renderable 3D element a Project and its datasets hold.

    Shared by ThreeDInspectCommand (`infobim 3d --inspect`) and
    ThreeDElementTreeInjectedCapability (the offline viewer's "3D
    inspect" tab), so the CLI and the viewer never disagree about which
    elements exist or what each one is titled -- an IFCX element's
    missing title is repaired here, once, the same way for both.

    A dataset is not guessed from the filesystem -- it is read from
    RegisteredDatasets, the same registry the container's own health
    and refresh pipelines resolve datasets through, so a directory that
    merely looks like a dataset is not searched as one.
    """

    RENDERABLE_SUFFIXES: ClassVar[Tuple[str, ...]] = (".ifcx", ".ifc-3d")
    LINKSET_DIRECTORY_NAME: ClassVar[str] = "linkset"
    _DXF_CACHE_SOURCE: ClassVar[str] = "dwg"
    _DXF_CACHE_FORMAT: ClassVar[str] = "dxf"
    _DXF_IFCX_FORMAT: ClassVar[str] = "ifcx"

    @classmethod
    def of(cls, project_path: Path) -> List[Dict[str, str]]:
        """
        Return every element as {title, file_name}, for a plain listing.
        """
        return [
            {
                ThreeDElementTree.TITLE_KEY: title,
                ThreeDElementTree.FILE_NAME_KEY: file_name,
            }
            for _, title, file_name in cls._discover(project_path)
        ]

    @classmethod
    def with_documents(cls, project_path: Path) -> List[Dict[str, Any]]:
        """
        Return every element as {title, file_name, document}.

        The offline viewer has no way to fetch a file by path once it is
        launched (see OfflineViewer.launch_page): a "3D inspect" tree
        node that a click should load into the scene must already carry
        everything ViewerModels.add needs, not just a path. *.ifc-3d
        elements carry no document -- nothing today parses that format
        the way IFCX is parsed here, so the viewer cannot load one by
        content the way it loads an IFCX either.
        """
        elements: List[Dict[str, Any]] = []
        for path, title, file_name in cls._discover(project_path):
            element: Dict[str, Any] = {
                ThreeDElementTree.TITLE_KEY: title,
                ThreeDElementTree.FILE_NAME_KEY: file_name,
            }
            if path.suffix.lower() == ".ifcx":
                element[ThreeDElementTree.DOCUMENT_KEY] = json.loads(
                    path.read_text(encoding="utf-8")
                )
            elements.append(element)

        return elements

    @classmethod
    def _discover(cls, project_path: Path) -> List[Tuple[Path, str, str]]:
        """
        Walk the Project and its datasets once, returning each renderable
        element as (absolute path, title, file name).

        A registered dataset's location is not guaranteed to sit inside
        the Project's own directory (RegisteredDatasets.of() resolves
        wherever its container.ttl says it lives). When it doesn't, the
        dataset's own directory name is kept as the leading path segment
        of the deduplication key, so an element a dataset shares with
        the Project's own tree (a dataset nested inside it) is not
        listed twice.
        """
        roots: List[Path] = [project_path] + RegisteredDatasets.of(project_path)
        found: Dict[str, Tuple[Path, str, str]] = {}
        root: Path
        for root in roots:
            path: Path
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in cls.RENDERABLE_SUFFIXES:
                    continue

                display_path: str = cls._display_path(path, root, project_path)
                if display_path in found:
                    continue

                found[display_path] = (
                    path,
                    cls._title_of(path, project_path),
                    path.name,
                )

        return list(found.values())

    @staticmethod
    def _display_path(path: Path, root: Path, project_path: Path) -> str:
        try:
            return str(path.relative_to(project_path))
        except ValueError:
            return str(Path(root.name) / path.relative_to(root))

    @staticmethod
    def _title_of(path: Path, project_path: Path) -> str:
        """
        Return the element's title, repairing a missing one first.

        Only IFCX carries this concern -- an IFCX file is named by the
        SHA-256 of the DXF it was converted from, so it has no human
        name of its own until is_ifcx_header_title_present repairs it.
        Any other renderable suffix is shown by its own file name.
        """
        if path.suffix.lower() != ".ifcx":
            return path.name

        # An IFCX that already says what it is called is not a file with
        # a missing title: the repair below exists for a drawing's IFCX,
        # named after the SHA-256 of the DXF it came from and carrying no
        # name of its own until its linkset gives it one. An element's
        # mesh arrives named, because the element it draws is named.
        stated: Optional[str] = ThreeDElementDiscovery._stated_title(path)
        if stated is not None:
            return stated

        ThreeDElementDiscovery._ensure_drawing_linked(path, project_path)

        if check_ifcx_header_title_present(ifcx_path=str(path)) != 0:
            if hotfix_ifcx_header_title_present(
                ifcx_path=str(path), container_path=str(project_path)
            ) != 0:
                raise IfcxTitleUnrecoverableError(
                    f"The IFCX file at {path} could not be repaired to "
                    f"carry a title."
                )

        document: Any = json.loads(path.read_text(encoding="utf-8"))
        header: Any = document.get("header") if isinstance(document, dict) else None
        title: Any = header.get("title") if isinstance(header, dict) else None
        if not isinstance(title, str) or not title.strip():
            raise IfcxTitleUnrecoverableError(
                f"The IFCX file at {path} carries no title even after repair."
            )

        return title

    @staticmethod
    def _dxf_path_for_ifcx(ifcx_path: Path, project_path: Path) -> Optional[Path]:
        dxf_cache: Path = TransformationPayloadPath.directory_for(
            project_path,
            ThreeDElementDiscovery._DXF_CACHE_SOURCE,
            ThreeDElementDiscovery._DXF_CACHE_FORMAT,
        )
        if not dxf_cache.is_dir():
            return None

        expected_hash: str = ifcx_path.stem
        candidate: Path
        for candidate in dxf_cache.rglob(
            f"*.{ThreeDElementDiscovery._DXF_CACHE_FORMAT}"
        ):
            if not candidate.is_file():
                continue
            try:
                if TransformationPayloadPath.identifier_for(candidate) == expected_hash:
                    return candidate.resolve()
            except OSError:
                continue
        return None
    def _stated_title(path: Path) -> Optional[str]:
        """
        Return the title the IFCX states for itself, or None when it
        states none.
        """
        try:
            document: Any = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

        header: Any = document.get("header") if isinstance(document, dict) else None
        title: Any = header.get("title") if isinstance(header, dict) else None

        return title.strip() if isinstance(title, str) and title.strip() else None

    @staticmethod
    def _ensure_drawing_linked(path: Path, project_path: Path) -> None:
        """
        Repair the drawing's own linkset before reading anything derived
        from it.

        is_ifcx_header_title_present reads name_IfcRoot off this same
        linkset instead of re-deriving a title itself, so nothing
        downstream can find it until is_drawing_linked_to_project has
        actually run. A drawing with no linkset at all (not every
        renderable IFCX necessarily came through the DWG/DXF pipeline)
        is left alone -- that absence is a different concern than an
        existing linkset missing a required property.
        """
        linkset_path: Path = (
            project_path
            / ProjectContract.DATASET_NAME
            / ProjectContract.PAYLOAD_DIRECTORY_NAME
            / ThreeDElementDiscovery.LINKSET_DIRECTORY_NAME
            / f"{path.stem}.ttl"
        )
        if not linkset_path.is_file():
            dxf_path: Optional[Path] = ThreeDElementDiscovery._dxf_path_for_ifcx(
                path, project_path
            )
            if dxf_path is None:
                return
            try:
                DxfIfcxLinksetWriter.write(project_path, dxf_path, path)
            except (OSError, ValueError):
                return
            if not linkset_path.is_file():
                return

        # Exit 2 is the check saying this is not a drawing's linkset at
        # all -- an element's mesh has one of its own, declaring an IFC
        # model where a drawing's declares a DXF. Repairing that as a
        # drawing's would be repairing something else's file.
        if check_drawing_linked_to_project(linkset_path=str(linkset_path)) == 1:
            if hotfix_drawing_linked_to_project(
                linkset_path=str(linkset_path), container_path=str(project_path)
            ) != 0:
                raise DrawingDwgLinkUnrecoverableError(
                    f"The linkset at {linkset_path} could not be repaired."
                )
