# An InfoBIM project is an OntoBDC container, so initializing a workspace is
# exactly OntoBDC's own `init` — there is no InfoBIM-specific behaviour to
# add. Re-exporting the command is enough for the loader to find it: it
# discovers classes by inspecting the module, and this one already declares
# the "cli" logical component InfoBIM looks it up under.
from ontobdc.cli.plugin.command.init import CliInitCommand

__all__ = ["CliInitCommand"]
