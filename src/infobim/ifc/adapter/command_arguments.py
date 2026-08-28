from __future__ import annotations

from typing import Dict, List, Optional, Set


class IfcCommandArguments:
    """Parse the declarative argument shapes exposed by IFC commands."""

    PROJECT_FLAGS: Set[str] = {"--project-id", "--project"}

    @classmethod
    def parse(
        cls,
        args: List[str],
        *,
        valued_flags: Set[str],
        switch_flags: Set[str],
    ) -> Optional[Dict[str, Optional[str]]]:
        if not args or args[0] != "ifc":
            return None

        parsed: Dict[str, Optional[str]] = {}
        index: int = 1
        while index < len(args):
            flag: str = str(args[index])
            if flag in parsed:
                return None
            if flag in valued_flags:
                value_index: int = index + 1
                if value_index >= len(args):
                    return None
                value: str = str(args[value_index] or "").strip()
                if not value or value.startswith("--"):
                    return None
                parsed[flag] = value
                index += 2
                continue
            if flag in switch_flags:
                parsed[flag] = None
                index += 1
                continue
            return None

        if cls.PROJECT_FLAGS.issubset(parsed):
            return None
        return parsed
