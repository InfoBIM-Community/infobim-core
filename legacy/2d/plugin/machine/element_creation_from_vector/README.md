# Element creation from vector

The statechart owns the sequence:

`UNDEFINED -> ELEMENT_KIND_RESOLVED -> ELEMENT_REPRESENTATION_RESOLVED`

The command creates an invocation-local context before parameter binding.
`KindStrategy` resolves the explicit `--kind`; no parameter or result is inherited
from the project's `context.ttl`. Missing `element_kind` is an error.

The execution container is the nearest ancestor of the invocation directory with
container metadata recognized by `StorageBootstrap`. The DXF must belong to that
container. A project `config.yaml` does not select the container for this command.

Each transformation writes its own atomic JSON event under:

```text
<container>/.__ontobdc__/etl/context/transformation/document/<sha256-of-dxf>/
    __element_kind_resolved__.json
    __element_representation_resolved__.json
```

Events record the source's container-relative path and content hash, the current
kind URI, the ontology resource fingerprint, the producing capability version,
and the output. Changes to these inputs invalidate reuse. Malformed events fail
explicitly. A context key by itself is never sufficient evidence of completion.

The evaluator derives the sequence from YAML, resolves capabilities by ID through
`CapabilityLoader`, and asks `is_satisfied()`. Representation readiness restores
validated output into the invocation-local context without rewriting the event.
Capabilities neither import nor invoke another capability or this machine.

The representation resolver follows `crm:P138i_has_representation` restrictions
on the kind and `crm:P138_represents` restrictions on representation classes in
the packaged kind ontologies. Missing or ambiguous representations fail explicitly.

Legacy values in a shared `context.ttl` are ignored, not migrated or deleted.
