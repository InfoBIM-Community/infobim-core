from typing import ClassVar, List, Optional
from array import array

from PySide6.QtGui import QVector3D
from PySide6.QtCore import Property, QByteArray
from PySide6.QtQuick3D import QQuick3DGeometry


class IfcElementGeometry(QQuick3DGeometry):
    """
    Triangulated Qt Quick 3D geometry of one IFC element.

    The geometry keeps the identity of the element it draws (GlobalId,
    Name and IFC type), so a Model picked in the scene leads back to the
    IFC element. Vertices are packed as float32 ``x, y, z`` triples,
    optionally followed by float32 normals, and indices as uint32 triangle
    corners, the same buffers a later serializer can read back.
    """

    POSITION_SIZE: ClassVar[int] = 3 * 4
    NORMAL_SIZE: ClassVar[int] = 3 * 4

    def __init__(
        self,
        global_id: str,
        name: str,
        ifc_type: str,
        vertices: List[float],
        indices: List[int],
        normals: Optional[List[float]] = None,
    ) -> None:
        super().__init__()
        if len(vertices) % 3 != 0 or len(indices) % 3 != 0:
            raise ValueError(
                f"IFC element {global_id} has vertices or indices that are not "
                "triangles of 3D points."
            )
        if normals is not None and len(normals) != len(vertices):
            raise ValueError(
                f"IFC element {global_id} has {len(normals)} normal components "
                f"for {len(vertices)} vertex components."
            )

        self._global_id: str = global_id
        self._name: str = name
        self._ifc_type: str = ifc_type
        self._has_normals: bool = normals is not None
        self._build(vertices, indices, normals)

    def _get_global_id(self) -> str:
        return self._global_id

    def _get_name(self) -> str:
        return self._name

    def _get_ifc_type(self) -> str:
        return self._ifc_type

    def _get_has_normals(self) -> bool:
        return self._has_normals

    globalId = Property(str, _get_global_id, constant=True)
    elementName = Property(str, _get_name, constant=True)
    ifcType = Property(str, _get_ifc_type, constant=True)
    hasNormals = Property(bool, _get_has_normals, constant=True)

    def _build(
        self,
        vertices: List[float],
        indices: List[int],
        normals: Optional[List[float]],
    ) -> None:
        stride: int = self.POSITION_SIZE
        interleaved: List[float] = list(vertices)
        if normals is not None:
            stride += self.NORMAL_SIZE
            interleaved = []
            offset: int
            for offset in range(0, len(vertices), 3):
                interleaved.extend(vertices[offset:offset + 3])
                interleaved.extend(normals[offset:offset + 3])

        self.setVertexData(QByteArray(array("f", interleaved).tobytes()))
        self.setIndexData(QByteArray(array("I", indices).tobytes()))
        self.setStride(stride)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.addAttribute(
            QQuick3DGeometry.Attribute.Semantic.PositionSemantic,
            0,
            QQuick3DGeometry.Attribute.ComponentType.F32Type,
        )
        if normals is not None:
            self.addAttribute(
                QQuick3DGeometry.Attribute.Semantic.NormalSemantic,
                self.POSITION_SIZE,
                QQuick3DGeometry.Attribute.ComponentType.F32Type,
            )
        self.addAttribute(
            QQuick3DGeometry.Attribute.Semantic.IndexSemantic,
            0,
            QQuick3DGeometry.Attribute.ComponentType.U32Type,
        )
        self.setBounds(
            QVector3D(min(vertices[0::3]), min(vertices[1::3]), min(vertices[2::3])),
            QVector3D(max(vertices[0::3]), max(vertices[1::3]), max(vertices[2::3])),
        )
