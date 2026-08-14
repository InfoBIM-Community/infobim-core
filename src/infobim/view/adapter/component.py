from __future__ import annotations

from importlib.resources import files
from typing import Dict, List, Type

from infobim.view.plugin.component.ifc_model import IfcModelTileComponent
from infobim.view.plugin.component.ifc_project import IfcProjectTileComponent
from infobim.view.plugin.component.ifc_work_schedule import (
    IfcWorkScheduleTileComponent,
)
from ontobdc.shared.adapter.loader import ComponentLoader
from ontobdc.shared.domain.port.component import ComponentPort


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

    def scripts(self) -> List[str]:
        import ontobdc_view

        tags = {"onto-presentation-surface"}
        tags.update(
            component.METADATA.tag
            for component in ComponentLoader().get_all()
        )

        scripts: List[str] = []
        for tag in sorted(tags):
            source = ontobdc_view.component_source(tag)
            if not isinstance(source, str) or not source.strip():
                raise ValueError(
                    f"ontobdc-view did not provide component source: {tag}"
                )
            scripts.append(source)

        asset_root = files("infobim").joinpath(
            "view", "plugin", "asset", "js"
        )
        for filename in self._INFOBIM_ASSETS:
            source = asset_root.joinpath(filename).read_text(encoding="utf-8")
            if not source.strip():
                raise ValueError(f"Empty InfoBIM component source: {filename}")
            scripts.append(source)
        return scripts

