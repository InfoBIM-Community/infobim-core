from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any, Dict, List, Optional

from infobim.project.plugin.parameter.project import ProjectIdStrategy
from infobim.view.adapter.component import InfoBIMComponentSourceAdapter
from infobim.view.adapter.machine import (
    InfoBIMSurfaceGenerationStateTransitionHandler,
)
from infobim.view.adapter.project import (
    InfoBIMProjectPresentationRepository,
)
from infobim.view.adapter.regeneration import (
    InfoBIMSurfaceRegenerationWorkerLauncher,
)
from ontobdc.cli.domain.exception.command import CliCommandArgumentException
from ontobdc.cli.domain.model.command import CliCommandMetadata
from ontobdc.cli.domain.port.command import CliCommandPort
from ontobdc.cli.domain.request.command import CliCommandRequest
from ontobdc.cli.domain.response.command import CommandResponse
from ontobdc.shared.adapter.filesystem import remove_directory_tree, remove_file
from ontobdc.view.adapter.surface.context import SurfaceContextAdapter
from ontobdc.view.plugin.capability.transformation.data_gathered import (
    DataGatheredCapability,
)


class ViewProjectCommand(CliCommandPort):
    """Project-aware proxy into the OntoBDC Presentation Surface pipeline."""

    METADATA = CliCommandMetadata(
        id="view_project",
        logical_component="view",
        description="Generate the InfoBIM Surface for an IfcProject.",
        arguments=[
            {
                "accepts": ["--project-id", "--project"],
                "valued": True,
                "description": (
                    "Select the Project by IfcProject GlobalId, or infer it "
                    "from the current Project directory."
                ),
                "usage": "infobim view --project-id <IfcProject GlobalId>",
            },
            {
                "accepts": ["--type"],
                "valued": True,
                "description": "Select the Surface type (standard).",
            },
            {
                "accepts": ["--representation"],
                "valued": True,
                "description": "Select the representation (html).",
            },
            {
                "accepts": ["--language"],
                "valued": True,
                "description": "Declare the Surface language.",
            },
        ],
    )

    _VALUED_FLAGS = {
        "--project-id",
        "--project",
        "--type",
        "--representation",
        "--language",
    }

    @staticmethod
    def accepts(args: List[str]) -> bool:
        if not args or args[0] != "view":
            return False
        remaining = args[1:]
        seen = set()
        index = 0
        while index < len(remaining):
            flag = remaining[index]
            if flag not in ViewProjectCommand._VALUED_FLAGS or flag in seen:
                return False
            if (
                index + 1 >= len(remaining)
                or str(remaining[index + 1]).startswith("--")
            ):
                return False
            seen.add(flag)
            index += 2
        return not ({"--project-id", "--project"} <= seen)

    def __init__(self, request: CliCommandRequest):
        self._request = request

    def check(self) -> bool:
        self._bind_explicit_values()
        # The root ``.__ontobdc__/context.ttl`` is shared by every sibling
        # container in a project.  A previous ``infobim view`` run against
        # another project (e.g. ``data/``) leaves stale ``container_*`` and
        # ``surface_*`` parameters persisted there.  ``ProjectIdStrategy``
        # below only knows about ``project_id`` / ``project_path`` and would
        # happily leave those stale bindings in place; later the
        # ``SurfaceContextAdapter`` would then derive the output
        # ``index.html`` location from the *stale* ``container_path`` and
        # silently write / open the wrong project's surface page.  Wipe any
        # persisted surface-target parameters BEFORE we resolve the current
        # project so the pipeline always targets the directory the user
        # actually ``cd``'d into.
        context = self._request.context
        if getattr(context, "delete_parameter", None) is not None:
            context.delete_parameter("container_id")
            context.delete_parameter("container_path")
            context.delete_parameter("surface_id")
            context.delete_parameter("surface_path")
        ProjectIdStrategy().execute(context)

        project_id = self._context_value("project_id")
        project_path = self._context_value("project_path")
        if not project_id or not project_path or not Path(project_path).is_dir():
            if self._argument_value("--project-id") or self._argument_value("--project"):
                raise CliCommandArgumentException(
                    "No InfoBIM Project matches the given --project-id/--project "
                    "selector. Run `infobim project --list` to see registered "
                    "Projects."
                )
            raise CliCommandArgumentException(
                "No IfcProject found in this directory. Run `infobim view` "
                "from inside an InfoBIM Project directory, or pass "
                "--project-id <GlobalId> (see `infobim project --list`)."
            )

        # Mirror the resolved project location onto the generic container
        # parameters used by the downstream OntoBDC surface pipeline.  The
        # project directory IS the data container for ``infobim view``; by
        # setting both here we guarantee that every downstream adapter
        # (``SurfaceContextAdapter``, ``DataGatheredCapability``, ETL state
        # directories, standalone viewer sidecar, etc.) writes artifacts
        # NEXT TO the project's own files -- and not next to some stale
        # sibling container lingering in ``context.ttl``.
        context.set_parameter_value("container_id", project_id)
        context.set_parameter_value("container_path", str(Path(str(project_path)).expanduser().resolve()))

        representation = (
            self._argument_value("--representation") or "html"
        ).lower()
        if representation != "html":
            raise CliCommandArgumentException(
                "infobim view currently supports --representation html only."
            )

        view_type = (self._argument_value("--type") or "standard").lower()
        if view_type != "standard":
            raise CliCommandArgumentException(
                "infobim view currently supports --type standard only."
            )

        self._request.context.set_parameter_value(
            "representation", representation
        )
        self._request.context.set_parameter_value("view_type", view_type)
        self._request.context.set_parameter_value(
            "language",
            (self._argument_value("--language") or "en").lower(),
        )
        return True

    def run(self) -> CommandResponse:
        project_id = self._required_context_value("project_id")
        project_path = self._required_context_value("project_path")
        presentation = InfoBIMProjectPresentationRepository().load(
            project_id=project_id,
            project_path=project_path,
        )

        surface_path = SurfaceContextAdapter().surface_path(self._request.context)
        if surface_path.is_file():
            remove_file(surface_path)
        etl_directory = DataGatheredCapability.state_directory(
            self._request.context
        )
        if etl_directory.is_dir():
            remove_directory_tree(etl_directory)

        self._request.context.set_parameter_value(
            "surface_component_scripts",
            InfoBIMComponentSourceAdapter().scripts(root_path=project_path),
        )
        response = InfoBIMSurfaceGenerationStateTransitionHandler(
            context=self._request.context,
            presentation=presentation,
        ).execute()

        if not surface_path.is_file():
            raise FileNotFoundError(
                "The InfoBIM Surface pipeline finished without generating "
                f"{surface_path}."
            )

        regeneration_worker_pid = InfoBIMSurfaceRegenerationWorkerLauncher().ensure_running(
            project_id=project_id,
            project_path=project_path,
            context_root=self._request.context.root_path,
            language=str(self._context_value("language") or "en"),
        )

        index_uri = surface_path.as_uri()
        browser_opened = False
        runtime_error: Optional[str] = None
        try:
            browser_opened = bool(webbrowser.open(index_uri, new=2))
            if not browser_opened:
                runtime_error = (
                    "The Surface was generated, but the default browser did "
                    f"not open {index_uri}."
                )
        except Exception as error:
            runtime_error = str(error)

        content: Dict[str, Any]
        if isinstance(response.content, dict):
            content = response.content
        else:
            content = {"result": response.content}
            response.content = content
        content.update(
            {
                "project_id": project_id,
                "project_path": project_path,
                "regeneration_worker_pid": regeneration_worker_pid,
                "container_id": self._context_value("container_id"),
                "view_type": self._context_value("view_type"),
                "representation": self._context_value("representation"),
                "language": self._context_value("language"),
                "index_path": str(surface_path),
                "index_uri": index_uri,
                "browser_opened": browser_opened,
                "runtime_error": runtime_error,
                "ifc_class_count": len(presentation.classes),
                "ifc_element_count": presentation.element_count,
            }
        )
        response.title = "InfoBIM Project Surface Generated"
        response.description = (
            f"Presented IfcProject '{project_id}' through the OntoBDC "
            "Presentation Surface pipeline."
        )
        return response

    def _bind_explicit_values(self) -> None:
        for flag, parameter in (
            ("--project-id", "project_id"),
            ("--project", "project"),
        ):
            value = self._argument_value(flag)
            if value is not None:
                self._request.context.set_parameter_value(parameter, value)

    def _argument_value(self, flag: str) -> Optional[str]:
        args = list(self._request.command_args)
        if flag not in args:
            return None
        index = args.index(flag) + 1
        if index >= len(args):
            return None
        value = str(args[index] or "").strip()
        return value or None

    def _context_value(self, name: str) -> Optional[str]:
        if not self._request.context.has_parameter(name):
            return None
        value = str(
            self._request.context.get_parameter_value(name) or ""
        ).strip()
        return value or None

    def _required_context_value(self, name: str) -> str:
        value = self._context_value(name)
        if value is None:
            raise CliCommandArgumentException(
                f"Required InfoBIM View context was not resolved: {name}"
            )
        return value
