from ontobdc.context.plugin.command import dictionary as _ontobdc_dictionary


class ContextDictionaryInspectCommand(
    _ontobdc_dictionary.ContextDictionaryInspectCommand
):
    """Expose ``ontobdc context --term <value> --inspect`` as ``infobim context``."""
