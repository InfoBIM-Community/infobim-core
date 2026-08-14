from typing import Optional

from infobim.project.plugin.check.is_ifc_project_facade_ready import evaluate as facade_ready
from infobim.project.plugin.check.is_ifc_project_ready import evaluate as ifc_project_ready
from infobim.project.plugin.check.is_ontobdc_container_ready import evaluate as container_ready
from infobim.project.plugin.check.is_project_dataset_ready import evaluate as dataset_ready


def evaluate(*, container_path: str, root_path: str) -> bool:
    return (
        container_ready(container_path=container_path, root_path=root_path)
        and dataset_ready(container_path=container_path, root_path=root_path)
        and facade_ready(container_path=container_path)
        and ifc_project_ready(container_path=container_path)
    )


def main(container_path: Optional[str] = None, root_path: Optional[str] = None) -> int:
    if not container_path or not root_path:
        return 1
    return 0 if evaluate(container_path=container_path, root_path=root_path) else 1
