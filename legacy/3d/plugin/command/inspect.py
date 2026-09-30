# Re-export only -- see infobim/3d/__init__.py for why this package
# exists. ThreeDInspectCommand's own METADATA is unchanged, so
# CommandLoader still discovers and registers it as the "3d"
# component's command.

from infobim._3d.plugin.command.inspect import ThreeDInspectCommand

__all__ = ["ThreeDInspectCommand"]
