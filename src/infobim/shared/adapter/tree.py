from typing import Any, ClassVar, Dict, List


class FileTree:
    """
    Build a deterministic directory/file tree from relative paths.

    Every file node carries its own relative path, so a reader opening it
    does not have to rebuild the path from the names of the branches it
    hangs from, which are presentation labels, not directories.
    """

    NAME_KEY: ClassVar[str] = "name"
    PATH_KEY: ClassVar[str] = "path"
    KIND_KEY: ClassVar[str] = "kind"
    CHILDREN_KEY: ClassVar[str] = "children"
    OPENABLE_KEY: ClassVar[str] = "openable"
    DIRECTORY_KIND: ClassVar[str] = "dir"
    SEPARATOR: ClassVar[str] = "/"

    @classmethod
    def of(
        cls,
        file_paths: List[str],
        root_name: str,
        root_kind: str,
        file_kind: str,
    ) -> Dict[str, Any]:
        root: Dict[str, Any] = {}
        file_path: str
        for file_path in file_paths:
            cls._graft(root, cls._segments_of(file_path))

        return {
            cls.NAME_KEY: root_name,
            cls.KIND_KEY: root_kind,
            cls.OPENABLE_KEY: False,
            cls.CHILDREN_KEY: cls._nodes_of(root, file_kind),
        }

    @classmethod
    def _segments_of(cls, file_path: str) -> List[str]:
        return [
            segment
            for segment in file_path.strip().split(cls.SEPARATOR)
            if segment and segment != "."
        ]

    @classmethod
    def _graft(cls, branch: Dict[str, Any], segments: List[str]) -> None:
        """Hang the file named by ``segments`` from ``branch``, keeping its path."""
        if not segments:
            return

        segment: str
        for segment in segments[:-1]:
            child: Any = branch.get(segment)
            if not isinstance(child, dict):
                child = {}
                branch[segment] = child
            branch = child

        branch.setdefault(segments[-1], cls.SEPARATOR.join(segments))

    @classmethod
    def _nodes_of(
        cls,
        branch: Dict[str, Any],
        file_kind: str,
    ) -> List[Dict[str, Any]]:
        nodes: List[Dict[str, Any]] = []
        name: str
        for name in sorted(
            branch,
            key=lambda entry: (isinstance(branch[entry], str), entry.lower()),
        ):
            children: Any = branch[name]
            if isinstance(children, str):
                nodes.append(
                    {
                        cls.NAME_KEY: name,
                        cls.KIND_KEY: file_kind,
                        cls.PATH_KEY: children,
                        cls.CHILDREN_KEY: [],
                    }
                )
                continue

            nodes.append(
                {
                    cls.NAME_KEY: name,
                    cls.KIND_KEY: cls.DIRECTORY_KIND,
                    cls.OPENABLE_KEY: False,
                    cls.CHILDREN_KEY: cls._nodes_of(children, file_kind),
                }
            )

        return nodes
