# Annotating a file held by a container is the OntoBDC runtime doing its own
# job, and an InfoBIM project is one of those containers, so the command is
# re-exported rather than wrapped: it already answers to the same word and
# already declares the "annotate" logical component InfoBIM finds it under.
from ontobdc.context.plugin.command.annotate import AnnotateCommand

__all__ = ["AnnotateCommand"]
