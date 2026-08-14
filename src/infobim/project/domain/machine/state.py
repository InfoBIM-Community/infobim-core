from enum import Enum
from typing import Any, Dict


class ProjectCreateProcessState(Enum):
    """States for creating an InfoBIM project over an OntoBDC container."""

    UNDEFINED = "__undefined__"
    INVALID_PATH = "__invalid_path__"
    ONTOBDC_CONTAINER_READY = "__ontobdc_container_ready__"
    PROJECT_DATASET_READY = "__project_dataset_ready__"
    IFC_PROJECT_FACADE_READY = "__ifc_project_facade_ready__"
    IFC_PROJECT_READY = "__ifc_project_ready__"
    PROJECT_READY = "__project_ready__"

    def label(self, lang: str = "en") -> str:
        labels: Dict[str, Dict[Any, str]] = {
            "en": {
                self.UNDEFINED: "Undefined",
                self.INVALID_PATH: "Invalid Path",
                self.ONTOBDC_CONTAINER_READY: "OntoBDC Container Ready",
                self.PROJECT_DATASET_READY: "Project Dataset Ready",
                self.IFC_PROJECT_FACADE_READY: "IfcProject Facade Ready",
                self.IFC_PROJECT_READY: "IfcProject Ready",
                self.PROJECT_READY: "Project Ready",
            },
            "pt-br": {
                self.UNDEFINED: "Indefinido",
                self.INVALID_PATH: "Caminho inválido",
                self.ONTOBDC_CONTAINER_READY: "Container OntoBDC pronto",
                self.PROJECT_DATASET_READY: "Dataset de projeto pronto",
                self.IFC_PROJECT_FACADE_READY: "Facade de IfcProject pronta",
                self.IFC_PROJECT_READY: "IfcProject pronto",
                self.PROJECT_READY: "Projeto pronto",
            },
        }
        return labels.get(lang, labels["en"]).get(self, self.value)

    def description(self, lang: str = "en") -> str:
        descriptions: Dict[str, Dict[Any, str]] = {
            "en": {
                self.UNDEFINED: "Initial state before the target path is classified.",
                self.INVALID_PATH: "The target path cannot become an InfoBIM project.",
                self.ONTOBDC_CONTAINER_READY: "The target path is a ready OntoBDC container.",
                self.PROJECT_DATASET_READY: "The container contains the reserved .__infobim__ EntityDataset.",
                self.IFC_PROJECT_FACADE_READY: "The project dataset contains the InfoBIM facade for ifcOWL:IfcProject.",
                self.IFC_PROJECT_READY: "The project dataset contains one editable IfcProject instance backed by an XLSX resource.",
                self.PROJECT_READY: "The OntoBDC container satisfies the complete InfoBIM project contract.",
            },
            "pt-br": {
                self.UNDEFINED: "Estado inicial antes da classificação do caminho alvo.",
                self.INVALID_PATH: "O caminho alvo não pode se tornar um projeto InfoBIM.",
                self.ONTOBDC_CONTAINER_READY: "O caminho alvo é um container OntoBDC pronto.",
                self.PROJECT_DATASET_READY: "O container contém o EntityDataset reservado .__infobim__.",
                self.IFC_PROJECT_FACADE_READY: "O dataset de projeto contém a facade InfoBIM para ifcOWL:IfcProject.",
                self.IFC_PROJECT_READY: "O dataset de projeto contém uma instância editável de IfcProject apoiada por XLSX.",
                self.PROJECT_READY: "O container OntoBDC satisfaz o contrato completo de projeto InfoBIM.",
            },
        }
        return descriptions.get(lang, descriptions["en"]).get(self, "")

    @staticmethod
    def get_state(state: str) -> "ProjectCreateProcessState":
        return getattr(ProjectCreateProcessState, state.upper())
