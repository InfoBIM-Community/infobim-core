from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Dict, List, Optional, Type

from infobim.view.adapter.i18n import catalog_for_namespace
from infobim.view.plugin.component.ifc_model import IfcModelTileComponent
from infobim.view.plugin.component.ifc_project import IfcProjectTileComponent
from infobim.view.plugin.component.ifc_work_schedule import (
    IfcWorkScheduleTileComponent,
)
from ontobdc.shared.adapter.loader import ComponentLoader
from ontobdc.shared.domain.port.component import ComponentPort

_I18N_PLACEHOLDER = "__ONTOBDC_BUILD_I18N__"

_I18N_NAMESPACE_BY_ASSET = {
    "onto-infobim-project-tile.js": "project_tile",
    "onto-infobim-ifc-model-tile.js": "ifc_model_tile",
    "onto-infobim-ifc-work-schedule-tile.js": "ifc_work_schedule_tile",
}


class InfoBIMComponentLoader(ComponentLoader):
    """Extend matching with BIM descriptors while retaining generic Tiles."""

    _INFOBIM_COMPONENTS = (
        IfcProjectTileComponent,
        IfcModelTileComponent,
        IfcWorkScheduleTileComponent,
    )

    def get_all(
        self,
        resource: str = "component",
    ) -> List[Type[ComponentPort]]:
        components = list(super().get_all(resource))
        if resource == "component":
            components.extend(self._INFOBIM_COMPONENTS)
        unique: Dict[str, Type[ComponentPort]] = {}
        for component in components:
            unique[component.METADATA.id] = component
        return list(unique.values())


class InfoBIMComponentSourceAdapter:
    """Return the complete offline component set needed by an InfoBIM Surface."""

    _INFOBIM_ASSETS = (
        "onto-infobim-project-tile.js",
        "onto-infobim-ifc-model-tile.js",
        "onto-infobim-ifc-work-schedule-tile.js",
    )

    def scripts(self, root_path: Optional[str] = None) -> List[str]:
        """Return component script sources for the surface.

        ``root_path`` is forwarded onto every ``ontobdc_view.component_source``
        call so branded tiles (``onto-logo-tile``, etc.) can discover the
        correct product-level SVGs on disk (InfoBIM vs OntoBDC defaults)
        even when the surface is generated for a nested per-project
        container whose assets live in a super-project/workspace root
        above it.

        ``root_path`` may be ``None`` -- the view layer is defensive and
        falls back to ``Path.cwd()`` with a parent-walk in that case -- but
        callers (``ViewProjectCommand.run``) are encouraged to pass the
        resolved ``project_path``/``container_path`` when known for more
        predictable behaviour on shell-less/daemon environments where
        ``cwd`` may not equal the project workspace.
        """
        import ontobdc_view

        try:
            if isinstance(root_path, str) and root_path.strip():
                resolved_root: Optional[str] = str(
                    Path(root_path).expanduser().resolve()
                )
            else:
                resolved_root = str(Path.cwd().resolve())
        except (OSError, ValueError):
            resolved_root = None

        tags = {"onto-presentation-surface"}
        tags.update(
            component.METADATA.tag
            for component in ComponentLoader().get_all()
        )

        scripts: List[str] = []
        for tag in sorted(tags):
            source = ontobdc_view.component_source(tag, root_path=resolved_root)
            if isinstance(source, str) and source.strip():
                scripts.append(source)
                continue

            # The ``onto-presentation-surface`` tag is the shared client-side
            # runtime used by every tile: a missing source here is a real
            # packaging error and must not be silenced.  Any other tag is
            # allowed to come back empty because several components registered
            # in the Python loader are **terminal-only widgets** (e.g.
            # ``onto-logo-tile-terminal`` used by the CLI frame).  They have
            # no JavaScript representation to embed into the offline HTML
            # Surface and must be skipped here.
            if tag == "onto-presentation-surface":
                raise ValueError(
                    f"ontobdc-view did not provide component source: {tag}"
                )

        asset_root = files("infobim").joinpath(
            "view", "plugin", "asset", "js"
        )
        for filename in self._INFOBIM_ASSETS:
            source = asset_root.joinpath(filename).read_text(encoding="utf-8")
            if not source.strip():
                raise ValueError(f"Empty InfoBIM component source: {filename}")
            if _I18N_PLACEHOLDER in source:
                namespace = _I18N_NAMESPACE_BY_ASSET.get(filename, "")
                encoded = json.dumps(
                    catalog_for_namespace(namespace), ensure_ascii=False, separators=(",", ":")
                )
                source = source.replace(_I18N_PLACEHOLDER, encoded)
            scripts.append(source)
        return scripts

