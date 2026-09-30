# Running capabilities by tag is the OntoBDC runtime doing its own job;
# InfoBIM adds nothing to it, so the command is re-exported rather than
# wrapped. See the note in capability.py for why a plain re-export is enough.
from ontobdc.run.plugin.command.tag import RunTagCommand

__all__ = ["RunTagCommand"]
