from typing import Callable, Dict, Any, List, Set
from domain.bom_models import Bom, BomLine, TotalEntry


class BomExploder:
    def explode_bom(
        self,
        root_bom: Bom,
        get_lines_for_bom: Callable[[int], List[BomLine]],
        get_bom_by_pn: Callable[[str], Bom | None],
    ) -> tuple[Dict[str, Any], Dict[str, TotalEntry]]:
        totals: Dict[str, TotalEntry] = {}
        visited_pns: Set[str] = set()

        root_key = root_bom.pn.strip() or str(root_bom.id)
        visited_pns.add(root_key)

        tree = self._explode_recursive(
            bom=root_bom,
            qty_multiplier=1.0,
            get_lines_for_bom=get_lines_for_bom,
            get_bom_by_pn=get_bom_by_pn,
            totals=totals,
            visited_pns=visited_pns,
        )
        return tree, totals

    def _explode_recursive(
        self,
        bom: Bom,
        qty_multiplier: float,
        get_lines_for_bom: Callable[[int], List[BomLine]],
        get_bom_by_pn: Callable[[str], Bom | None],
        totals: Dict[str, TotalEntry],
        visited_pns: Set[str],
    ) -> Dict[str, Any]:

        node: Dict[str, Any] = {
            "pos": "",
            "internal_code": bom.pn,
            "description": bom.title,
            "qty": qty_multiplier,
            "unit": "",
            "manufacturer": "",
            "manufacturer_code": "",
            "refdes": "",
            "notes": "",
            "type": "",
            "rev": "",
            "access_ref": "",
            "ce": "",
            "mp": "",
            "children": [],
        }

        for line in get_lines_for_bom(bom.id):
            code = (line.internal_code or "").strip()
            total_qty = line.qty * qty_multiplier

            # --- TOTALIZZAZIONE: solo se codice NON vuoto e qty != 0
            if code and total_qty != 0:
                if code not in totals:
                    totals[code] = TotalEntry(
                        internal_code=code,
                        description=line.description,
                        qty=0.0,
                        unit=line.unit,
                        manufacturer=line.manufacturer,
                        manufacturer_code=line.manufacturer_code,
                    )
                totals[code].add_quantity(total_qty)

            # --- NODO FIGLIO BASE ---
            child_node: Dict[str, Any] = {
                "pos": line.pos,
                "internal_code": code,
                "description": line.description,
                "qty": total_qty,
                "unit": line.unit,
                "manufacturer": line.manufacturer,
                "manufacturer_code": line.manufacturer_code,
                "refdes": line.refdesignator,
                "notes": line.notes,
                "type": line.type,
                "rev": line.rev,
                "access_ref": line.access_ref,
                "ce": line.ce,
                "mp": line.mp,
                "children": [],
            }

            # --- SOTTO-BOM? ---
            sub_bom = get_bom_by_pn(code) if code else None
            if sub_bom:
                sub_key = sub_bom.pn.strip() or str(sub_bom.id)
                if sub_key in visited_pns:
                    # ciclo → evito ricorsione infinita, ma segnalo
                    child_node["description"] += " (RICORSIONE BLOCCATA)"
                else:
                    new_visited = set(visited_pns)
                    new_visited.add(sub_key)

                    sub_tree = self._explode_recursive(
                        bom=sub_bom,
                        qty_multiplier=total_qty,
                        get_lines_for_bom=get_lines_for_bom,
                        get_bom_by_pn=get_bom_by_pn,
                        totals=totals,
                        visited_pns=new_visited,
                    )

                    # innesto i dati di linea nel nodo radice della sotto-BOM
                    sub_tree["pos"] = line.pos
                    sub_tree["unit"] = line.unit
                    sub_tree["manufacturer"] = line.manufacturer
                    sub_tree["manufacturer_code"] = line.manufacturer_code
                    sub_tree["refdes"] = line.refdesignator
                    sub_tree["notes"] = line.notes
                    sub_tree["type"] = line.type
                    sub_tree["rev"] = line.rev
                    sub_tree["access_ref"] = line.access_ref
                    sub_tree["ce"] = line.ce
                    sub_tree["mp"] = line.mp

                    child_node = sub_tree

            node["children"].append(child_node)

        return node
