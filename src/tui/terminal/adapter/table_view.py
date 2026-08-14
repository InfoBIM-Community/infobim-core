from typing import List, Tuple, Optional, Any
from rich.table import Table
from rich.box import Box

DASHED_HORIZONTALS = Box(
    " ── \n"
    "    \n"
    " ── \n"
    "    \n"
    " ╌╌ \n"
    " ── \n"
    "    \n"
    " ── \n"
)


class TableViewAdapter:
    PRIMARY_COLUMN = {"style": "cyan", "vertical": "top"}
    NUMERIC_COLUMN = {"justify": "right", "vertical": "top"}
    SECONDARY_COLUMN = {"style": "dim", "vertical": "top"}
    INDEX_COLUMN = {"justify": "right", "style": "dim", "vertical": "top"}

    @staticmethod
    def create_table(
        title: str,
        columns: List[Tuple[str, Any]],
        show_header: bool = True,
        header_style: str = "bold white",
        border_style: str = "grey35"
    ) -> Table:
        table = Table(
            title=title,
            box=DASHED_HORIZONTALS,
            border_style=border_style,
            show_lines=True,
            show_header=show_header,
            header_style=header_style
        )

        for col_name, col_kwargs in columns:
            table.add_column(col_name, **col_kwargs)

        return table

    @staticmethod
    def col(label: str, kind: str = "primary", **overrides: Any) -> Tuple[str, Any]:
        kind_map = {
            "primary": TableViewAdapter.PRIMARY_COLUMN,
            "numeric": TableViewAdapter.NUMERIC_COLUMN,
            "secondary": TableViewAdapter.SECONDARY_COLUMN,
            "index": TableViewAdapter.INDEX_COLUMN,
        }
        base = dict(kind_map.get(kind, {}))
        base.update(overrides)
        return label, base
