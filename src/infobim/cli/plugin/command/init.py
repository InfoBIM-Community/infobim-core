# InfoBIM projects are OntoBDC containers, so initializing one is exactly
# OntoBDC's own `init` -- no InfoBIM-specific behavior needed. A plain
# re-export is enough for CommandLoader's discovery (inspect.getmembers()
# picks up imported names too) to register it under InfoBIM's own "cli"
# domain, matching its METADATA.logical_component == "cli".
from ontobdc.cli.plugin.command.init import CliInitCommand

__all__ = ["CliInitCommand"]
