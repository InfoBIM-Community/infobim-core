# Running a capability is the OntoBDC runtime doing its own job; InfoBIM adds
# nothing to it, so the command is re-exported rather than wrapped. The
# loader discovers it by inspecting this module, and its own "run" logical
# component is what InfoBIM looks it up under.
from ontobdc.run.plugin.command.capability import RunCapabilityCommand

__all__ = ["RunCapabilityCommand"]
