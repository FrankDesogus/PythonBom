from __future__ import annotations

from typing import Dict, List, Any, Optional

from odoo_client import OdooClient
from domain.bom_models import Bom, BomLine
import config


class BomRepository:
    """
    Carica tutte le BOM e le righe da Odoo,
    indicizza i dati e calcola le BOM radice.
    """

    def __init__(self, client: OdooClient) -> None:
        self.client = client

        self.boms: List[Bom] = []
        self.lines: List[BomLine] = []

        self.boms_by_id: Dict[int, Bom] = {}
        self.boms_by_code_rev: Dict[tuple[str, str], Bom] = {}
        self.lines_by_bom_id: Dict[int, List[BomLine]] = {}

        self.root_boms: List[Bom] = []

    # ------------------------------------------------------------------
    # CARICAMENTO COMPLETO
    # ------------------------------------------------------------------

    def load_all(self) -> None:
        self._load_boms()
        self._load_lines()
        self._index_data()
        self._compute_root_boms()

    # ------------------------------------------------------------------
    # CARICAMENTO BOM
    # ------------------------------------------------------------------

    def _load_boms(self) -> None:
        fields = [
            "id",
            config.FIELD_BOM_PN,
            config.FIELD_BOM_TITLE,
            config.FIELD_BOM_X_NAME,
            config.FIELD_BOM_NAME,
            config.FIELD_BOM_REVISION,
        ]
        records = self.client.search_read(config.MODEL_BOM, [], fields=fields)

        self.boms = [
            Bom(
                id=rec["id"],
                pn=rec.get(config.FIELD_BOM_PN, "") or "",
                title=rec.get(config.FIELD_BOM_TITLE, "") or "",
                x_name=rec.get(config.FIELD_BOM_X_NAME, "") or "",
                name=rec.get(config.FIELD_BOM_NAME, "") or "",
                revision=rec.get(config.FIELD_BOM_REVISION, "") or "",
            )
            for rec in records
        ]

    # ------------------------------------------------------------------
    # CARICAMENTO RIGHE BOM
    # ------------------------------------------------------------------

    def _load_lines(self) -> None:
        """Carica record del modello x_bom_line."""
        records = self.client.search_read(
            config.MODEL_BOM_LINE,
            [],
            fields=[
                "id",
                config.FIELD_LINE_BOM,
                config.FIELD_LINE_POS,
                config.FIELD_LINE_QTY,
                config.FIELD_LINE_UNIT,
                config.FIELD_LINE_INTERNAL_CODE,
                config.FIELD_LINE_DESCRIPTION,
                config.FIELD_LINE_VAL,
                config.FIELD_LINE_RAT,
                config.FIELD_LINE_TOL,
                config.FIELD_LINE_REFDES,
                config.FIELD_LINE_TECN,
                config.FIELD_LINE_NOTES,
                config.FIELD_LINE_MANUFACTURER,
                config.FIELD_LINE_MANUFACTURER_CODE,
                config.FIELD_LINE_TYPE,
                config.FIELD_LINE_REV,
                config.FIELD_LINE_ACCESS_REF,
                config.FIELD_LINE_CE,
                config.FIELD_LINE_MP,
                config.FIELD_LINE_NAME,
            ],
        )

        lines: List[BomLine] = []

        for rec in records:
            # many2one: può essere [id, "name"] o un int o None
            bom_field = rec.get(config.FIELD_LINE_BOM, None)
            if isinstance(bom_field, list):
                bom_id = bom_field[0]
            elif isinstance(bom_field, int):
                bom_id = bom_field
            else:
                bom_id = 0

            # POS
            pos = str(rec.get(config.FIELD_LINE_POS, "") or "").strip()

            # internal_code può essere int, str o None
            raw_code = rec.get(config.FIELD_LINE_INTERNAL_CODE, "")
            if raw_code in (None, False):
                internal_code = ""
            else:
                internal_code = str(raw_code).strip()

            # qty robusta
            raw_qty = rec.get(config.FIELD_LINE_QTY, 0) or 0
            try:
                qty = float(raw_qty)
            except (TypeError, ValueError):
                qty = 0.0

            def _f(key) -> Optional[float]:
                raw = rec.get(key, None)
                if raw in (None, False, ""):
                    return None
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    return None

            line = BomLine(
                id=rec["id"],
                bom_id=bom_id,
                pos=pos,
                qty=qty,
                unit=(rec.get(config.FIELD_LINE_UNIT, "") or ""),
                internal_code=internal_code,
                description=(rec.get(config.FIELD_LINE_DESCRIPTION, "") or ""),
                val=_f(config.FIELD_LINE_VAL),
                rat=_f(config.FIELD_LINE_RAT),
                tol=_f(config.FIELD_LINE_TOL),
                refdesignator=(rec.get(config.FIELD_LINE_REFDES, "") or ""),
                tecn=(rec.get(config.FIELD_LINE_TECN, "") or ""),
                notes=(rec.get(config.FIELD_LINE_NOTES, "") or ""),
                manufacturer=(rec.get(config.FIELD_LINE_MANUFACTURER, "") or ""),
                manufacturer_code=(rec.get(config.FIELD_LINE_MANUFACTURER_CODE, "") or ""),
                type=(rec.get(config.FIELD_LINE_TYPE, "") or ""),
                rev=(rec.get(config.FIELD_LINE_REV, "") or ""),
                access_ref=(rec.get(config.FIELD_LINE_ACCESS_REF, "") or ""),
                ce=(rec.get(config.FIELD_LINE_CE, "") or ""),
                mp=(rec.get(config.FIELD_LINE_MP, "") or ""),
                name=(rec.get(config.FIELD_LINE_NAME, "") or ""),
            )

            lines.append(line)

        self.lines = lines

    # ------------------------------------------------------------------
    # INDICIZZAZIONE + ROOT BOM
    # ------------------------------------------------------------------

    def _index_data(self) -> None:
        self.boms_by_id = {b.id: b for b in self.boms}
        self.boms_by_code_rev = {}
        for b in self.boms:
            key = (b.pn.strip(), b.revision.strip())
            self.boms_by_code_rev[key] = b

        mapping: Dict[int, List[BomLine]] = {}
        for line in self.lines:
            mapping.setdefault(line.bom_id, []).append(line)
        self.lines_by_bom_id = mapping

    def _compute_root_boms(self) -> None:
        """
        Identifica le BOM radice:
        un P/N è radice se NON compare come internal_code in NESSUNA BOM Line.
        """
        self.root_boms = list(self.boms)


    # ------------------------------------------------------------------
    # API PUBBLICHE
    # ------------------------------------------------------------------

    def get_root_boms(self) -> List[Bom]:
        return list(self.root_boms)

    def get_lines_for_bom(self, bom_id: int) -> List[BomLine]:
        return self.lines_by_bom_id.get(bom_id, [])

    def get_bom_by_code(self, code: str, revision: str | None = None) -> Bom | None:
        code = code.strip()
        rev_key = revision.strip() if revision else ""

        if not code:
            return None

        bom = self.boms_by_code_rev.get((code, rev_key))
        if bom:
            return bom

        # fallback: se non specificata la revisione, ritorna la prima BOM con lo stesso codice
        for b in self.boms:
            if b.pn.strip() == code:
                return b
        return None

    def get_bom_by_id(self, bom_id: int) -> Bom | None:
        return self.boms_by_id.get(bom_id)
