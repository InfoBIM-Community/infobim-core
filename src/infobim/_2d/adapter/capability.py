from typing import ClassVar

from infobim.shared.adapter.capability import PrivatePackageCapabilityLoader


class TwoDCapabilityLoader(PrivatePackageCapabilityLoader):
    """
    Discover capabilities implemented inside the private ``infobim._2d``
    package.

    Mirrors :class:`~infobim._2d.adapter.command.TwoDCommandLoader`: ``_2d``
    is deliberately hidden — the 2D stack is an optional extra, off unless
    PySide6 is installed — so its capabilities are imported from
    ``infobim._2d.plugin.capability`` directly.
    """

    CAPABILITY_PACKAGE: ClassVar[str] = "infobim._2d.plugin.capability"
