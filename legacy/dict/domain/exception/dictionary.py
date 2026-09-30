class DictionaryError(Exception):
    """
    Base of every failure the dictionary flow reports by itself.

    Reaching a dictionary, reading what it declares and applying it to an
    element are three different steps, and each fails for a reason the
    caller can act on. A bare ``ValueError`` would say that something went
    wrong without saying which of the three gave up.
    """


class DictionaryUriInvalidError(DictionaryError):
    """
    The URI given with ``--uri`` is not one a dictionary can be read from.

    A dictionary entry is read over HTTP(S) or from a file this machine
    can open. Anything else is reported rather than guessed at: a scheme
    nobody supports is a mistake in the invocation, not a location to be
    derived from the spelling.
    """


class DictionaryPrefixNotRegisteredError(DictionaryError):
    """
    The prefix given with ``--uri`` names no ontology this runtime knows.

    A prefix is short for a document, and which prefix is short for which
    document is declared centrally, once, for every tool that reads the
    ontology tree. A prefix nobody declared is therefore unknown rather
    than a location to be assembled out of its own spelling — assembling
    one would read whatever file happened to sit at the path the guess
    produced.
    """


class DictionaryEntryUnreachableError(DictionaryError):
    """
    The dictionary entry the URI names could not be retrieved.

    The entry is the whole input of this command, so a network failure, a
    404 or an empty document stops the run instead of leaving the element
    to be defined by nothing.
    """


class DictionaryDefinitionInvalidError(DictionaryError):
    """
    The retrieved document does not declare a definition to apply.

    A dictionary entry declares at least one class. A document that parses
    as RDF but declares none is not an entry of the dictionary, whatever
    it is, and what it would apply to the element is nothing.
    """


class DictionaryTargetInvalidError(DictionaryError):
    """
    The element the definitions are meant for is not properly identified.

    The identity is what ties a downloaded definition to the element it
    defines, so an absent or malformed GlobalId is reported here rather
    than allowing the state of one element to be filed under another.
    """
