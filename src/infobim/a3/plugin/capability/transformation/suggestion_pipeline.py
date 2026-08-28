import json
import os
import re as _re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from ontobdc.a3.domain.model.language import A3SupportedLanguages
from ontobdc.cli.domain.port.context import CliContextPort
from ontobdc.shared.domain.model.capability import CapabilityMetadata
from ontobdc.shared.domain.port.capability import TransactionCapabilityPort
from ontobdc.storage.adapter.bootstrap import (
    StorageBootstrap,
    StoragePathStatHelper,
)
from ontobdc.storage.adapter.manifest import ContainerDataPackageSynchronizer

from infobim.a3.domain.model.suggestion import (
    build_llm_prompt,
    build_suggestion_record,
    state_artifact_path,
    suggestion_index_directory,
    suggestion_key,
)
from infobim.a3.domain.machine.state import A3LlmSuggestionProcessState
from infobim.project.plugin.capability.base import ProjectTransactionCapability


_A3_STATE_PARAM: str = "a3_suggestion_state"
_A3_RO_CRATE_PARAM: str = "a3_ro_crate_payload"
_A3_FILES_PARAM: str = "a3_enriched_files"
_A3_LLM_RESULTS_PARAM: str = "a3_llm_evaluation_results"


def _bound_context(context: CliContextPort) -> Dict[str, Any]:
    container_path: Path = Path(
        str(context.get_parameter_value("container_path"))
    ).expanduser().resolve()
    element_id: str = str(context.get_parameter_value("target_element_id")).strip()
    dimension: str = str(
        context.get_parameter_value("target_dimension_property")
    ).strip()
    if not container_path.is_dir():
        raise ValueError(
            f"A3 LLM suggestion: container_path is not a directory: {container_path}"
        )
    if not element_id:
        raise ValueError("A3 LLM suggestion: target_element_id is empty")
    if not dimension:
        raise ValueError(
            "A3 LLM suggestion: target_dimension_property is empty"
        )
    return {
        "container_path": container_path,
        "element_id": element_id,
        "dimension": dimension,
    }


def _state_payload(context: CliContextPort) -> Dict[str, Any]:
    existing: Any = context.get_parameter_value(_A3_STATE_PARAM)
    if isinstance(existing, dict):
        return existing
    return {}


def _write_state(context: CliContextPort, state: Dict[str, Any]) -> None:
    bound = _bound_context(context)
    container_path: Path = bound["container_path"]
    suggestion_index_directory(container_path)
    artifact: Path = state_artifact_path(container_path)
    payload: Dict[str, Any] = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **state,
    }
    artifact.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    context.set_parameter_value(_A3_STATE_PARAM, payload)


class A3BaseCapability(ProjectTransactionCapability):
    """Shared base for InfoBIM A3 LLM suggestion capabilities.

    Concrete subclasses declare their own :data:`METADATA` and implement
    :meth:`_transition_body`; this base handles the ``label``/``description``
    presentation (reusing the state enum), boilerplate parameter binding and
    the state-artifact write contract so every capability writes a
    machine-readable checkpoint under ``.__ontobdc__/a3_suggestions/``.
    """

    TARGET_STATE: ClassVar[A3LlmSuggestionProcessState]

    def label(self, lang: str = "en") -> str:
        return self.TARGET_STATE.label(lang)

    def description(self, lang: str = "en") -> str:
        return self.TARGET_STATE.description(lang)

    def execute(self, context: CliContextPort) -> Dict[str, Any]:
        result: Dict[str, Any] = self._transition_body(context)
        state: Dict[str, Any] = dict(_state_payload(context))
        state.setdefault("visited_states", []).append(self.TARGET_STATE.value)
        state.setdefault("capability_results", {})[
            self.TARGET_STATE.value
        ] = {
            "capability_id": self.METADATA.id,
            "result": result,
        }
        state["current_state"] = self.TARGET_STATE.value
        _write_state(context, state)
        return {
            "resulting_state": self.TARGET_STATE,
            "state_artifact": str(
                state_artifact_path(_bound_context(context)["container_path"])
            ),
            **result,
        }

    def _transition_body(self, context: CliContextPort) -> Dict[str, Any]:
        raise NotImplementedError(
            f"{type(self).__name__} must implement _transition_body(context)."
        )


class A3ContainerBoundCapability(A3BaseCapability):
    TARGET_STATE = A3LlmSuggestionProcessState.CONTAINER_BOUND
    METADATA = CapabilityMetadata(
        id="org.infobim.a3.plugin.capability.transformation.target.container_bound",
        version="1.0.0",
        name="A3 Container Bound",
        description=(
            "Bind the requested --project, --element and --suggest values to "
            "the CLI context as a container path, target BIM element GlobalId "
            "and target dimension-property token, respectively."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "a3", "llm", "container", "binding"],
        supported_languages=A3SupportedLanguages.list(),
        log_message={
            "info": {
                "en": "A3 container, element and dimension-property were bound to the CLI context.",
            },
            "debug_entry": {
                "en": "Binding A3 container, element and dimension-property to the CLI context.",
            },
        },
    )

    def _transition_body(self, context: CliContextPort) -> Dict[str, Any]:
        bound = _bound_context(context)
        container_path: Path = bound["container_path"]
        element_id: str = bound["element_id"]
        dimension: str = bound["dimension"]
        return {
            "container_path": str(container_path),
            "target_element_id": element_id,
            "target_dimension_property": dimension,
        }


class A3RoCrateLoadedCapability(A3BaseCapability):
    TARGET_STATE = A3LlmSuggestionProcessState.RO_CRATE_LOADED
    METADATA = CapabilityMetadata(
        id="org.infobim.a3.plugin.capability.transformation.target.ro_crate_loaded",
        version="1.0.0",
        name="A3 RO-Crate Loaded",
        description=(
            "Load and validate the container RO-Crate manifest "
            "(.__ontobdc__/ro-crate-metadata.json): dataset node, @graph and "
            "hasPart list must all be internally consistent and "
            "recoverable."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "a3", "ro-crate", "manifest"],
        supported_languages=A3SupportedLanguages.list(),
        log_message={
            "info": {
                "en": "A3 container RO-Crate manifest was loaded and validated.",
            },
            "debug_entry": {
                "en": "Loading and validating the A3 container RO-Crate manifest.",
            },
        },
    )

    def _transition_body(self, context: CliContextPort) -> Dict[str, Any]:
        bound = _bound_context(context)
        container_path: Path = bound["container_path"]
        crate_file: Path = StorageBootstrap.get_container_crate_metadata_file_path(
            container_path
        )
        if not crate_file.is_file():
            raise FileNotFoundError(
                "A3 RO-Crate manifest is missing: "
                f"{crate_file}. Run a container update first."
            )
        try:
            crate_data: Any = json.loads(
                crate_file.read_text(encoding="utf-8")
            )
        except Exception as exc:  # pragma: no cover - runtime guard
            raise ValueError(
                f"A3 RO-Crate manifest is not valid JSON: {crate_file}"
            ) from exc
        if not isinstance(crate_data, dict):
            raise ValueError(
                f"A3 RO-Crate manifest root is not a JSON object: {crate_file}"
            )
        graph: Any = crate_data.get("@graph")
        if not isinstance(graph, list):
            raise ValueError(
                f"A3 RO-Crate manifest missing @graph list: {crate_file}"
            )
        dataset_node: Optional[Dict[str, Any]] = None
        for node in graph:
            if isinstance(node, dict) and node.get("@id") == "./":
                dataset_node = node
                break
        if dataset_node is None:
            raise ValueError(
                f"A3 RO-Crate manifest missing dataset node (@id='./'): {crate_file}"
            )
        has_part: Any = dataset_node.get("hasPart")
        if has_part is not None and not isinstance(has_part, list):
            raise ValueError(
                f"A3 RO-Crate manifest dataset hasPart is not a list: {crate_file}"
            )
        payload: Dict[str, Any] = {
            "ro_crate_path": str(crate_file),
            "crate_data": crate_data,
            "dataset_node": dataset_node,
            "has_part_count": len(has_part) if isinstance(has_part, list) else 0,
            "graph_count": len(graph),
        }
        context.set_parameter_value(_A3_RO_CRATE_PARAM, payload)
        return payload


class A3FilesEnumeratedCapability(A3BaseCapability):
    TARGET_STATE = A3LlmSuggestionProcessState.FILES_ENUMERATED
    METADATA = CapabilityMetadata(
        id="org.infobim.a3.plugin.capability.transformation.target.files_enumerated",
        version="1.0.0",
        name="A3 Files Enumerated",
        description=(
            "Enumerate every file referenced by the RO-Crate manifest, "
            "cross-check with the on-disk listing and attach lightweight "
            "metadata (size, MIME type, RO-Crate file-node attributes) used "
            "by the subsequent LLM evaluation step."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "a3", "files", "enumeration"],
        supported_languages=A3SupportedLanguages.list(),
        log_message={
            "info": {
                "en": "A3 container files were enumerated and enriched with RO-Crate metadata.",
            },
            "debug_entry": {
                "en": "Enumerating A3 container files and attaching RO-Crate metadata.",
            },
        },
    )

    @staticmethod
    def _file_nodes_by_id(
        graph: List[Any],
    ) -> Dict[str, Dict[str, Any]]:
        normalized: Dict[str, Dict[str, Any]] = {}
        for node in graph:
            if not isinstance(node, dict):
                continue
            node_id: Any = node.get("@id")
            if not isinstance(node_id, str) or node_id in {
                "./",
                "ro-crate-metadata.json",
            }:
                continue
            node_type: Any = node.get("@type")
            is_file: bool = node_type == "File" or (
                isinstance(node_type, list) and "File" in node_type
            )
            if not is_file:
                continue
            clean_id: str = A3FilesEnumeratedCapability._normalize_id(node_id)
            if not clean_id:
                continue
            normalized[clean_id] = node
        return normalized

    @staticmethod
    def _normalize_id(raw: str) -> str:
        normalized: str = raw.strip()
        if normalized.startswith("./"):
            normalized = normalized[2:]
        return normalized

    def _transition_body(self, context: CliContextPort) -> Dict[str, Any]:
        bound = _bound_context(context)
        container_path: Path = bound["container_path"]
        crate_payload: Any = context.get_parameter_value(_A3_RO_CRATE_PARAM)
        if not isinstance(crate_payload, dict):
            raise ValueError(
                "A3 files enumerated requires a previous successful "
                "ro_crate_loaded payload."
            )
        crate_data: Any = crate_payload.get("crate_data")
        if not isinstance(crate_data, dict):
            raise ValueError(
                "A3 files enumerated: ro_crate_loaded payload has no crate_data."
            )
        graph: Any = crate_data.get("@graph")
        if not isinstance(graph, list):
            raise ValueError(
                "A3 files enumerated: ro_crate_loaded payload has no @graph."
            )

        relative_ids: List[str] = ContainerDataPackageSynchronizer.list_container_file_paths(
            container_path
        )
        file_nodes: Dict[str, Dict[str, Any]] = (
            A3FilesEnumeratedCapability._file_nodes_by_id(graph)
        )

        enriched: List[Dict[str, Any]] = []
        for relative_path in sorted(set(relative_ids)):
            absolute: Path = container_path / Path(relative_path)
            if not absolute.is_file():
                continue
            stat_result: Any = StoragePathStatHelper.safe_stat(absolute)
            size: int = 0
            if stat_result is not None and hasattr(stat_result, "st_size"):
                size = int(getattr(stat_result, "st_size") or 0)
            mime_type: str = str(
                (mimetypes_for_file(absolute) or ("application/octet-stream", None))[0]
                or "application/octet-stream"
            )
            record: Dict[str, Any] = {
                "relative_path": relative_path,
                "absolute_path": str(absolute),
                "size_bytes": size,
                "mime_type": mime_type,
                "extension": absolute.suffix.lower().lstrip("."),
                "ro_crate_node": file_nodes.get(relative_path, {}),
            }
            enriched.append(record)
        payload: Dict[str, Any] = {
            "file_count": len(enriched),
            "files": enriched,
        }
        context.set_parameter_value(_A3_FILES_PARAM, payload)
        return payload


class A3LlmEvaluatedCapability(A3BaseCapability):
    """Evaluate each enumerated file with Claude Haiku/Sonnet.

    The capability routes each file through a pluggable
    :class:`A3LlmEvaluationAdapter`, which by default uses the real
    Anthropic API (HAIKU → cheap for most files, SONNET → fallback for
    content-heavy / complex documents) **if** the environment is configured
    with an ``ANTHROPIC_API_KEY``. When the API is unavailable the adapter
    runs a deterministic local heuristic that mirrors the same JSON shape
    so the rest of the pipeline remains identical.

    Real Anthropic routing is the only LLM integration point.
    """

    TARGET_STATE = A3LlmSuggestionProcessState.LLM_EVALUATED
    METADATA = CapabilityMetadata(
        id="org.infobim.a3.plugin.capability.transformation.target.llm_evaluated",
        version="1.0.0",
        name="A3 LLM Evaluated",
        description=(
            "Run each enumerated file through Claude Haiku/Sonnet to decide "
            "whether the file is a useful evidence source for the target "
            "dimension-property on the target BIM element."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "a3", "llm", "claude", "haiku", "sonnet"],
        supported_languages=A3SupportedLanguages.list(),
        log_message={
            "info": {
                "en": "A3 files were evaluated through Claude Haiku/Sonnet.",
            },
            "debug_entry": {
                "en": "Evaluating A3 files through Claude Haiku/Sonnet.",
            },
        },
    )

    def _transition_body(self, context: CliContextPort) -> Dict[str, Any]:
        bound = _bound_context(context)
        container_path: Path = bound["container_path"]
        element_id: str = bound["element_id"]
        dimension: str = bound["dimension"]

        files_payload: Any = context.get_parameter_value(_A3_FILES_PARAM)
        if not isinstance(files_payload, dict):
            raise ValueError(
                "A3 LLM evaluated requires a previous successful "
                "files_enumerated payload."
            )
        files: Any = files_payload.get("files")
        if not isinstance(files, list):
            raise ValueError(
                "A3 LLM evaluated: files_enumerated payload has no files list."
            )

        adapter: A3LlmEvaluationAdapter = A3LlmEvaluationAdapter()
        accepted_results: List[Dict[str, Any]] = []
        rejected_results: List[Dict[str, Any]] = []
        evaluated: List[Dict[str, Any]] = []

        for index, file_record in enumerate(files):
            if not isinstance(file_record, dict):
                continue
            try:
                result: Dict[str, Any] = adapter.evaluate(
                    container_path=container_path,
                    element_id=element_id,
                    dimension_property=dimension,
                    file_record=file_record,
                    index=index,
                    total=len(files),
                )
            except Exception as exc:  # pragma: no cover - diagnostic channel
                result = {
                    "relative_path": str(
                        file_record.get("relative_path") or "<unknown>"
                    ),
                    "accepted": False,
                    "confidence": 0.0,
                    "rationale": (
                        "A3 LLM evaluation raised an exception for this "
                        f"file: {type(exc).__name__}: {exc}"
                    ),
                    "model": "error",
                    "dimension_hints": [],
                }
            result_record: Dict[str, Any] = build_suggestion_record(
                relative_path=result["relative_path"],
                element_id=element_id,
                dimension_property=dimension,
                file_metadata=file_record,
                accepted=bool(result.get("accepted", False)),
                confidence=result.get("confidence"),
                rationale=str(result.get("rationale", "")),
                model=str(result.get("model", "unknown")),
            )
            result_record["dimension_hints"] = result.get("dimension_hints") or []
            evaluated.append(result_record)
            if bool(result_record["accepted"]):
                accepted_results.append(result_record)
            else:
                rejected_results.append(result_record)

        payload: Dict[str, Any] = {
            "total_files": len(evaluated),
            "accepted_count": len(accepted_results),
            "rejected_count": len(rejected_results),
            "evaluations": evaluated,
            "accepted": accepted_results,
            "rejected": rejected_results,
        }
        context.set_parameter_value(_A3_LLM_RESULTS_PARAM, payload)
        return payload


class A3SuggestionsSavedCapability(A3BaseCapability):
    TARGET_STATE = A3LlmSuggestionProcessState.SUGGESTIONS_SAVED
    METADATA = CapabilityMetadata(
        id="org.infobim.a3.plugin.capability.transformation.target.suggestions_saved",
        version="1.0.0",
        name="A3 Suggestions Saved",
        description=(
            "Persist accepted LLM suggestions into the container so the "
            "Suggested Files screen can render them for the target BIM "
            "element and dimension-property."
        ),
        author=["http://kb.elias.eng.br/nid/elias.ttl#Elias"],
        tags=["infobim", "a3", "persistence", "suggestions"],
        supported_languages=A3SupportedLanguages.list(),
        log_message={
            "info": {
                "en": "A3 LLM file suggestions were persisted in the container.",
            },
            "debug_entry": {
                "en": "Persisting A3 LLM file suggestions into the container.",
            },
        },
    )

    @staticmethod
    def _index_path(container_path: Path) -> Path:
        return suggestion_index_directory(container_path) / "suggestions_index.json"

    def _transition_body(self, context: CliContextPort) -> Dict[str, Any]:
        bound = _bound_context(context)
        container_path: Path = bound["container_path"]
        element_id: str = bound["element_id"]
        dimension: str = bound["dimension"]

        evaluations: Any = context.get_parameter_value(_A3_LLM_RESULTS_PARAM)
        if not isinstance(evaluations, dict):
            raise ValueError(
                "A3 suggestions saved requires a previous successful "
                "llm_evaluated payload."
            )
        accepted: Any = evaluations.get("accepted")
        if not isinstance(accepted, list):
            raise ValueError(
                "A3 suggestions saved: llm_evaluated payload has no accepted list."
            )

        index_path: Path = A3SuggestionsSavedCapability._index_path(container_path)
        index_data: Dict[str, Any] = {"schema_version": "1.0", "by_target": {}}
        if index_path.is_file():
            try:
                loaded: Any = json.loads(index_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    index_data = loaded
            except Exception:
                index_data = {"schema_version": "1.0", "by_target": {}}
        index_data.setdefault("by_target", {})
        key: str = json.dumps(suggestion_key(element_id, dimension), sort_keys=True)
        previous_by_path: Dict[str, Any] = {}
        previous_bucket: Any = index_data["by_target"].get(key)
        if isinstance(previous_bucket, dict):
            previous_list: Any = previous_bucket.get("items")
            if isinstance(previous_list, list):
                for item in previous_list:
                    if isinstance(item, dict):
                        rp: Any = item.get("relative_path")
                        if isinstance(rp, str):
                            previous_by_path[rp] = item

        now: str = datetime.now(timezone.utc).isoformat()
        merged_items: List[Dict[str, Any]] = []
        seen_paths: set = set()
        for accepted_record in accepted:
            if not isinstance(accepted_record, dict):
                continue
            relative_path: str = str(accepted_record.get("relative_path") or "")
            if not relative_path or relative_path in seen_paths:
                continue
            seen_paths.add(relative_path)
            merged: Dict[str, Any] = dict(accepted_record)
            merged["updated_at"] = now
            if relative_path in previous_by_path:
                prev: Dict[str, Any] = previous_by_path[relative_path]
                created_at: Any = prev.get("created_at")
                if isinstance(created_at, str):
                    merged["created_at"] = created_at
                else:
                    merged["created_at"] = now
            else:
                merged["created_at"] = now
            merged.setdefault("status", "suggested")
            merged_items.append(merged)

        index_data["by_target"][key] = {
            "element_id": element_id,
            "dimension_property": dimension,
            "updated_at": now,
            "item_count": len(merged_items),
            "items": merged_items,
        }
        index_path.write_text(
            json.dumps(index_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return {
            "index_path": str(index_path),
            "element_id": element_id,
            "dimension_property": dimension,
            "saved_count": len(merged_items),
        }


def mimetypes_for_file(file_path: Path) -> Optional[Tuple[str, Optional[str]]]:
    """Small helper to keep :mod:`mimetypes` side-effect centralised."""
    import mimetypes

    mimetypes.init()
    return mimetypes.guess_type(str(file_path))


class A3LlmEvaluationAdapter:
    """Evaluate a single file through Claude Haiku/Sonnet with a local fallback.

    Routing rules
    -------------
    * If ``ANTHROPIC_API_KEY`` is present and the ``anthropic`` package is
      importable → **real API**:
      - document ≤ 32 KiB or extension in ``{md,txt,csv,json,yaml,yml}`` →
        ``claude-3-haiku-20240307``
      - otherwise → ``claude-3-5-sonnet-20241022`` (SONNET)
    * Otherwise → **deterministic heuristic** that returns the same JSON
      contract so downstream persistence / rendering is identical and users
      get a reproducible baseline pipeline even before the API is wired.
    """

    _HAIKU_ID: ClassVar[str] = "anthropic/claude-3-haiku-20240307"
    _SONNET_ID: ClassVar[str] = "anthropic/claude-3-5-sonnet-20241022"
    _LOCAL_HINT_ID: ClassVar[str] = "local/heuristic-v1"
    _HAIKU_MAX_SIZE_BYTES: ClassVar[int] = 32 * 1024
    _DOCUMENT_SNIPPET_BYTES: ClassVar[int] = 8 * 1024
    _HINTED_EXTENSIONS: ClassVar[frozenset] = frozenset(
        {
            "md", "txt", "csv", "tsv", "json", "yaml", "yml", "xml",
            "xlsx", "xls", "ods", "docx", "odt", "pdf",
        }
    )

    # ------------------------------------------------------------------
    # Public evaluation entry point
    # ------------------------------------------------------------------
    def evaluate(
        self,
        *,
        container_path: Path,
        element_id: str,
        dimension_property: str,
        file_record: Dict[str, Any],
        index: int,
        total: int,
    ) -> Dict[str, Any]:
        relative_path: str = str(file_record.get("relative_path") or "")
        absolute_path: Path = container_path / Path(relative_path)
        snippet: str = self._safe_snippet(absolute_path)
        metadata: Dict[str, Any] = dict(file_record)
        prompt: str = build_llm_prompt(
            element_id=element_id,
            dimension_property=dimension_property,
            file_relative_path=relative_path,
            file_metadata=metadata,
            file_snippet=snippet,
        )

        if self._api_enabled():
            size_bytes: int = int(file_record.get("size_bytes") or 0)
            extension: str = str(file_record.get("extension") or "").lower()
            use_sonnet: bool = (
                size_bytes > self._HAIKU_MAX_SIZE_BYTES
                or extension not in self._HINTED_EXTENSIONS
                and extension in {"pdf", "docx", "xlsx"}
            )
            model_label: str = self._SONNET_ID if use_sonnet else self._HAIKU_ID
            try:
                return self._call_anthropic(
                    prompt=prompt,
                    model_label=model_label,
                    relative_path=relative_path,
                    sonnet=use_sonnet,
                )
            except Exception as exc:  # pragma: no cover - runtime guard
                return {
                    "relative_path": relative_path,
                    "accepted": False,
                    "confidence": 0.0,
                    "rationale": (
                        "Anthropic API call failed for this file, falling "
                        f"back to local heuristics: {type(exc).__name__}: {exc}"
                    ),
                    "model": f"{model_label}+heuristic-fallback",
                    "dimension_hints": [],
                    **self._heuristic_result(
                        relative_path=relative_path,
                        dimension_property=dimension_property,
                        snippet=snippet,
                    ),
                }

        return {
            "relative_path": relative_path,
            "model": self._LOCAL_HINT_ID,
            **self._heuristic_result(
                relative_path=relative_path,
                dimension_property=dimension_property,
                snippet=snippet,
            ),
        }

    # ------------------------------------------------------------------
    # API wiring helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _api_enabled() -> bool:
        key: Optional[str] = os.environ.get("ANTHROPIC_API_KEY")
        if not isinstance(key, str) or not key.strip():
            return False
        try:
            import anthropic  # type: ignore  # noqa: F401
        except Exception:
            return False
        return True

    def _call_anthropic(
        self,
        *,
        prompt: str,
        model_label: str,
        relative_path: str,
        sonnet: bool,
    ) -> Dict[str, Any]:
        import anthropic

        api_key: str = str(os.environ.get("ANTHROPIC_API_KEY") or "").strip()
        client: Any = anthropic.Anthropic(api_key=api_key)
        model_id: str = (
            "claude-3-5-sonnet-20241022"
            if sonnet
            else "claude-3-haiku-20240307"
        )
        message: Any = client.messages.create(
            model=model_id,
            max_tokens=512,
            temperature=0.0,
            system=(
                "You are a strict JSON-only assistant. Respond with exactly "
                "the requested JSON object and no additional prose."
            ),
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text: str = ""
        for block in getattr(message, "content", []) or []:
            block_type: str = str(getattr(block, "type", "") or "")
            if block_type == "text":
                raw_text += str(getattr(block, "text", "") or "")
        return self._parse_llm_json(raw_text, relative_path, model_label)

    def _parse_llm_json(
        self,
        raw_text: str,
        relative_path: str,
        model_label: str,
    ) -> Dict[str, Any]:
        payload: Any = None
        text: str = str(raw_text or "").strip()
        if text:
            try:
                payload = json.loads(text)
            except Exception:
                start: int = text.find("{")
                end: int = text.rfind("}")
                if 0 <= start < end:
                    try:
                        payload = json.loads(text[start : end + 1])
                    except Exception:
                        payload = None
        if not isinstance(payload, dict):
            return {
                "relative_path": relative_path,
                "accepted": False,
                "confidence": 0.0,
                "rationale": (
                    "LLM did not return a parseable JSON object; "
                    "treating the file as rejected."
                ),
                "model": model_label,
                "dimension_hints": [],
            }
        accepted: Any = payload.get("accepted")
        confidence: Any = payload.get("confidence")
        rationale: Any = payload.get("rationale")
        hints: Any = payload.get("dimension_hints")
        clean_confidence: Optional[float]
        if isinstance(confidence, (int, float)):
            clean_confidence = float(confidence)
            if clean_confidence < 0.0:
                clean_confidence = 0.0
            elif clean_confidence > 1.0:
                clean_confidence = 1.0
        else:
            clean_confidence = None
        clean_hints: List[str]
        if isinstance(hints, list):
            clean_hints = [str(h) for h in hints if isinstance(h, str)]
        else:
            clean_hints = []
        return {
            "relative_path": relative_path,
            "accepted": bool(accepted),
            "confidence": clean_confidence,
            "rationale": str(rationale or "").strip(),
            "model": model_label,
            "dimension_hints": clean_hints,
        }

    # ------------------------------------------------------------------
    # Local heuristic fallback (API disabled, API failure, or testing)
    # ------------------------------------------------------------------
    def _heuristic_result(
        self,
        *,
        relative_path: str,
        dimension_property: str,
        snippet: str,
    ) -> Dict[str, Any]:
        name: str = Path(relative_path).name.lower()
        stem: str = Path(relative_path).stem.lower()
        ext: str = Path(relative_path).suffix.lower().lstrip(".")
        dim_tokens: List[str] = [
            t for t in _tokenize(str(dimension_property).lower()) if t
        ]
        dim_mentions: List[str] = [
            token for token in dim_tokens if token and token in (snippet.lower() + " " + name + " " + stem)
        ]
        doc_like: bool = ext in self._HINTED_EXTENSIONS
        size_hint: bool = len(snippet.strip()) > 64
        keyword_bonus: int = len(dim_mentions)

        accepted: bool = doc_like and (keyword_bonus >= 1 or size_hint and keyword_bonus >= 0)
        confidence: float = 0.0
        if doc_like:
            confidence += 0.35
        if size_hint:
            confidence += 0.15
        confidence += min(0.4, 0.1 * keyword_bonus)
        if confidence > 1.0:
            confidence = 1.0
        if not accepted:
            confidence = max(0.0, confidence - 0.1)

        rationale: str
        if accepted:
            rationale = (
                f"Arquivo {relative_path} foi classificado como fonte de "
                f"evidência plausível para a dimensão {dimension_property} "
                f"(heurística local: tipo documental={doc_like}, "
                f"menções={sorted(set(dim_mentions))})."
            )
        else:
            rationale = (
                f"Arquivo {relative_path} foi rejeitado pela heurística "
                f"local: não é um tipo documental reconhecido ou não "
                f"apresenta conteúdo suficiente para a dimensão "
                f"{dimension_property}."
            )
        return {
            "accepted": accepted,
            "confidence": confidence,
            "rationale": rationale,
            "dimension_hints": sorted(set(dim_mentions)),
        }

    @classmethod
    def _safe_snippet(cls, absolute_path: Path) -> str:
        if not absolute_path.is_file():
            return ""
        size: int = absolute_path.stat().st_size if absolute_path.exists() else 0
        if size == 0:
            return ""
        ext: str = absolute_path.suffix.lower()
        text_extensions: frozenset = frozenset(
            {
                ".txt", ".md", ".markdown", ".rst", ".csv", ".tsv",
                ".json", ".geojson", ".ndjson", ".jsonl", ".yaml", ".yml",
                ".xml", ".html", ".htm", ".log", ".ini", ".cfg", ".sql",
            }
        )
        if ext not in text_extensions:
            return ""
        try:
            with open(absolute_path, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read(cls._DOCUMENT_SNIPPET_BYTES)
        except Exception:
            return ""


def _tokenize(value: str) -> List[str]:
    return [t for t in __TOKEN_SPLIT_RE.split(value.lower()) if t]


__TOKEN_SPLIT_RE: Any = _re.compile(r"[^a-z0-9]+")

__all__: List[str] = [
    "A3BaseCapability",
    "A3ContainerBoundCapability",
    "A3FilesEnumeratedCapability",
    "A3LlmEvaluatedCapability",
    "A3LlmEvaluationAdapter",
    "A3RoCrateLoadedCapability",
    "A3SuggestionsSavedCapability",
]
assert TransactionCapabilityPort is not None  # explicit import guard
