import os
from pathlib import Path
from typing import Optional

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, Namespace

from ontobdc.cli.domain.port.context import CliContextPort, CliContextStrategyPort
from ontobdc.shared.domain.model.parameter import ParameterMetadata
from ontobdc.shared.domain.port.parameter import ParameterPort


_IFCOWL = Namespace("http://ifcowl.openbimstandards.org/IFC4#")


class ProjectIdStrategy(ParameterPort, CliContextStrategyPort):
    """Resolve an explicit project identifier or infer it from the current path."""

    METADATA = ParameterMetadata(
        id="org.infobim.domain.project.parameter.project",
        version="0.4.0",
        name="project",
        description=(
            "Resolve --project and --project-id to the project identifier, "
            "or infer the active project from the current directory."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        python_type=str,
    )

    def execute(self, context: CliContextPort) -> CliContextPort:
        raw_project = context.get_parameter_value("project")
        if raw_project is None:
            raw_project = context.get_parameter_value("project_id")

        project_id = str(raw_project or "").strip()
        if project_id:
            context.set_parameter_value("project_id", project_id)
            return context

        inferred_project_id = self._infer_project_id_from_current_path()
        if inferred_project_id:
            context.set_parameter_value("project_id", inferred_project_id)

        return context

    @staticmethod
    def _infer_project_id_from_current_path() -> Optional[str]:
        current_path = Path(os.getcwd()).expanduser().resolve()

        for candidate_root in (current_path, *current_path.parents):
            project_file = (
                candidate_root
                / ".__ontobdc__"
                / "__infobim__"
                / "project.ttl"
            )
            if not project_file.is_file():
                continue

            try:
                project_graph = Graph()
                project_graph.parse(str(project_file), format="turtle")
            except Exception:
                return None

            project_subjects = [
                subject
                for subject in project_graph.subjects(
                    RDF.type,
                    _IFCOWL.IfcProject,
                )
                if isinstance(subject, URIRef)
            ]
            if project_subjects:
                return str(project_subjects[0])

            container_name = candidate_root.name.strip()
            if container_name:
                return f"urn:infobim:project:{container_name}"

        return None
