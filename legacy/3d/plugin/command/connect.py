# Re-export only -- see infobim/3d/__init__.py for why this package
# exists. ThreeDConnectCommand's own METADATA is unchanged, so
# CommandLoader still discovers and registers it as the "3d"
# component's command.

from infobim._3d.plugin.command.connect import ThreeDConnectCommand

__all__ = ["ThreeDConnectCommand"]
