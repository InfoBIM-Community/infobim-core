class DrawingRepairError(Exception):
    """
    Base of every failure a drawing repair hotfix reports by itself.

    A hotfix that cannot repair what it was asked to raises its own
    error once every source it knows to recover from is exhausted,
    instead of returning quietly -- the caller must see that the data
    itself is gone, not mistake a returned failure code for "try again
    later".
    """


class IfcxTitleUnrecoverableError(DrawingRepairError):
    """
    The drawing's own linkset carries no name_IfcRoot yet.

    An IFCX file's title is is_drawing_linked_to_project's
    name_IfcRoot -- the DXF document's own ct:filename, stem only --
    copied from the drawing's linkset rather than re-derived here. When
    the linkset does not carry it yet (its own hotfix has not repaired
    that linkset), there is nothing to copy, and no title is invented
    in its place.
    """


class IfcxGlobalIdUnrecoverableError(DrawingRepairError):
    """
    The drawing's own linkset carries no globalId_IfcRoot yet.

    An IFCX file's infobim::globalId is is_drawing_linked_to_project's
    globalId_IfcRoot, copied from the drawing's linkset rather than
    generated here: that check/hotfix is what generates the fresh IFC
    GlobalId for this drawing. When the linkset does not carry it yet
    (its own hotfix has not repaired that linkset), there is nothing to
    copy, and none is invented in its place.
    """


class DrawingDwgLinkUnrecoverableError(DrawingRepairError):
    """
    A DXF's source DWG cannot be located to link the two.

    A DXF/IFCX linkset never records the DWG a DXF was itself converted
    from -- that is a separate linkset, DwgDxfLinksetWriter's, written
    only while the DWG-to-DXF conversion still has both files to write
    it from. Recovering the link means finding, by content hash, the
    real DWG file the cached DXF this document identifies was
    converted from -- first in the Project's own tree, then in its
    RO-Crate. When no DWG file matches by hash in either place, the
    source DWG is not recoverable, and none is invented in its place.
    """
