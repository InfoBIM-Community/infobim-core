from __future__ import annotations
import ifcopenshell
import ifcopenshell.util.element
from typing import Dict, Any, Tuple, List, Optional, Set

def find_uhc_match(element, table: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    name = element.Name.lower() if element.Name else ""
    obj_type = element.ObjectType.lower() if element.ObjectType else ""
    desc = element.Description.lower() if element.Description else ""
    search_text = f"{name} {obj_type} {desc}"
    best_match = None
    for row in table:
        appliance = row["appliance"].lower()
        detail = row["detail"].lower() if row.get("detail") else ""
        if appliance in search_text:
            if detail and detail not in search_text:
                continue
            score = len(appliance) + len(detail)
            if best_match is None or score > best_match["score"]:
                best_match = {"row": row, "score": score}
    return best_match["row"] if best_match else None

def get_base_uhc(element, uhc_table: List[Dict[str, Any]]) -> float:
    uhc = 0.0
    psets = ifcopenshell.util.element.get_psets(element)
    if "Pset_BR_NBR8160" in psets and "UHC" in psets["Pset_BR_NBR8160"]:
        try:
            uhc = float(psets["Pset_BR_NBR8160"]["UHC"])
        except Exception:
            pass
    if element.is_a("IfcFlowTerminal") or element.is_a("IfcBuildingElementProxy") or element.is_a("IfcFurnishingElement"):
        match = find_uhc_match(element, uhc_table)
        if match and uhc == 0.0 and match.get("uhc"):
            try:
                uhc = float(match["uhc"])
            except Exception:
                pass
    return uhc

def calculate_sizing(total_uhc: float, sizing_table: List[Dict[str, Any]]):
    if total_uhc <= 0:
        return 0, 0
    for row in sizing_table:
        dn = row["dn"]
        if dn < 150:
            cap = row.get("slope_1_0")
            if cap is not None and total_uhc <= cap:
                return dn, 1.0
        else:
            cap = row.get("slope_1_0")
            if cap is not None and total_uhc <= cap:
                return dn, 1.0
            cap = row.get("slope_2_0")
            if cap is not None and total_uhc <= cap:
                return dn, 2.0
            cap = row.get("slope_4_0")
            if cap is not None and total_uhc <= cap:
                return dn, 4.0
    if sizing_table:
        return f">{sizing_table[-1]['dn']}", None
    return 0, 0

def get_all_connected_neighbors(element, ifc_file) -> Set[Any]:
    neighbors = set()
    try:
        for rel in ifc_file.get_inverse(element):
            if rel.is_a("IfcRelConnectsElements"):
                if rel.RelatingElement == element:
                    neighbors.add(rel.RelatedElement)
                elif rel.RelatedElement == element:
                    neighbors.add(rel.RelatingElement)
    except Exception:
        pass
    if hasattr(element, "IsNestedBy"):
        for rel in element.IsNestedBy:
            if rel.is_a("IfcRelDefinesByNesting") or rel.is_a("IfcRelNests"):
                for obj in rel.RelatedObjects:
                    if obj.is_a("IfcDistributionPort"):
                        try:
                            for port_rel in ifc_file.get_inverse(obj):
                                if port_rel.is_a("IfcRelConnectsPorts"):
                                    other_port = None
                                    if port_rel.RelatingPort == obj:
                                        other_port = port_rel.RelatedPort
                                    elif port_rel.RelatedPort == obj:
                                        other_port = port_rel.RelatingPort
                                    if other_port:
                                        for nest_rel in ifc_file.get_inverse(other_port):
                                            if nest_rel.is_a("IfcRelDefinesByNesting") or nest_rel.is_a("IfcRelNests"):
                                                if nest_rel.RelatingObject:
                                                    neighbors.add(nest_rel.RelatingObject)
                        except Exception:
                            pass
    return {n for n in neighbors if n is not None}

def _normalize_name(name: Optional[str]) -> str:
    if not name:
        return ""
    return name.replace("_", " ").strip().lower()

def determine_flow_direction(node_el, neighbor_el, ifc_file) -> str:
    if hasattr(node_el, "IsNestedBy"):
        for rel in node_el.IsNestedBy:
            if rel.is_a("IfcRelDefinesByNesting") or rel.is_a("IfcRelNests"):
                for item in rel.RelatedObjects:
                    if item.is_a("IfcDistributionPort"):
                        node_port = item
                        try:
                            for port_rel in ifc_file.get_inverse(node_port):
                                if port_rel.is_a("IfcRelConnectsPorts"):
                                    other_port = None
                                    if port_rel.RelatingPort == node_port:
                                        other_port = port_rel.RelatedPort
                                    elif port_rel.RelatedPort == node_port:
                                        other_port = port_rel.RelatingPort
                                    if other_port:
                                        owner = None
                                        for nest_rel in ifc_file.get_inverse(other_port):
                                            if nest_rel.is_a("IfcRelDefinesByNesting") or nest_rel.is_a("IfcRelNests"):
                                                owner = nest_rel.RelatingObject
                                                break
                                        if owner and owner.GlobalId == neighbor_el.GlobalId:
                                            fd = getattr(node_port, "FlowDirection", None)
                                            if fd == "SINK":
                                                return "upstream"
                                            elif fd == "SOURCE":
                                                return "downstream"
                        except Exception:
                            pass
    n_name = _normalize_name(neighbor_el.Name if neighbor_el.Name else "")
    c_name = _normalize_name(node_el.Name if node_el.Name else "")
    if "->" in n_name:
        parts = n_name.split("->")
        if len(parts) == 2:
            src = parts[0].strip()
            dst = parts[1].strip()
            if src == c_name:
                return "downstream"
            if dst == c_name:
                return "upstream"
    if "->" in c_name:
        parts = c_name.split("->")
        if len(parts) == 2:
            src = parts[0].strip()
            dst = parts[1].strip()
            if src == n_name:
                return "upstream"
            if dst == n_name:
                return "downstream"
    return "unknown"

def analyze_network(ifc_file, uhc_table, sizing_table, sink_name_filter=None, debug_callback=None):
    candidates = ifc_file.by_type("IfcDistributionElement") + \
                 ifc_file.by_type("IfcBuildingElementProxy") + \
                 ifc_file.by_type("IfcFurnishingElement")
    target_sinks = []
    if sink_name_filter:
        lower_filter = sink_name_filter.lower()
        is_guid = len(sink_name_filter) == 22 and "$" not in sink_name_filter
        for c in candidates:
            if is_guid and c.GlobalId == sink_name_filter:
                target_sinks.append(c)
                continue
            if c.Name and lower_filter in c.Name.lower():
                target_sinks.append(c)
    else:
        for c in candidates:
            if c.Name and "SANEPAR" in c.Name:
                target_sinks.append(c)
    target_sinks = list({c.GlobalId: c for c in target_sinks}.values())
    sink_map = {s.GlobalId: s for s in target_sinks}
    guids_to_remove = set()
    for guid1, s1 in sink_map.items():
        for guid2, s2 in sink_map.items():
            if guid1 == guid2:
                continue
            neighbors_s2 = get_all_connected_neighbors(s2, ifc_file)
            neighbor_guids = {n.GlobalId for n in neighbors_s2}
            if guid1 in neighbor_guids:
                direction = determine_flow_direction(s2, s1, ifc_file)
                if direction == "upstream":
                    guids_to_remove.add(guid1)
    final_sinks = [s for s in target_sinks if s.GlobalId not in guids_to_remove]
    target_sinks = final_sinks
    graph: Dict[str, Dict[str, Any]] = {}
    queue: List[str] = []
    for s in target_sinks:
        base_uhc = get_base_uhc(s, uhc_table)
        graph[s.GlobalId] = {
            "element": s,
            "base_uhc": base_uhc,
            "min_dn": 0,
            "min_slope": 0,
            "level": 0,
            "upstream": [],
            "downstream": [],
            "accumulated_uhc": 0.0,
        }
        queue.append(s.GlobalId)
    idx = 0
    while idx < len(queue):
        curr_guid = queue[idx]
        idx += 1
        curr_node = graph[curr_guid]
        curr_el = curr_node["element"]
        neighbors = get_all_connected_neighbors(curr_el, ifc_file)
        for n in neighbors:
            n_guid = n.GlobalId
            direction = determine_flow_direction(curr_el, n, ifc_file)
            if direction == "downstream":
                continue
            if n_guid not in curr_node["upstream"]:
                curr_node["upstream"].append(n_guid)
            if n_guid not in graph:
                base_uhc = get_base_uhc(n, uhc_table)
                graph[n_guid] = {
                    "element": n,
                    "base_uhc": base_uhc,
                    "min_dn": 0,
                    "min_slope": 0,
                    "level": curr_node["level"] + 1,
                    "upstream": [],
                    "downstream": [],
                    "accumulated_uhc": 0.0,
                }
                queue.append(n_guid)
            else:
                existing_node = graph[n_guid]
                new_level = curr_node["level"] + 1
                if new_level > existing_node["level"]:
                    existing_node["level"] = new_level
                    queue.append(n_guid)
    sorted_guids = sorted(graph.keys(), key=lambda k: graph[k]["level"], reverse=True)
    for guid in sorted_guids:
        node = graph[guid]
        total = node["base_uhc"]
        unique_sources: Dict[str, Dict[str, Any]] = {}
        for up_guid in node["upstream"]:
            curr_trace = graph[up_guid]
            while curr_trace["element"].is_a("IfcPipeSegment"):
                if not curr_trace["upstream"]:
                    break
                next_guid = curr_trace["upstream"][0]
                curr_trace = graph[next_guid]
            source_guid = curr_trace["element"].GlobalId
            is_pipe_path = graph[up_guid]["element"].is_a("IfcPipeSegment")
            if source_guid not in unique_sources:
                unique_sources[source_guid] = {
                    "entry_guid": up_guid,
                    "is_pipe": is_pipe_path,
                    "val": graph[up_guid]["accumulated_uhc"],
                }
            else:
                if is_pipe_path and not unique_sources[source_guid]["is_pipe"]:
                    unique_sources[source_guid] = {
                        "entry_guid": up_guid,
                        "is_pipe": is_pipe_path,
                        "val": graph[up_guid]["accumulated_uhc"],
                    }
        node["effective_upstream"] = []
        node["effective_sources"] = []
        for src_guid, info in unique_sources.items():
            up_val = info["val"]
            total += up_val
            node["effective_upstream"].append(info["entry_guid"])
            node["effective_sources"].append(
                {"source_guid": src_guid, "entry_guid": info["entry_guid"], "is_pipe": info["is_pipe"]}
            )
        node["accumulated_uhc"] = total
        min_dn, min_slope = calculate_sizing(total, sizing_table)
        node["min_dn"] = min_dn
        node["min_slope"] = min_slope
        if debug_callback:
            debug_callback(f"Total for {node['element'].Name}: {total}")
    return graph, target_sinks
