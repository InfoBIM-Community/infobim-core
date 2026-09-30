import io
import contextlib
from typing import Any, ClassVar, Dict, Tuple

from ezdxf.document import Drawing
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.cli.domain.exception.command import CliCommandArgumentException

from infobim._2d.domain.port.viewer import DxfViewerSessionPort


class DxfViewerDocuments:
    """Read the drawing states the 2D viewer can show from the context."""

    DOCUMENTS_KEY: ClassVar[str] = "dxf_documents"
    ORIGINAL_KEY: ClassVar[str] = "dxf_original"
    ANNOTATED_KEY: ClassVar[str] = "dxf_annotated"
    SUGGESTED_KEY: ClassVar[str] = "dxf_suggested"

    STATES: ClassVar[Tuple[Tuple[str, str, str], ...]] = (
        ("original", "Original", ORIGINAL_KEY),
        ("annotated", "Notes", ANNOTATED_KEY),
        ("suggested", "Suggestions", SUGGESTED_KEY),
    )

    @classmethod
    def from_context(cls, context: CliContextPort) -> Dict[str, Drawing]:
        documents_by_key: Any = context.get_parameter_value(cls.DOCUMENTS_KEY)
        if not isinstance(documents_by_key, dict):
            raise CliCommandArgumentException(
                f"Context parameter '{cls.DOCUMENTS_KEY}' must be a dictionary "
                "of ezdxf Drawings."
            )

        documents: Dict[str, Drawing] = {}

        state: str
        key: str
        for state, _label, key in cls.STATES:
            if key not in documents_by_key:
                continue
            document: Any = documents_by_key[key]
            if not isinstance(document, Drawing):
                raise CliCommandArgumentException(
                    f"'{cls.DOCUMENTS_KEY}' entry '{key}' is not an ezdxf Drawing."
                )
            documents[state] = document

        if "original" not in documents:
            raise CliCommandArgumentException(
                f"'{cls.DOCUMENTS_KEY}' entry '{cls.ORIGINAL_KEY}' is required."
            )

        return documents


class DxfViewerSessionFactory:
    """
    Open a 2D viewer session.

    The Qt implementation is imported only here, so the 2D capabilities can
    be discovered without a Qt binding and fail with a clear message when
    a viewer is actually needed. Importing ezdxf's Qt binding prints which
    binding it chose; that notice is kept off standard output, which
    belongs to the command's response.
    """

    @staticmethod
    def open(documents: Dict[str, Drawing]) -> DxfViewerSessionPort:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                from infobim._2d.adapter.qt_viewer import DxfViewerSession
        except ImportError as error:
            raise RuntimeError(
                "InfoBIM DXF viewer requires PySide6 (or PyQt5). "
                "Reinstall InfoBIM with its current dependencies."
            ) from error

        return DxfViewerSession(documents, DxfViewerDocuments.STATES)
