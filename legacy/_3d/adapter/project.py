"""Read the selected Project's declared 3D files without modifying its data."""

import json
from typing import Any, Dict, List, Set, Tuple
from pathlib import Path, PurePosixPath
from urllib.parse import SplitResult, unquote, urlsplit

from ontobdc.storage.adapter.bootstrap import StorageBootstrap

from .dwg import DwgConverter
from infobim.drawing.model import DrawingPlacement, IfcxDocument
from infobim.drawing.adapter.dxf import DxfConversion, DxfConverter
from infobim.project.adapter.contract import ProjectGuard
from infobim.project.domain.model.contract import ProjectContract


class ProjectScene:
    @classmethod
    def load(cls, project: Path) -> Dict[str, Any]:
        global_id: Any = ProjectGuard.ifc_project_global_id(project)
        if not isinstance(global_id, str) or not global_id:
            raise ValueError("The Project must declare exactly one readable IfcProject GlobalId.")
        files: List[Tuple[str, Path]] = cls._files(project)
        placements: Dict[str, DrawingPlacement] = cls._placements(project)
        cad_names: Set[str] = {name for name, path in files if path.suffix.lower() in {".dxf", ".dwg"}}
        if set(placements) - cad_names:
            raise ValueError(f"3D settings reference CAD files absent from the RO-Crate: {sorted(set(placements) - cad_names)}")
        models: List[Dict[str, Any]] = []
        warnings: List[str] = []
        dwg_converter: DwgConverter | None = DwgConverter() if any(path.suffix.lower() == ".dwg" for _, path in files) else None
        name: str
        source: Path
        for name, source in files:
            suffix: str = source.suffix.lower()
            if suffix in {".dxf", ".dwg"}:
                placement: DrawingPlacement = placements[name] if name in placements else DrawingPlacement()
                converted: DxfConversion
                if suffix == ".dwg":
                    if dwg_converter is None:
                        raise RuntimeError("The DWG converter was not initialized.")
                    converted = dwg_converter.convert(source, f"{global_id}/{name}", placement)
                else:
                    converted = DxfConverter.convert(source, f"{global_id}/{name}", placement)
                models.append({"name": str(PurePosixPath(name).with_suffix(".ifcx")), "model": converted.document})
                if converted.unsupported:
                    warnings.append(f"{name}: unsupported CAD entities omitted: {converted.unsupported}")
            else:
                document: Dict[str, Any] = IfcxDocument.validate(cls._json(source), name)
                models.append({"name": name, "model": document})
        if not models:
            raise ValueError("The Project RO-Crate contains no DWG, DXF or IFCX drawings to display.")
        return {"project": project.name, "globalId": global_id, "models": models, "warnings": warnings}

    @staticmethod
    def _json(path: Path) -> Any:
        return json.loads(path.read_text(encoding="utf-8"))

    @classmethod
    def _files(cls, project: Path) -> List[Tuple[str, Path]]:
        crate_path: Path = StorageBootstrap.get_container_crate_metadata_file_path(project)
        crate: Any = cls._json(crate_path)
        if not isinstance(crate, dict) or not isinstance(crate.get("@graph"), list):
            raise ValueError(f"Invalid Project RO-Crate: {crate_path.name}")
        result: List[Tuple[str, Path]] = []
        seen: Set[Path] = set()
        node: Any
        for node in crate["@graph"]:
            if not isinstance(node, dict):
                raise ValueError("Each RO-Crate graph entry must be an object.")
            types: Any = node.get("@type")
            if types != "File" and not (isinstance(types, list) and "File" in types):
                continue
            identifier: Any = node.get("@id")
            if not isinstance(identifier, str) or not identifier.strip():
                raise ValueError("RO-Crate File entry has no valid @id.")
            reference: str = unquote(identifier)
            if PurePosixPath(reference).suffix.lower() not in {".dxf", ".ifcx", ".dwg"}:
                continue
            uri: SplitResult = urlsplit(identifier)
            relative: PurePosixPath = PurePosixPath(reference)
            if uri.scheme or uri.netloc or uri.query or uri.fragment or relative.is_absolute() or ".." in relative.parts or "\\" in reference:
                raise ValueError(f"3D file must have a relative path inside the Project: {identifier}")
            path: Path = (project / relative).resolve()
            if not path.is_relative_to(project.resolve()):
                raise ValueError(f"3D file escapes the Project: {identifier}")
            if not path.is_file():
                raise ValueError(f"RO-Crate 3D file is missing: {identifier}")
            if path not in seen:
                seen.add(path)
                result.append((relative.as_posix(), path))
        return sorted(result)

    @classmethod
    def _placements(cls, project: Path) -> Dict[str, DrawingPlacement]:
        config: Path = project / ProjectContract.DATASET_NAME / "3d.json"
        if not config.exists():
            return {}
        value: Any = cls._json(config)
        if not isinstance(value, dict) or set(value) != {"drawings"} or not isinstance(value["drawings"], dict):
            raise ValueError("3d.json must contain a drawings object keyed by relative DWG or DXF path.")
        result: Dict[str, DrawingPlacement] = {}
        name: str
        settings: Any
        for name, settings in value["drawings"].items():
            if not name or PurePosixPath(name).as_posix() != name:
                raise ValueError(f"3d.json drawing path must be normalized: {name}")
            result[name] = DrawingPlacement.from_json(settings)
        return result
