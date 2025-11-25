from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import List, Optional
import math
import datetime as dt
import pandas as pd

@dataclass
class RigaBOM:
    pos: str
    qty: Optional[float]
    um: Optional[str]
    internal_code: Optional[str]
    description: Optional[str]
    val: Optional[str]
    rat: Optional[str]
    tol: Optional[str]
    ref_designator: Optional[str]
    tecn: Optional[str]
    notes: Optional[str]
    manufacturer: Optional[str]
    manufacturer_code: Optional[str]

    # --- nuovi campi per PDF ---
    tipo: Optional[str] = None          # Tipo / Type
    rev: Optional[str] = None           # Rev.
    rif_dis: Optional[str] = None       # Rif.DIS
    rif_access: Optional[str] = None    # Rif.Access / Access Ref.
    ce: Optional[str] = None            # CE
    mp: Optional[str] = None            # MP


@dataclass
class AutoreBOM:
    responsibility: Optional[str]
    company: Optional[str]
    unit: Optional[str]
    company_code: Optional[str]
    sign_date: Optional[dt.date]

@dataclass
class PartListRevision:
    revision: str
    description: str

@dataclass
class DocumentoBOM:
    # Intestazione documento comuni (Excel + PDF)
    code: Optional[str]
    revision: Optional[str]
    doc_date: Optional[dt.date]
    title: Optional[str]
    pn: Optional[str]

    # Tabella autori (solo Excel)
    authors: List["AutoreBOM"]

    # Metadati finali (solo Excel)
    ram_number: Optional[str]
    ram_validity: Optional[str]
    part_list_revisions: List["PartListRevision"]

    # Lista parti
    items: List[RigaBOM]

    # --- nuovi campi header usati dal PDF ---
    bom_type: Optional[str] = None          # Tipo / Type intestazione
    only_released: Optional[str] = None     # Solo rilasciati / Only Released

    def to_dict(self) -> dict:
        return asdict(self)

def _to_str(value):
    """Converte in stringa pulita, oppure None per NaN / vuoti."""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return str(value).strip()


def _to_date(value):
    """Converte in datetime.date se possibile, altrimenti None."""
    if value is None:
        return None
    if isinstance(value, (dt.date, dt.datetime)):
        return value.date() if isinstance(value, dt.datetime) else value
    try:
        return pd.to_datetime(value, dayfirst=True).date()
    except Exception:
        return None


def _make_header_map(row) -> dict:
    """
    Dato un pandas.Series di intestazione,
    restituisce {TESTO_IN_MAIUSCOLO: indice_colonna}.
    """
    header_map = {}
    for idx, val in enumerate(row):
        name = _to_str(val)
        if not name:
            continue
        header_map[name.upper()] = idx
    return header_map


def _find_col(logical_name: str, header_map: dict, aliases: dict) -> Optional[int]:
    """
    Restituisce l'indice di colonna per un 'logical_name' (es. 'pos', 'qty'),
    provando tutte le etichette alias definite.
    """
    for alias in aliases.get(logical_name, []):
        col_idx = header_map.get(alias.upper())
        if col_idx is not None:
            return col_idx
    return None

BOM_COLUMN_ALIASES = {
    "pos": ["POS.", "POS", "POSITION"],
    "qty": ["Q.TY", "Q.Ty", "QTY", "QTY."],
    "um": ["UM", "U.M.", "UNIT"],
    "internal_code": ["INTERNAL CODE", "INT. CODE", "INT CODE", "PART NUMBER", "PART NO.", "P/N"],
    "description": ["DESCRIPTION", "DESCRIZIONE", "DESC"],
    "val": ["VAL", "VALUE"],
    "rat": ["RAT", "RATING"],
    "tol": ["TOL", "TOLERANCE"],
    "ref_designator": ["REF.DESIGNATOR", "REF. DESIGNATOR", "REFDES", "REF.DES"],
    "tecn": ["TECN", "TECH", "TECNOLOGIA"],
    "notes": ["NOTES", "NOTE"],
    "manufacturer": ["MANUFACTURER", "MFR", "MANUF."],
    "manufacturer_code": ["MANUFACTURER CODE", "MFR CODE", "MANUF CODE", "MFR. CODE"],
}
AUTHORS_COLUMN_ALIASES = {
    "responsibility": ["RESPONSIBILITY"],
    "company": ["COMPANY"],
    "unit": ["UNIT"],
    "company_code": ["CODE", "COMPANY CODE"],
    "date": ["DATE", "SIGN DATE"],
}
REVISION_META_ALIASES = {
    "rev": ["PART LIST REVISION", "REVISION", "REV."],
    "desc": ["MODIFY DESCRIPTION", "DESCRIPTION", "MOD. DESCRIPTION"],
}


def carica_bom_da_excel(path: str, sheet_name=0) -> DocumentoBOM:
    """
    Legge il file Excel e costruisce un DocumentoBOM.
    Funziona anche se le colonne della tabella Autori e BOM sono spostate,
    purché le intestazioni abbiano nomi riconoscibili.
    """
    df = pd.read_excel(path, sheet_name=sheet_name, header=None)

    # -------------------------------------------------
    # 1) Intestazione documento: CODE, REVISION, DATE, TITLE, P/N
    # -------------------------------------------------
    code = revision = None
    doc_date = None
    title = None
    pn = None

    for r in range(df.shape[0]):
        for c in range(df.shape[1]):
            val = df.iat[r, c]
            if not isinstance(val, str):
                continue
            text = val.strip()
            upper = text.upper()
            if upper.startswith("CODE:"):
                code = text.split(":", 1)[1].strip() or None
            elif upper.startswith("REVISION:"):
                revision = text.split(":", 1)[1].strip() or None
            elif upper.startswith("DATE:") and doc_date is None:
                doc_date = _to_date(text.split(":", 1)[1].strip())
            elif upper.startswith("TITLE:"):
                title = text.split(":", 1)[1].strip() or None

    # P/N: cerca la cella con "P/N:" e prende la prima a destra non vuota
    for r in range(df.shape[0]):
        for c in range(df.shape[1]):
            val = df.iat[r, c]
            if isinstance(val, str) and val.strip().upper() == "P/N:":
                for cc in range(c + 1, df.shape[1]):
                    v2 = df.iat[r, cc]
                    if v2 is not None and not (isinstance(v2, float) and math.isnan(v2)):
                        pn = str(v2).strip()
                        break
                break

    # -------------------------------------------------
    # 2) Trova riga intestazione Autori e intestazioni BOM (POS.)
    # -------------------------------------------------
    authors_header_row = None
    header_rows_bom: List[int] = []

    for r in range(df.shape[0]):
        row_vals = [(_to_str(df.iat[r, c]) or "").upper() for c in range(df.shape[1])]

        # intestazione Autori: contiene "RESPONSIBILITY"
        if "RESPONSIBILITY" in row_vals and authors_header_row is None:
            authors_header_row = r

        # intestazione BOM: contiene "POS." e una delle QTY
        if "POS." in row_vals and any(q in row_vals for q in ["Q.TY", "Q.TY", "QTY", "QTY."]):
            header_rows_bom.append(r)

    first_parts_header = min(header_rows_bom) if header_rows_bom else df.shape[0]

    # -------------------------------------------------
    # 3) Tabella Autori (tra intestazione "RESPONSIBILITY" e prima "POS.")
    # -------------------------------------------------
    authors: List[AutoreBOM] = []

    if authors_header_row is not None:
        header_map_auth = _make_header_map(df.iloc[authors_header_row])

        idx_resp = _find_col("responsibility", header_map_auth, AUTHORS_COLUMN_ALIASES)
        idx_comp = _find_col("company", header_map_auth, AUTHORS_COLUMN_ALIASES)
        idx_unit = _find_col("unit", header_map_auth, AUTHORS_COLUMN_ALIASES)
        idx_code = _find_col("company_code", header_map_auth, AUTHORS_COLUMN_ALIASES)
        idx_date = _find_col("date", header_map_auth, AUTHORS_COLUMN_ALIASES)

        for r in range(authors_header_row + 1, first_parts_header):
            row = df.iloc[r]

            resp = _to_str(row.iloc[idx_resp]) if idx_resp is not None else None
            if not resp:
                continue  # nessun autore valido in questa riga

            company = _to_str(row.iloc[idx_comp]) if idx_comp is not None else None
            unit = _to_str(row.iloc[idx_unit]) if idx_unit is not None else None
            company_code = _to_str(row.iloc[idx_code]) if idx_code is not None else None
            sign_date = _to_date(row.iloc[idx_date]) if idx_date is not None else None

            authors.append(
                AutoreBOM(
                    responsibility=resp,
                    company=company,
                    unit=unit,
                    company_code=company_code,
                    sign_date=sign_date,
                )
            )

    # -------------------------------------------------
    # 4) Metadati finali: RAM N, RAM VALIDITY, PART LIST REVISION, MODIFY DESCRIPTION
    # -------------------------------------------------
    ram_number = ram_validity = None
    part_list_revisions: List[PartListRevision] = []
    ram_header_row = None
    ram_header_map = None

    for r in range(df.shape[0]):
        row = df.iloc[r]
        row_vals = [(_to_str(v) or "").upper() for v in row]
        if any(v.startswith("RAM N") for v in row_vals):
            ram_header_row = r
            ram_header_map = _make_header_map(row)
            break

    rev_col = desc_col = None
    if ram_header_row is not None and ram_header_map is not None:
        rev_col = _find_col("rev", ram_header_map, REVISION_META_ALIASES)
        desc_col = _find_col("desc", ram_header_map, REVISION_META_ALIASES)

        # leggi le righe successive come revisioni finché c'è qualcosa nella colonna "rev"
        for r in range(ram_header_row + 1, df.shape[0]):
            row = df.iloc[r]
            raw_rev = row.iloc[rev_col] if rev_col is not None and rev_col < len(row) else None
            rev = _to_str(raw_rev)
            if not rev:
                continue
            raw_desc = row.iloc[desc_col] if desc_col is not None and desc_col < len(row) else None
            desc = _to_str(raw_desc) or ""
            part_list_revisions.append(PartListRevision(revision=rev, description=desc))

    # -------------------------------------------------
    # 5) Lista parti (BOM) con mappatura dinamica delle colonne
    # -------------------------------------------------
    items: List[RigaBOM] = []

    for header_row in header_rows_bom:
        header_map_bom = _make_header_map(df.iloc[header_row])

        idx_pos  = _find_col("pos", header_map_bom, BOM_COLUMN_ALIASES)
        idx_qty  = _find_col("qty", header_map_bom, BOM_COLUMN_ALIASES)
        idx_um   = _find_col("um", header_map_bom, BOM_COLUMN_ALIASES)
        idx_ic   = _find_col("internal_code", header_map_bom, BOM_COLUMN_ALIASES)
        idx_desc = _find_col("description", header_map_bom, BOM_COLUMN_ALIASES)
        idx_val  = _find_col("val", header_map_bom, BOM_COLUMN_ALIASES)
        idx_rat  = _find_col("rat", header_map_bom, BOM_COLUMN_ALIASES)
        idx_tol  = _find_col("tol", header_map_bom, BOM_COLUMN_ALIASES)
        idx_ref  = _find_col("ref_designator", header_map_bom, BOM_COLUMN_ALIASES)
        idx_tecn = _find_col("tecn", header_map_bom, BOM_COLUMN_ALIASES)
        idx_note = _find_col("notes", header_map_bom, BOM_COLUMN_ALIASES)
        idx_mfr  = _find_col("manufacturer", header_map_bom, BOM_COLUMN_ALIASES)
        idx_mfrc = _find_col("manufacturer_code", header_map_bom, BOM_COLUMN_ALIASES)

        # se per qualche motivo non abbiamo la colonna POS, saltiamo questo blocco
        if idx_pos is None:
            continue

        for r in range(header_row + 1, df.shape[0]):

            # nuova intestazione BOM → blocco successivo
            if r in header_rows_bom and r != header_row:
                break

            # se arriviamo al blocco RAM N° → fine BOM
            if ram_header_row is not None and r >= ram_header_row:
                break

            row = df.iloc[r]

            pos_val = row.iloc[idx_pos]
            if _to_str(pos_val) is None:
                continue  # riga vuota

            # sicurezza extra: se qui trovassimo ancora una riga di header
            if isinstance(pos_val, str) and pos_val.strip().upper() == "POS.":
                continue

            def get_cell(idx):
                if idx is None or idx >= len(row):
                    return None
                return row.iloc[idx]

            # qty numerica
            raw_qty = get_cell(idx_qty)
            qty: Optional[float] = None
            if isinstance(raw_qty, (int, float)) and not (isinstance(raw_qty, float) and math.isnan(raw_qty)):
                qty = float(raw_qty)

            items.append(
                RigaBOM(
                    pos=_to_str(pos_val) or "",
                    qty=qty,
                    um=_to_str(get_cell(idx_um)),
                    internal_code=_to_str(get_cell(idx_ic)),
                    description=_to_str(get_cell(idx_desc)),
                    val=_to_str(get_cell(idx_val)),
                    rat=_to_str(get_cell(idx_rat)),
                    tol=_to_str(get_cell(idx_tol)),
                    ref_designator=_to_str(get_cell(idx_ref)),
                    tecn=_to_str(get_cell(idx_tecn)),
                    notes=_to_str(get_cell(idx_note)),
                    manufacturer=_to_str(get_cell(idx_mfr)),
                    manufacturer_code=_to_str(get_cell(idx_mfrc)),
                )
            )

    # -------------------------------------------------
    # 6) Costruzione DocumentoBOM
    # -------------------------------------------------
    return DocumentoBOM(
        code=code,
        revision=revision,
        doc_date=doc_date,
        title=title,
        pn=pn,
        authors=authors,
        ram_number=ram_number,
        ram_validity=ram_validity,
        part_list_revisions=part_list_revisions,
        items=items,
    )

