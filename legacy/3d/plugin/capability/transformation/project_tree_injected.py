# Re-export only -- see infobim/3d/__init__.py for why this package
# exists. CapabilityLoader's directory scan skips "infobim._3d" the
# same way it skips "__pycache__", so this class's own METADATA.id is
# only reachable through a plain top-level "infobim.3d" package.

from infobim._3d.plugin.capability.transformation.project_tree_injected import (
    ProjectTreeInjectedCapability,
)

__all__ = ["ProjectTreeInjectedCapability"]
