PROJECT_DATASET_NAME = ".__infobim__"
PROJECT_WORKBOOK_NAME = "IfcProject.xlsx"
PROJECT_WORKSHEET_NAME = "IfcProject"

INFOBIM_NS = "https://infobim.org/ontology/ns#"
IFCOWL_NS = "https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#"

IFC_PROJECT_CLASS_URI = f"{IFCOWL_NS}IfcProject"
IFC_PROJECT_FACADE_URI = f"{INFOBIM_NS}IfcProjectFacade"

IFC_PROJECT_FIELDS = (
    ("GlobalId", "globalId_IfcRoot"),
    ("Name", "name_IfcRoot"),
    ("Description", "description_IfcRoot"),
    ("LongName", "longName_IfcContext"),
    ("Phase", "phase_IfcContext"),
)
