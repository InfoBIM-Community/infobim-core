from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_DEFAULT_A3_SUGGESTION_SUBDIR: str = "a3_suggestions"
_STATE_ARTIFACT_BASENAME: str = "llm_file_suggestions.json"


def _artifact_directory(container_path: Path) -> Path:
    return (
        container_path.expanduser().resolve()
        / ".__ontobdc__"
        / _DEFAULT_A3_SUGGESTION_SUBDIR
    )


def state_artifact_path(container_path: Path) -> Path:
    return _artifact_directory(container_path) / _STATE_ARTIFACT_BASENAME


def ensure_state_directory(container_path: Path) -> Path:
    directory: Path = _artifact_directory(container_path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def suggestion_index_directory(container_path: Path) -> Path:
    return ensure_state_directory(container_path)


def build_suggestion_record(
    *,
    relative_path: str,
    element_id: str,
    dimension_property: str,
    file_metadata: Dict[str, Any],
    accepted: bool,
    confidence: Optional[float],
    rationale: str,
    model: str,
) -> Dict[str, Any]:
    return {
        "relative_path": str(relative_path),
        "element_id": str(element_id),
        "dimension_property": str(dimension_property),
        "accepted": bool(accepted),
        "confidence": (float(confidence) if confidence is not None else None),
        "rationale": str(rationale),
        "model": str(model),
        "file_metadata": dict(file_metadata or {}),
    }


def suggestion_key(element_id: str, dimension_property: str) -> Tuple[str, str]:
    return (str(element_id), str(dimension_property))


def build_llm_prompt(
    *,
    element_id: str,
    dimension_property: str,
    file_relative_path: str,
    file_metadata: Dict[str, Any],
    file_snippet: str,
) -> str:
    joined: List[str] = [
        "You are an A3 dimensional-analysis assistant for BIM projects.",
        "Decide whether the provided document is a good evidence source to",
        "suggest or validate a specific dimension-property for a specific BIM element.",
        "",
        "INPUT:",
        f"- Element GlobalId: {element_id}",
        f"- Target dimension property: {dimension_property}",
        f"- File: {file_relative_path}",
        f"- File metadata: {dict(file_metadata or {})}",
        "",
        "DOCUMENT SNIPPET (first bytes; may be partial):",
        "---BEGIN DOCUMENT SNIPPET---",
        str(file_snippet or "").strip(),
        "---END DOCUMENT SNIPPET---",
        "",
        "ANSWER strictly with a JSON object and nothing else:",
        "{",
        '  "accepted": boolean,',
        '  "confidence": number between 0.0 and 1.0,',
        '  "rationale": short one-paragraph string in Portuguese explaining why the file is accepted or rejected,',
        '  "dimension_hints": [optional list of dimension names mentioned that are related to the target]',
        "}",
    ]
    return "\n".join(joined)
