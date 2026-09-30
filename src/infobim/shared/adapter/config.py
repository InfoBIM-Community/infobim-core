from typing import Any, Optional

from importlib.util import find_spec

from ontobdc.shared.adapter.config import ConfigDataAdapter as OntobdcConfigDataAdapter


class InfoBIMConfigDataAdapter(OntobdcConfigDataAdapter):
    """
    InfoBIM-specific extension of the ontobdc shared ConfigDataAdapter.

    Single Responsibility: this subclass only adds the InfoBIM-specific
    optional-dependency feature probes (``is_2d_installed`` and any
    future ones). All generic config behaviour (project root discovery,
    ``__ontobdc__/config.yaml`` loading, language selection, the
    ``is_a3_installed`` probe for the shared ``ontobdc-a3`` package,
    etc.) is inherited unchanged from the ontobdc base adapter, so we
    keep one single source of truth for shared behaviour.
    """

    def __init__(self, root_dir: Optional[str] = None) -> None:
        super().__init__(root_dir=root_dir)

    @staticmethod
    def is_2d_installed() -> bool:
        """
        Return ``True`` when the optional InfoBIM ``2d`` extra, which
        brings the heavy Qt-backed DXF viewer stack (``PySide6``), is
        importable in the current environment.

        The ``PySide6`` wheel carries the full Qt binary payload, so it
        is shipped as a PEP-621 ``[project.optional-dependencies]``
        group named ``2d`` and is **never** part of the base InfoBIM
        install. Features that actually open the interactive Qt DXF
        preview widget (the legacy commands that import
        ``from ezdxf.addons.xqt import QtWidgets``) **must** guard on
        this check before they try to import anything from that
        stack.
        """
        try:
            return find_spec("PySide6") is not None
        except (AttributeError, ImportError, ValueError):
            return False
