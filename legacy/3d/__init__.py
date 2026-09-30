"""Re-export shim so `infobim 3d ...` keeps routing to `infobim._3d`.

The real 3D-viewer implementation lives under `infobim._3d`: "3d" is not
a usable Python identifier in hand-written source (`import infobim.3d`
is a SyntaxError), so the package itself is named `_3d` and every
absolute import against it (`from infobim._3d.adapter... import ...`)
goes through that name instead.

Plugin discovery does not go through hand-written imports, though --
CommandLoader.get_all() and CapabilityLoader.get_all()/get()
(ontobdc.shared.adapter.loader, both built on the same PluginLoader
base) walk `infobim`'s own installed directory looking for
`<name>/plugin/<resource>` folders via `_scan_directory`, which
explicitly skips any entry whose name starts with "_" (the same
convention that already excludes "__pycache__" and dotfiles). That
skip is what makes `infobim._3d` invisible to BOTH command and
capability discovery, regardless of what each class's own
METADATA.logical_component / METADATA.id says.

This package is the fix: a directory literally named "3d" (so the scan
finds it) whose `plugin/command/*.py` and `plugin/capability/**/*.py`
modules do nothing but re-export the real classes from `infobim._3d`.
The command loader's own code comment already accounts for exactly
this pattern ("a command module may import another domain's command
class... to delegate/proxy to it") -- each re-exported class's
METADATA is unchanged, so it is still discovered and registered as the
"3d" component's own command/capability.

Nothing here should ever contain real logic. If a new `infobim._3d`
command or capability needs to be discoverable as `infobim`'s "3d"
component, add a one-line re-export module for it here, not a copy of
its implementation.
"""
