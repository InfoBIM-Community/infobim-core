from pathlib import Path
from typing import Any, ClassVar, List, Tuple

import yaml

from ontobdc.shared.adapter.statechart import StatechartLocator
from ontobdc.shared.adapter.worker import StateWorkerAdapter

from infobim.context.plugin.machine.entity_inspection.port import EntityInspectionProcessStatePort


class EntityInspectionStatechart:
    """Provide the statechart definition independently of machine execution."""

    PACKAGE: ClassVar[str] = "infobim.context.plugin.machine.entity_inspection"
    FILE: ClassVar[str] = "standard_entity_inspection.yaml"
    # The capability of a state has the id of a prefix followed by the state
    # name. InfoBIM's own prefix comes first; a state InfoBIM does not
    # implement is reached by the OntoBDC capability of the same name.
    CAPABILITY_ID_PREFIXES: ClassVar[Tuple[str, ...]] = (
        "org.infobim.context.plugin.capability.transformation.target.",
        "org.ontobdc.context.plugin.capability.transformation.target.",
    )

    @classmethod
    def path(cls) -> Path:
        return StatechartLocator.locate(cls.PACKAGE, cls.FILE)

    @classmethod
    def sequence(cls) -> List[str]:
        data: Any = yaml.safe_load(cls.path().read_text(encoding="utf-8"))
        return StateWorkerAdapter.compute_state_sequence(data)

    @classmethod
    def capability_ids(cls, state: EntityInspectionProcessStatePort) -> List[str]:
        state_name: str = state.value.strip("_")
        return [prefix + state_name for prefix in cls.CAPABILITY_ID_PREFIXES]
