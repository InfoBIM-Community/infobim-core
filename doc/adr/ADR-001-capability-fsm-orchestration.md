# ADR 001: Capability Orchestration via Finite State Machine (FSM) and Ontological Metadata

## Status
Accepted

## Context
The InfoBIM system is evolving from a collection of isolated tools into a platform capable of executing complex engineering workflows (e.g., IFC file processing, data extraction, report generation).

Initially, we considered using Large Language Models (LLMs) as primary orchestrators, trusting them to decide which tool to call next and how to pass data from one to another. However, we observed that:
1.  **LLMs are probabilistic:** They may fail to maintain execution context, "hallucinate" parameters, or skip critical steps in engineering processes that require rigor.
2.  **Implicit Coupling:** Data passing between tools depended on the LLM "understanding" that tool A's output serves as tool B's input, without a formal contract.
3.  **Lack of Robustness:** Error handling (e.g., empty file, parse failure) was left to the model's interpretation, often resulting in ineffective retry loops.

Recently, capabilities have begun to be enriched with more detailed metadata, including input schemas (`input_schema`) and event definitions (`events`), suggesting a more formal structure.

## Decision
We decided to move the responsibility of **execution orchestration** to a deterministic **Finite State Machine (FSM)** or **Workflow Engine**, guided by explicit metadata and ontological keys. The LLM will act as a natural interface (intent recognition) and results analyst, but not as the step-by-step execution engine.

### Architecture Pillars:

1.  **Capabilities as Graph Nodes:**
    Capabilities cease to be isolated functions and explicitly declare:
    *   **Output Events (`events`):** Not just "success/error", but granular scenarios (e.g., `list_pipes.success`, `list_pipes.empty`, `list_pipes.paginated`).
    *   **Dependencies (`required`):** Execution prerequisites (e.g., `list_pipes` might require `list_materials` to have been executed).

2.  **Ontological Context Bus:**
    Input parameters will no longer use arbitrary names (like `lang`), but rather global semantic keys based on an ontology (e.g., `obdc.base.lang.code`).
    *   This allows the orchestrator to automatically inject values from an accumulated "Global Context" without one capability needing to know the other.

3.  **Deterministic Execution:**
    State transitions will be defined by clear rules based on triggered events.
    *   *Example:* If `list_pipes` triggers `success` -> Transition to `export_csv`.
    *   *Example:* If `list_pipes` triggers `failure` -> Transition to `error_handler` or `notify_user`.

## Consequences

### Positive
*   **Determinism and Reliability:** Engineering processes will follow pre-defined and testable paths, eliminating stochastic LLM variability in execution.
*   **Error Recovery:** Clear and robust "fallback" flows can be defined for each type of failure event.
*   **Observability:** The system state is always known (e.g., "Current State: Processing Geometry"), facilitating logging and debugging.
*   **Reusability:** Capabilities become LEGO pieces with standardized interfaces via ontology.

### Negative / Challenges
*   **Initial Rigidity:** Creating new workflows requires defining the FSM and metadata, losing the "magical" flexibility of asking the LLM for anything.
*   **Metadata Maintenance:** Requires strict discipline to keep `input_schema` and ontological keys synchronized across all capabilities. A contract breach (e.g., changing an ontological key) can stop the flow.
*   **Learning Curve:** Developers need to understand the ontology and event system to create new capabilities.

## Implementation Example (Metadata)

```python
class ListPipesCapability(Capability):
    METADATA = CapabilityMetadata(
        id="infobim.capability.base.list_pipes",
        # ...
        events={
            "success": "infobim.capability.base.list_pipes.success",
            "failure": "infobim.capability.base.list_pipes.failure",
            # Explicit dependency
            "required": ["infobim.capability.base.list_materials"]
        },
        input_schema={
            "type": "object",
            "properties": {
                # Input normalized via Ontology
                "obdc.base.lang.code": {
                    "type": "string", 
                    "enum": ["en", "pt_BR"],
                    "default": "en"
                }
            }
        }
    )
```
