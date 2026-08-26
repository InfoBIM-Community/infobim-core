"""Repositories for IFC geometric-representation context lookup.

Any capability that inserts geometry into an existing IFC file needs to
anchor that geometry against an ``IfcGeometricRepresentationSubContext``
whose ``ContextIdentifier`` matches the representation type being written
(``Body`` for real swept solid geometry, ``Annotation`` for labels/
callouts, etc.). This adapter centralises those lookups so capabilities
do not each re-implement the same 8-line scan.
"""

from typing import Any


class RepresentationContextRepository:
    """Resolve representation sub-contexts by their canonical identifier."""

    def __init__(self, model: Any) -> None:
        self._model = model

    def get(self, identifier: str) -> Any:
        """Return the first ``IfcGeometricRepresentationSubContext`` whose
        ``ContextIdentifier`` equals ``identifier`` (case-sensitive)."""
        candidates = [
            ctx for ctx in self._model.by_type("IfcGeometricRepresentationSubContext")
            if getattr(ctx, "ContextIdentifier", None) == identifier
        ]
        if not candidates:
            raise ValueError(
                f"No '{identifier}' IfcGeometricRepresentationSubContext found in the IFC file."
            )
        return candidates[0]

    def get_case_insensitive(self, identifier: str, fallback: Any) -> Any:
        """Match ``ContextIdentifier`` case-insensitively; return ``fallback`` when absent."""
        key = str(identifier).lower()
        candidates = [
            ctx for ctx in self._model.by_type("IfcGeometricRepresentationSubContext")
            if str(getattr(ctx, "ContextIdentifier", "")).lower() == key
        ]
        return candidates[0] if candidates else fallback

    def get_body(self) -> Any:
        """Shorthand for :meth:`get` on the canonical Body context."""
        return self.get("Body")

    def get_annotation(self, fallback: Any) -> Any:
        """Shorthand for :meth:`get_case_insensitive` on the Annotation context."""
        return self.get_case_insensitive("Annotation", fallback)
