from typing import ClassVar


class ProjectContract:
    """
    What an OntoBDC container must carry to be an InfoBIM project.

    A project is a container plus one reserved dataset, and that dataset
    holds the IfcProject the whole model hangs from. The names below are the
    contract: change one and an existing project stops being recognised.
    """

    DATASET_NAME: ClassVar[str] = ".__infobim__"
    DATASET_TITLE: ClassVar[str] = "InfoBIM Project"
    PAYLOAD_DIRECTORY_NAME: ClassVar[str] = "payload"
    TRIPLE_DIRECTORY_NAME: ClassVar[str] = "triple"
    LINKSET_DIRECTORY_NAME: ClassVar[str] = "linkset"
    IFC_PROJECT_FILE_NAME: ClassVar[str] = "ifc_project.ttl"

    INFOBIM_NAMESPACE: ClassVar[str] = "https://infobim.org/ontology/ns#"

    # Schema dispatch uses the official buildingSMART release URI directly.
    # No parallel short schema identifier is part of the project contract.
    IFC_SCHEMA_URI_BASE: ClassVar[str] = (
        "https://standards.buildingsmart.org/IFC/RELEASE/"
    )
    DEFAULT_IFC_SCHEMA: ClassVar[str] = (
        "https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/"
    )

    # IFC RDF terms remain in the buildingSMART ifcOWL namespace. The schema
    # check resolves that vocabulary namespace to the official RELEASE URI
    # used for loader dispatch.
    IFCOWL_NAMESPACE_BASE: ClassVar[str] = (
        "https://standards.buildingsmart.org/IFC/DEV/"
    )
    IFCOWL_NAMESPACE: ClassVar[str] = (
        "https://standards.buildingsmart.org/IFC/DEV/IFC4_3/OWL#"
    )

    IFC_PROJECT_CLASS: ClassVar[str] = f"{IFCOWL_NAMESPACE}IfcProject"
    IFC_PROJECT_GLOBAL_ID_PROPERTY: ClassVar[str] = (
        f"{IFCOWL_NAMESPACE}globalId_IfcRoot"
    )
    IFC_PROJECT_NAME_PROPERTY: ClassVar[str] = f"{IFCOWL_NAMESPACE}name_IfcRoot"
