from typing import ClassVar, List, Tuple
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.parse import SplitResult, urlsplit, urlunsplit
from urllib.request import urlopen

from infobim.dict.domain.port.dictionary import DictionaryEntryFetcherPort
from infobim.dict.domain.exception.dictionary import (
    DictionaryUriInvalidError,
    DictionaryEntryUnreachableError,
)


class DictionaryEntryFetcher(DictionaryEntryFetcherPort):
    """
    Retrieves the document a dictionary URI names, and stores it.

    A dictionary is a place outside the project, so reaching it is a
    concern of its own: which schemes are supported, how long the project
    waits for an answer, and what counts as an answer at all. Everything
    downstream then reads a file, and never a URL — a definition is read
    once, from the copy the project kept, so reading it again cannot
    quietly become a different definition.

    A code-hosting page is not the document it displays. The reference
    dictionary is kept in a Git repository and its entries are linked by
    the URL a human opens, which serves HTML around the file rather than
    the file itself. Those URLs are translated to the raw location of the
    same revision, so the caller may paste the link they were given
    instead of hand-editing it into something a parser accepts. The
    translation is a declared pair of hosts, not a rewriting rule: a host
    nobody registered is fetched exactly as it was written.
    """

    HTTP_SCHEMES: ClassVar[Tuple[str, ...]] = ("http", "https")
    FILE_SCHEME: ClassVar[str] = "file"
    TIMEOUT_SECONDS: ClassVar[float] = 30.0
    ENCODING: ClassVar[str] = "utf-8"

    GITHUB_HOST: ClassVar[str] = "github.com"
    GITHUB_RAW_HOST: ClassVar[str] = "raw.githubusercontent.com"
    GITHUB_BLOB_SEGMENT: ClassVar[str] = "blob"

    def fetch(self, uri: str, destination: Path) -> Path:
        """
        Store what the URI returns at the destination and return it.
        """
        document: str = self._read(uri)
        if not document.strip():
            raise DictionaryEntryUnreachableError(
                f"The dictionary entry at {uri} is empty, so it defines "
                f"nothing that could be applied to an element."
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(document, encoding=self.ENCODING)

        return destination

    @classmethod
    def _read(cls, uri: str) -> str:
        """
        Return the document the URI names, whichever scheme it uses.
        """
        if not isinstance(uri, str) or not uri.strip():
            raise DictionaryUriInvalidError(
                "No dictionary URI was given, so there is no entry to read."
            )

        split: SplitResult = urlsplit(uri.strip())
        if split.scheme in cls.HTTP_SCHEMES:
            return cls._retrieved(cls.raw_uri(uri.strip()))

        if split.scheme in (cls.FILE_SCHEME, ""):
            return cls._opened(uri.strip(), split)

        raise DictionaryUriInvalidError(
            f"The dictionary URI {uri} uses the scheme '{split.scheme}', "
            f"which no dictionary is read over. Supported: "
            f"{', '.join(cls.HTTP_SCHEMES)}, {cls.FILE_SCHEME}, and a path "
            f"this machine can open."
        )

    @classmethod
    def raw_uri(cls, uri: str) -> str:
        """
        Return the URI the document itself is served at.

        Only the registered code-hosting page is translated; every other
        URI is the location of its own document and is returned unchanged.
        """
        split: SplitResult = urlsplit(uri)
        if split.netloc != cls.GITHUB_HOST:
            return uri

        segments: List[str] = [
            segment for segment in split.path.split("/") if segment
        ]
        if len(segments) < 5 or segments[2] != cls.GITHUB_BLOB_SEGMENT:
            return uri

        owner: str = segments[0]
        repository: str = segments[1]
        remainder: str = "/".join(segments[3:])

        return urlunsplit((
            split.scheme,
            cls.GITHUB_RAW_HOST,
            f"/{owner}/{repository}/{remainder}",
            "",
            "",
        ))

    @classmethod
    def _retrieved(cls, uri: str) -> str:
        """
        Return what the server answers, or fail saying it did not.
        """
        try:
            with urlopen(uri, timeout=cls.TIMEOUT_SECONDS) as response:
                return response.read().decode(cls.ENCODING)
        except HTTPError as error:
            raise DictionaryEntryUnreachableError(
                f"The dictionary at {uri} answered {error.code} "
                f"({error.reason}), so its entry was not read."
            ) from error
        except (URLError, OSError, ValueError) as error:
            raise DictionaryEntryUnreachableError(
                f"The dictionary at {uri} could not be reached: {error}."
            ) from error

    @classmethod
    def _opened(cls, uri: str, split: SplitResult) -> str:
        """
        Return a dictionary entry this machine holds as a file.
        """
        location: str = split.path if split.scheme == cls.FILE_SCHEME else uri
        document_path: Path = Path(location).expanduser()
        if not document_path.is_file():
            raise DictionaryEntryUnreachableError(
                f"The dictionary entry at {uri} is not a file this machine "
                f"holds: {document_path}."
            )

        return document_path.read_text(encoding=cls.ENCODING)
