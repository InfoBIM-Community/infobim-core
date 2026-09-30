"""Produce one offline launch page with the selected Project embedded as JSON."""

import json
from typing import Any, ClassVar, Dict, Optional
from pathlib import Path
from tempfile import NamedTemporaryFile

from ..vendor import ViewerAsset


class OfflineViewer:
    MARKER: ClassVar[str] = '<script type="application/json" id="infobim-project">null</script>'

    @classmethod
    def launch_page(cls, project: Optional[Dict[str, Any]]) -> Path:
        """
        Render the offline viewer, with project embedded as its bootstrap
        data, or with none at all: project is None launches the viewer
        the same way MARKER's own default already does, at the blank
        "open local IFCX files" state the viewer's own JS falls back to
        when it finds no bootstrap data.
        """
        template: str = ViewerAsset.path().read_text(encoding="utf-8")
        if template.count(cls.MARKER) != 1:
            raise ValueError("The packaged viewer must contain exactly one Project bootstrap marker.")
        payload: str = json.dumps(project, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        script: str = f'<script type="application/json" id="infobim-project">{payload}</script>'
        html: str = template.replace(cls.MARKER, script)
        with NamedTemporaryFile(mode="w", encoding="utf-8", prefix="infobim-3d-", suffix=".html", delete=False) as launch:
            launch.write(html)
            return Path(launch.name)
