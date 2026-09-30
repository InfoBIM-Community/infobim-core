from typing import ClassVar, Tuple

PARAMETER_KEY: ClassVar[str] = "element_kind"
REPRESENTATION_PARAMETER_KEY: ClassVar[str] = "element_kind_representation"
CONTAINER_PATH_KEY: ClassVar[str] = "container_path"
DXF_PATH_KEY: ClassVar[str] = "dxf_path"
KIND_STATE: ClassVar[str] = "__element_kind_resolved__"
REPRESENTATION_STATE: ClassVar[str] = "__element_representation_resolved__"
ONTOLOGY_FILES: ClassVar[Tuple[str, ...]] = ("kind.ttl", "kind_representation.ttl")
ETL_SEGMENTS: ClassVar[Tuple[str, ...]] = ("etl", "context", "transformation", "document")
CAPABILITY_PREFIX: ClassVar[str] = "org.infobim.context.plugin.capability.transformation.target."
MACHINE_PACKAGE: ClassVar[str] = "infobim.2d.plugin.machine.element_creation_from_vector"
MACHINE_FILE: ClassVar[str] = "standard_element_creation_from_vector.yaml"
WORK_PLANE_Z_KEY: ClassVar[str] = "z"
PIPE_RADIUS_KEY: ClassVar[str] = "radius"
VECTOR_TRACE_KEY: ClassVar[str] = "vector_trace"
IFC_ELEMENTS_KEY: ClassVar[str] = "ifc_elements"
