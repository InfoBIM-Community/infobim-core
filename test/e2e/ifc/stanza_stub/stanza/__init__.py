"""
Test-only stand-in for the Stanza NLP package.

The real Stanza downloads its language models from the network, which the
end-to-end environment cannot rely on. This stand-in answers the language
named by ``INFOBIM_E2E_STANZA_LANGUAGE`` and keeps every word as its own
lowercased lemma, so the dictionary states still run on the given text.
It is placed on ``PYTHONPATH`` only by the end-to-end tests.
"""

from stanza.pipeline.core import Pipeline

__all__ = ["Pipeline"]
