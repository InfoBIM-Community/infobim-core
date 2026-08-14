import os
import csv
from typing import List, Dict, Any


def load_uhc_table(csv_path: str) -> List[Dict[str, Any]]:
    table: List[Dict[str, Any]] = []
    if not os.path.exists(csv_path):
        return table
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            table.append(row)
    return table


def load_sizing_table(csv_path: str) -> List[Dict[str, Any]]:
    table: List[Dict[str, Any]] = []
    if not os.path.exists(csv_path):
        return table
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            processed_row: Dict[str, Any] = {"dn": int(row["dn"])}
            for k in ["slope_0_5", "slope_1_0", "slope_2_0", "slope_4_0"]:
                val = row.get(k, "")
                if val and val.strip():
                    try:
                        processed_row[k] = float(val)
                    except Exception:
                        processed_row[k] = None
                else:
                    processed_row[k] = None
            table.append(processed_row)
    table.sort(key=lambda x: x["dn"])
    return table
