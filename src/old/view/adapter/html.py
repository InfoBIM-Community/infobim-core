import json
import shutil
import webbrowser
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, RDF, RDFS, Namespace

from ontobdc.view.adapter.workstream import WorkStreamContext

from infobim.view.adapter.card import (
    DynamicMenubarCardAdapter,
    HeroCardAdapter,
    MiniCardGridCardAdapter,
    ProjectInformationCardAdapter,
    PyodideRuntimeCardAdapter,
)


class ProjectDashboardHtmlRenderer:
    _ONTOBDC_DIR_NAME: str = ".__ontobdc__"
    _ASSET_ROOT_NAME: str = "asset"
    _ASSET_NAMESPACE: str = "infobim-view"
    _IFCOWL: Namespace = Namespace("http://ifcowl.openbimstandards.org/IFC4#")
    _WEEKDAY_NAMES: tuple[str, ...] = (
        "segunda-feira",
        "terca-feira",
        "quarta-feira",
        "quinta-feira",
        "sexta-feira",
        "sabado",
        "domingo",
    )
    _MONTH_NAMES: tuple[str, ...] = (
        "janeiro",
        "fevereiro",
        "marco",
        "abril",
        "maio",
        "junho",
        "julho",
        "agosto",
        "setembro",
        "outubro",
        "novembro",
        "dezembro",
    )

    def __init__(self) -> None:
        self._hero_card_adapter = HeroCardAdapter()
        self._dynamic_menubar_card_adapter = DynamicMenubarCardAdapter()
        self._mini_card_grid_card_adapter = MiniCardGridCardAdapter()
        self._project_information_card_adapter = ProjectInformationCardAdapter()
        self._pyodide_runtime_card_adapter = PyodideRuntimeCardAdapter()

    def render(self, project_data: Dict[str, Any]) -> Path:
        container_path: Path = Path(
            str(project_data["path"])
        ).expanduser().resolve()
        output_file: Path = container_path / "index.html"
        asset_output_dir: Path = (
            container_path
            / self._ONTOBDC_DIR_NAME
            / self._ASSET_ROOT_NAME
            / self._ASSET_NAMESPACE
        )
        asset_output_dir.mkdir(parents=True, exist_ok=True)

        self._copy_asset_directory(asset_output_dir)
        output_file.write_text(
            self._build_html_document(project_data),
            encoding="utf-8",
        )
        webbrowser.open(output_file.as_uri())
        return output_file

    def _build_html_document(self, project_data: Dict[str, Any]) -> str:
        template = self._template_environment().get_template(
            "project_dashboard.html.j2"
        )
        container_path: Path = Path(
            str(project_data["path"])
        ).expanduser().resolve()
        project_file: Path = (
            container_path
            / ".__ontobdc__"
            / "__infobim__"
            / "project.ttl"
        )
        asset_root: str = self._asset_root_relative_path()
        payload: Dict[str, Any] = {
            "projectId": str(project_data.get("project_id", "")).strip(),
            "name": str(project_data.get("name", "")).strip(),
            "path": str(container_path),
        }
        return template.render(
            page_title=payload["name"] or "InfoBIM Project",
            hero_card_html=self._hero_card_adapter.render(
                payload,
                self._resolve_project_description(project_file),
                asset_root,
            ),
            dynamic_menubar_card_html=(
                self._dynamic_menubar_card_adapter.render(payload)
            ),
            mini_card_grid_card_html=(
                self._mini_card_grid_card_adapter.render()
            ),
            project_information_card_html=(
                self._project_information_card_adapter.render(
                    payload,
                    self._current_date_label(),
                )
            ),
            pyodide_runtime_card_html=(
                self._pyodide_runtime_card_adapter.render()
            ),
            project=payload,
            pyodide_payload_json=json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
            asset_root=asset_root,
        )

    def _template_environment(self) -> Environment:
        template_dir: Path = (
            Path(__file__).resolve().parents[1] / "plugin" / "template"
        )
        return Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(("html", "xml")),
        )

    def _asset_source_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "plugin" / "asset"

    def _asset_root_relative_path(self) -> str:
        return (
            f"{self._ONTOBDC_DIR_NAME}/"
            f"{self._ASSET_ROOT_NAME}/"
            f"{self._ASSET_NAMESPACE}"
        )

    def _copy_asset_directory(self, asset_output_dir: Path) -> None:
        asset_source_dir: Path = self._asset_source_dir()
        for source_path in asset_source_dir.rglob("*"):
            if source_path.is_dir():
                continue

            relative_path: Path = source_path.relative_to(asset_source_dir)
            target_path: Path = asset_output_dir / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)

    def _resolve_project_description(self, project_file: Path) -> str:
        if not project_file.is_file():
            return ""

        project_graph: Graph = Graph()
        project_graph.parse(str(project_file), format="turtle")

        subjects = [
            subject
            for subject in project_graph.subjects(
                RDF.type,
                self._IFCOWL.IfcProject,
            )
            if isinstance(subject, URIRef)
        ]
        if not subjects:
            return ""

        project_subject: URIRef = subjects[0]
        for predicate in (DCTERMS.description, RDFS.comment):
            values = [
                str(value).strip()
                for value in project_graph.objects(
                    project_subject,
                    predicate,
                )
                if isinstance(value, Literal) and str(value).strip()
            ]
            if values:
                return values[0]

        return ""

    def _current_date_label(self) -> str:
        current_datetime: datetime = datetime.now().astimezone()
        weekday_name: str = self._WEEKDAY_NAMES[
            current_datetime.weekday()
        ]
        month_name: str = self._MONTH_NAMES[current_datetime.month - 1]
        return (
            f"{weekday_name}, {current_datetime.day} de "
            f"{month_name} de {current_datetime.year}"
        )


class WorkStream5W2HHtmlRenderer(ProjectDashboardHtmlRenderer):
    """Render a live 5W2H page backed by the project container."""

    _ONTOBDC_ANNOTATION_MODULES: tuple[str, ...] = (
        "annotation_model.js",
        "annotation_lifecycle.js",
        "annotation_entity_resolver.js",
        "annotation_persistence.js",
        "annotation_visual_contract.js",
        "annotation_visual_resolver.js",
        "annotation_store.js",
        "annotation_surface.js",
        "annotation_renderer.js",
        "annotation_field_factory.js",
        "annotation_form_registry.js",
        "annotation_geometry_controller.js",
        "annotation_editor.js",
        "annotation_runtime.js",
        "annotation_workspace.js",
        "annotation_subject_page.js",
    )
    _ONTOBDC_ANNOTATION_STYLES: tuple[str, ...] = (
        "annotation_visual.css",
        "annotation_editor.css",
        "annotation_workspace.css",
    )
    _ONTOBDC_WORKSTREAM_MODULES: tuple[str, ...] = (
        "workstream_context.js",
        "workstream_annotations.js",
    )
    _ONTOBDC_VIEW_ONTOLOGIES: tuple[str, ...] = (
        "file_display.ttl",
        "enrichment_annotation.ttl",
        "enrichment_annotation_facade.ttl",
        "visual_representation_type.ttl",
        "visual_representation_type_facade.ttl",
    )

    def render(
        self,
        project_data: Dict[str, Any],
        element_id: str,
    ) -> Path:
        container_path = Path(
            str(project_data["path"])
        ).expanduser().resolve()
        output_dir = container_path / "payload" / "view"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{element_id}.html"
        asset_output_dir = (
            container_path
            / self._ONTOBDC_DIR_NAME
            / self._ASSET_ROOT_NAME
            / self._ASSET_NAMESPACE
        )
        asset_output_dir.mkdir(parents=True, exist_ok=True)

        self._copy_asset_directory(asset_output_dir)
        self._copy_ontobdc_view_assets(asset_output_dir)
        output_file.write_text(
            self._build_workstream_document(project_data, element_id),
            encoding="utf-8",
        )
        webbrowser.open(output_file.as_uri())
        return output_file

    def _build_workstream_document(
        self,
        project_data: Dict[str, Any],
        element_id: str,
    ) -> str:
        template = self._template_environment().get_template(
            "workstream_5w2h.html.j2"
        )
        work_stream_context = WorkStreamContext(element_id)
        payload = {
            "projectId": str(project_data.get("project_id", "")).strip(),
            "projectName": str(project_data.get("name", "")).strip(),
            "elementId": element_id,
            "entity": "WorkStream",
            **work_stream_context.as_payload(),
            "annotationRuntime": self._annotation_runtime_configuration(),
            "datapackagePath": ".__ontobdc__/datapackage.json",
            "linksetPath": ".__ontobdc__/linkset/WorkStream.ttl",
            "resourceLinksetPath": (
                ".__ontobdc__/linkset/WorkStreamResource.ttl"
            ),
            "roCratePath": ".__ontobdc__/ro-crate-metadata.json",
            "fileDisplayOntologyPath": (
                ".__ontobdc__/asset/infobim-view/ontology/"
                "file_display.ttl"
            ),
        }
        return template.render(
            page_title="InfoBIM WorkStream 5W2H",
            asset_root="../../.__ontobdc__/asset/infobim-view",
            project_title=payload["projectName"],
            workstream_payload_json=json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
            ),
        )

    @staticmethod
    def _annotation_runtime_configuration() -> Dict[str, Any]:
        return {
            "prefix": "workstream",
            "bodyOpenClass": "has-annotation-dialog",
            "store": {
                "datasetFileName": "EnrichmentAnnotation.ttl",
                "defaultColor": "#67e8f9",
            },
            "surface": {
                "imageAlt": "Representação anotável",
                "imageLoadError": "Não foi possível carregar a imagem.",
                "unsupportedError": (
                    "Este formato ainda não possui representação anotável."
                ),
            },
            "labels": {
                "note": "Nota",
                "emptyNote": "Nota sem texto.",
                "showNote": "Exibir nota: ",
                "closeNote": "Fechar nota",
                "previewUnavailable": (
                    "A área de visualização não está disponível."
                ),
                "openCancelled": (
                    "A abertura da anotação foi cancelada."
                ),
                "application": "InfoBIM Annotation",
                "resource": "Arquivo",
                "dialog": "Anotar arquivo",
                "close": "Fechar",
                "instructions": (
                    "Clique na imagem para marcar um ou mais pontos "
                    "da mesma nota."
                ),
                "placeholder": "Escreva a nota...",
                "text": "Texto da nota",
                "color": "Cor",
                "category": "Categoria",
                "newAnnotation": "Nova anotação",
                "delete": "Excluir",
                "save": "Salvar",
                "invalidGeometry": (
                    "A geometria selecionada não é válida para esta categoria."
                ),
                "categoryLabels": {
                    "NoteAnnotation": "Nota",
                    "IssueAnnotation": "Issue",
                    "ClassificationAnnotation": "Classificação",
                    "LocationAnnotation": "Localização",
                    "RecordAnnotation": "Registro",
                },
                "toolLabels": {
                    "select": "Selecionar",
                    "point": "Ponto",
                    "multiple-points": "Vários pontos",
                    "bounding-box": "Caixa delimitadora",
                    "clear": "Limpar geometria",
                },
                "fieldLabels": {
                    "body": "Texto",
                    "markerColor": "Cor do marcador",
                    "issueKind": "Tipo de issue",
                    "issueStatus": "Estado da issue",
                    "resolution": "Resolução",
                    "resolvedAt": "Resolvido em",
                    "classifiedAs": "Classificado como",
                    "classificationLabel": "Rótulo da classificação",
                    "locationKind": "Tipo de localização",
                    "latitude": "Latitude",
                    "longitude": "Longitude",
                    "altitude": "Altitude",
                    "coordinateReferenceSystem": "Sistema de referência",
                    "relativeTo": "Relativo a",
                    "spatialRelation": "Relação espacial",
                    "recordResource": "Recurso registrado",
                    "recordKind": "Tipo de registro",
                    "recordedAt": "Registrado em",
                    "recordedBy": "Registrado por",
                    "evidenceFor": "Evidência para",
                    "subjects": "Assuntos (URIs separadas por vírgula)",
                    "assignedTo": "Atribuído a (URIs separadas por vírgula)",
                    "resolvedBy": "Resolvido por",
                },
                "valueLabels": {
                    "Problem": "Problema",
                    "Question": "Pergunta",
                    "Open": "Aberta",
                    "InProgress": "Em andamento",
                    "Resolved": "Resolvida",
                    "Closed": "Fechada",
                    "GeospatialLocation": "Geoespacial",
                    "PositionalLocation": "Posicional",
                    "RelativeLocation": "Relativa",
                    "RepresentationLocation": "Na representação",
                    "Inside": "Dentro",
                    "Above": "Acima",
                    "Below": "Abaixo",
                    "Near": "Próximo",
                    "AdjacentTo": "Adjacente",
                    "Between": "Entre",
                    "PhotoRecord": "Fotografia",
                    "VideoRecord": "Vídeo",
                    "AudioRecord": "Áudio",
                    "InvoiceRecord": "Nota fiscal",
                    "DocumentRecord": "Documento",
                    "MeasurementRecord": "Medição",
                    "GenericRecord": "Registro genérico",
                },
            },
        }

    def _ontobdc_view_dir(self) -> Path:
        loader_spec = find_spec("ontobdc.view.adapter.loader")
        if loader_spec is None or loader_spec.origin is None:
            raise FileNotFoundError(
                "Could not locate the installed OntoBDC package."
            )
        return Path(loader_spec.origin).resolve().parents[1]

    def _copy_ontobdc_view_assets(
        self,
        asset_output_dir: Path,
    ) -> None:
        ontobdc_view_dir = self._ontobdc_view_dir()
        ontology_source_dir = ontobdc_view_dir / "plugin" / "ontology"
        annotation_source_dir = (
            ontobdc_view_dir
            / "plugin"
            / "asset"
            / "js"
            / "annotation"
        )
        annotation_style_source_dir = (
            ontobdc_view_dir
            / "plugin"
            / "asset"
            / "css"
        )
        work_stream_source_dir = (
            ontobdc_view_dir
            / "plugin"
            / "asset"
            / "js"
            / "workstream"
        )

        sources: list[tuple[Path, Path]] = []
        sources.extend(
            (
                ontology_source_dir / file_name,
                asset_output_dir / "ontology" / file_name,
            )
            for file_name in self._ONTOBDC_VIEW_ONTOLOGIES
        )
        sources.extend(
            (
                annotation_source_dir / file_name,
                asset_output_dir
                / "js"
                / "ontobdc"
                / "annotation"
                / file_name,
            )
            for file_name in self._ONTOBDC_ANNOTATION_MODULES
        )
        sources.extend(
            (
                annotation_style_source_dir / file_name,
                asset_output_dir
                / "css"
                / "ontobdc"
                / "annotation"
                / file_name,
            )
            for file_name in self._ONTOBDC_ANNOTATION_STYLES
        )
        sources.extend(
            (
                work_stream_source_dir / file_name,
                asset_output_dir
                / "js"
                / "ontobdc"
                / "workstream"
                / file_name,
            )
            for file_name in self._ONTOBDC_WORKSTREAM_MODULES
        )

        for source_path, target_path in sources:
            if not source_path.is_file():
                raise FileNotFoundError(
                    f"OntoBDC view asset was not found: {source_path}"
                )
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
