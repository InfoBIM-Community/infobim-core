from abc import ABC, abstractmethod
from typing import Dict, List


class DxfViewerSessionPort(ABC):
    """
    One visual session of the InfoBIM 2D viewer.

    The session is opened once and can then either run as a plain viewer
    until it is closed, or capture points on the same window.
    """

    @property
    @abstractmethod
    def current_state(self) -> str:
        """Return the drawing state shown by the selected tab."""
        ...

    @abstractmethod
    def show(self) -> None:
        """Show the window without blocking."""
        ...

    @abstractmethod
    def run(self) -> str:
        """Block until the window is closed and return the selected state."""
        ...

    @abstractmethod
    def capture_points(self) -> List[Dict[str, float]]:
        """
        Block while the user picks points and return them in click order.

        A left click adds a point, Backspace or Delete removes the last one
        and a left double click adds a last point and finishes the capture.
        """
        ...

    @abstractmethod
    def request_annotation_details(self) -> Dict[str, str]:
        """
        Block while the user fills in the details of an annotation on the
        open window, and return them by key: ``title`` always, ``text`` and
        ``author`` when filled in.

        Raises:
            RuntimeError: the user cancelled the form.
        """
        ...

    @abstractmethod
    def close(self) -> None:
        """Release the window."""
        ...
