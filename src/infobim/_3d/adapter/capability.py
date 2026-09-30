from typing import ClassVar

from infobim.shared.adapter.capability import PrivatePackageCapabilityLoader


class ThreeDCapabilityLoader(PrivatePackageCapabilityLoader):
    """
    Discover capabilities implemented inside the private ``infobim._3d``
    package.

    ``_3d`` is hidden like ``_2d``: the 3D stack is an optional extra, off
    unless PySide6 is installed, so its capabilities are imported from
    ``infobim._3d.plugin.capability`` directly.
    """

    CAPABILITY_PACKAGE: ClassVar[str] = "infobim._3d.plugin.capability"
