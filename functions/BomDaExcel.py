#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Importa automaticamente tutte le BOM da una cartella:
- cerca tutti i file *.xls / *.xlsx / *.xlsm
- filtra quelli che nel nome contengono 'PRT LIST' o 'PART LIST'
- per ciascuno:
    - legge la BOM con carica_bom_da_excel
    - se la P/N esiste già in Odoo -> non fa nulla (modalità normale)
    - oppure la sovrascrive (modalità overwrite=True)
    - altrimenti crea x_boms + x_bom_line

Espone la funzione:

    import_boms_from_folder(folder, client, log=print, overwrite=False)

da usare nella GUI o in altri script.

NOTA: qui NON definiamo OdooClient, usiamo quello che gli passi tu
(dal tuo main / MainWindow).
"""

from pathlib import Path
from typing import Iterable, Tuple, List, Dict
import math
import config
from functions.data.BOM_partslist import DocumentoBOM, carica_bom_da_excel

# nomi dei modelli Odoo
BOM_HEADER_MODEL = "x_boms"
BOM_LINE_MODEL = "x_bom_line"


# ======================================================================
# MAPPING: DocumentoBOM -> dati testata + righe (ex ExcelHelper)
# ======================================================================

def documento_to_header_data(doc: DocumentoBOM) -> Dict:
    """
    Converte un DocumentoBOM nei campi della testata x_boms.
    Usa:
      - doc.pn come P/N
      - doc.title come Titolo
      - un "name" base = "PN - Title"
    """
    pn = doc.pn or ""
    title = doc.title or ""
    base_name = f"{pn} - {title}" if title else pn or (doc.code or "BOM")

    # Serializzo autori e revisioni in testo (solo se presenti)
    authors_lines: List[str] = []
    for a in doc.authors or []:
        authors_lines.append(
            f"{a.responsibility or ''} | {a.company or ''} | {a.unit or ''} | "
            f"{a.company_code or ''} | {a.sign_date or ''}"
        )
    authors_text = "\n".join(authors_lines)

    rev_lines: List[str] = []
    for r in doc.part_list_revisions or []:
        rev_lines.append(f"{r.revision} - {r.description}")
    pl_revisions_text = "\n".join(rev_lines)

    header_data: Dict = {
        "x_name": base_name,
        "x_studio_x_name": base_name,
        "x_studio_x_pn": pn,            # P/N
        "x_studio_x_titolo": title,     # Titolo

        "x_studio_x_revision": doc.revision or "",
        "x_studio_x_data": doc.doc_date.isoformat() if doc.doc_date else False,
        "x_studio_x_type": doc.bom_type or "",
        "x_studio_x_only_released": doc.only_released or "",
        "x_studio_x_ram_number": doc.ram_number or "",
        "x_studio_x_ram_validity": doc.ram_validity or "",
        "x_studio_x_authors": authors_text,
        "x_studio_x_pl_revisions": pl_revisions_text,
    }

    return header_data


def documento_to_line_data_list(doc: DocumentoBOM) -> List[Dict]:
    """
    Converte le righe di DocumentoBOM (doc.items) in una lista di dict
    pronti per la creazione di record x_bom_line in Odoo.
    """
    line_data_list: List[Dict] = []

    for idx, item in enumerate(doc.items, start=1):
        # POS safe
        try:
            pos = int(item.pos) if item.pos is not None else idx
        except ValueError:
            pos = idx

        def _safe_qty(val):
            if val is None:
                return 0.0
            try:
                v = float(val)
                if math.isnan(v):
                    return 0.0
                return v
            except (ValueError, TypeError):
                return 0.0

        qty = _safe_qty(item.qty)

        def _to_float(val):
            if val is None:
                return 0.0
            try:
                return float(str(val).replace(",", "."))
            except ValueError:
                return 0.0

        line: Dict = {
            "x_studio_x_pos": pos,
            "x_studio_x_qty": float(qty),
            "x_studio_x_um": item.um or "",
            "x_studio_x_internal_code": item.internal_code or "",
            "x_studio_x_description": item.description or "",
            "x_studio_x_val": _to_float(item.val),
            "x_studio_x_rat": _to_float(item.rat),
            "x_studio_x_tol": _to_float(item.tol),

            # refdesignator = Rif.Schema / Diag Ref.
            "x_studio_x_refdesignator": (
                item.ref_designator
                or getattr(item, "rif_dis", None)
                or ""
            ),
            "x_studio_x_tecn": item.tecn or "",
            "x_studio_x_notes": item.notes or "",
            "x_studio_x_manufacturer": item.manufacturer or "",
            "x_studio_x_manufacturer_code": item.manufacturer_code or "",

            # nuovi campi PDF (nomi tecnici da Odoo)
            "x_studio_x_type": item.tipo or "",          # colonna Tipo / Type
            "x_studio_x_rev": item.rev or "",            # colonna Rev.
            "x_studio_x_access_ref": item.rif_access or "",  # colonna Rif Access
            "x_studio_x_ce": item.ce or "",              # colonna CE
            "x_studio_x_mp": item.mp or "",              # colonna MP

            "x_name": f"{item.internal_code or ''} {item.description or ''}".strip(),
        }

        line_data_list.append(line)

    return line_data_list


# ======================================================================
# create_bom (integrata qui, al posto di CreateRecords)
# ======================================================================

def create_bom(client, header_data: dict, line_data_list: List[dict]) -> Tuple[int, List[int]]:
    """
    Crea una BOM (testata + righe) in Odoo.

    `client` deve avere almeno i metodi:
        - create(model, vals)
        - search(model, domain)
    come il tuo OdooClient in view.gui.
    """
    # copia locale
    safe_header = dict(header_data)

    # assicurati che x_name sia sempre valorizzato (campo obbligatorio di x_boms)
    if not safe_header.get("x_name"):
        base_name = safe_header.get("x_studio_x_name")
        if not base_name:
            pn = safe_header.get("x_studio_x_pn", "")
            # titolo: prova sia x_studio_x_titolo che x_studio_x_title
            title = safe_header.get("x_studio_x_titolo", "") or safe_header.get("x_studio_x_title", "")
        revision = safe_header.get("x_studio_x_revision", "")
        parts = [p for p in [pn, title, revision] if p]
        base_name = " - ".join(parts) or "BOM senza nome"
        safe_header["x_name"] = base_name

    print("Header che mando a Odoo:", safe_header)

    # 1) crea la testata
    bom_id = client.create(BOM_HEADER_MODEL, safe_header)

    # 2) crea righe collegate
    line_ids: List[int] = []
    for line_data in line_data_list:
        vals = dict(line_data)
        # campo many2one dal modello x_bom_line verso x_boms
        vals["x_studio_x_boms_id"] = bom_id
        line_id = client.create(BOM_LINE_MODEL, vals)
        line_ids.append(line_id)

    return bom_id, line_ids


# ======================================================================
# Nuova utility: sovrascrivere una BOM esistente
# ======================================================================

def overwrite_bom(client, bom_id: int, header_data: dict, line_data_list: List[dict], log=print) -> Tuple[int, List[int]]:
    """
    Sovrascrive una BOM esistente:
      - aggiorna la testata con write
      - cancella tutte le righe x_bom_line collegate
      - ricrea le righe da line_data_list

    Richiede che il client esponga anche:
      - write(model, ids, vals)
      - unlink(model, ids)
      - search(model, domain)
    """
    safe_header = dict(header_data)

    # come in create_bom: garantisci x_name valorizzato
    if not safe_header.get("x_name"):
        base_name = safe_header.get("x_studio_x_name")
        if not base_name:
            pn = safe_header.get("x_studio_x_pn", "")
            title = safe_header.get("x_studio_x_titolo", "") or safe_header.get("x_studio_x_title", "")
            revision = safe_header.get("x_studio_x_revision", "")
            parts = [p for p in [pn, title, revision] if p]
            base_name = " - ".join(parts) or "BOM senza nome"
        safe_header["x_name"] = base_name

    log(f"  ✏️ Aggiorno testata BOM ID {bom_id}")
    client.write(BOM_HEADER_MODEL, [bom_id], safe_header)

    # Cancella tutte le righe esistenti collegate a questa BOM
    existing_line_ids = client.search(
        BOM_LINE_MODEL,
        [("x_studio_x_boms_id", "=", bom_id)],
    )
    if existing_line_ids:
        log(f"  🗑 Cancello {len(existing_line_ids)} righe esistenti.")
        client.unlink(BOM_LINE_MODEL, existing_line_ids)

    # Crea nuove righe
    new_line_ids: List[int] = []
    for line_data in line_data_list:
        vals = dict(line_data)
        vals["x_studio_x_boms_id"] = bom_id
        line_id = client.create(BOM_LINE_MODEL, vals)
        new_line_ids.append(line_id)

    return bom_id, new_line_ids


# ======================================================================
# UTILS PER I FILE EXCEL
# ======================================================================

def iter_bom_files(base_dir: Path) -> Iterable[Path]:
    """
    Ritorna tutti i file Excel nella cartella (e sottocartelle)
    che nel nome contengono 'PRT LIST' o 'PART LIST' (case-insensitive).
    """
    patterns = ("*.xls", "*.xlsx", "*.xlsm")

    for pattern in patterns:
        for path in base_dir.rglob(pattern):
            name_up = path.name.upper()
            if "PRT LIST" in name_up or "PART LIST" in name_up:
                yield path


# ======================================================================
# IMPORT "NORMALE": create-or-skip (comportamento preesistente)
# ======================================================================

def import_or_skip_bom(client, doc: DocumentoBOM, log=print) -> Tuple[int | None, List[int]]:
    """
    Importa una singola BOM (DocumentoBOM) in Odoo:

    - se esiste già una BOM con lo stesso P/N -> non fa nulla e ritorna (existing_id, [])
    - se non esiste -> crea testata + righe con create_bom e ritorna (new_id, [line_ids])
    """
    header_data = documento_to_header_data(doc)
    line_data_list = documento_to_line_data_list(doc)

    pn = header_data.get("x_studio_x_pn") or doc.pn
    if not pn:
        log("  ⚠ Nessun P/N trovato, salto import di questa BOM.")
        return None, []
    revision = (doc.revision or "").strip()

    # Cerca BOM già presente per questo P/N e Revisione
    existing_ids = client.search(
        BOM_HEADER_MODEL,
        [
            ("x_studio_x_pn", "=", pn),
            ("x_studio_x_revision", "=", revision),
        ],
    )
    if existing_ids:
        log(
            f"  🔁 BOM per P/N {pn} e Revisione {revision} esiste già "
            f"(ID={existing_ids[0]}), non faccio nulla."
        )
        return existing_ids[0], []

    # Nessuna BOM esistente: crea nuova
    log(f"  🆕 Creo nuova BOM per P/N {pn}")
    bom_id, line_ids = create_bom(client, header_data, line_data_list)
    return bom_id, line_ids


# ======================================================================
# IMPORT CON SOVRASCRITTURA: create-or-overwrite
# ======================================================================

def import_with_overwrite(client, doc: DocumentoBOM, log=print) -> Tuple[str, int | None, List[int]]:
    """
    Importa una singola BOM (DocumentoBOM) in modalità "create-or-overwrite".

    Ritorna:
      - status: "imported", "overwritten" o "error"
      - bom_id
      - lista new_line_ids (vuota in caso di errore)
    """
    header_data = documento_to_header_data(doc)
    line_data_list = documento_to_line_data_list(doc)

    pn = header_data.get("x_studio_x_pn") or doc.pn
    if not pn:
        log("  ⚠ Nessun P/N trovato, salto import di questa BOM (manca P/N).")
        return "error", None, []

    revision = (doc.revision or "").strip()

    # Cerca BOM esistente per stesso P/N e Revisione
    existing_ids = client.search(
        BOM_HEADER_MODEL,
        [
            ("x_studio_x_pn", "=", pn),
            ("x_studio_x_revision", "=", revision),
        ],
    )
    if not existing_ids:
        # Nessuna BOM esistente: stesso comportamento di import_or_skip_bom
        log(
            f"  🆕 Nessuna BOM trovata per P/N {pn} con Revisione {revision or 'N/A'}, creo nuova BOM."
        )
        bom_id, line_ids = create_bom(client, header_data, line_data_list)
        return "imported", bom_id, line_ids

    if len(existing_ids) > 1:
        # Norma di sicurezza: se ci sono più BOM con stesso P/N e Revisione, non faccio nulla
        log(
            f"  ❌ [ERRORE] Trovate {len(existing_ids)} BOM per P/N {pn} e Revisione {revision} "
            f"(IDs={existing_ids}). Sovrascrittura bloccata, controlla i dati in Odoo."
        )
        return "error", None, []

    existing_id = existing_ids[0]
    log(
        f"  ♻️ Sovrascrivo BOM esistente per P/N {pn} e Revisione {revision} (ID={existing_id})."
    )
    bom_id, line_ids = overwrite_bom(client, existing_id, header_data, line_data_list, log=log)
    return "overwritten", bom_id, line_ids


# ======================================================================
# FUNZIONE PRINCIPALE RIUTILIZZABILE (PER GUI)
# ======================================================================

def import_boms_from_folder(folder, client, log=print, overwrite: bool = False) -> dict:
    """
    Esegue l'intero flusso di import partendo da una cartella.

    :param folder: cartella da cui leggere i file Excel delle BOM
    :param client: client Odoo già connesso (quello che hai in MainWindow)
    :param log: funzione di logging (default: print). Nella GUI puoi passare una funzione
                che aggiunge testo a una QTextEdit/console invece di stampare in console.
    :param overwrite: se False, modalità create-or-skip (comportamento storico);
                      se True, modalità create-or-overwrite (sovrascrive BOM esistenti
                      con lo stesso P/N).
    :return: dizionario con il riepilogo
             {
                 'imported': int,
                 'skipped': int,
                 'overwritten': int,
                 'errors': int,
             }
    """
    stats = {
        "imported": 0,
        "skipped": 0,
        "overwritten": 0,
        "errors": 0,
    }
    base_dir = Path(folder)

    if not base_dir.is_dir():
        raise FileNotFoundError(f"La cartella BOM non esiste: {base_dir}")

    log(f"📁 Cerco file BOM in: {base_dir}")
    files = list(iter_bom_files(base_dir))

    if not files:
        log("⚠ Nessun file Excel con 'PRT LIST' o 'PART LIST' nel nome trovato.")
        return stats

    log(f"✅ Trovati {len(files)} file BOM candidati:")
    for f in files:
        log(f"   - {f.name}")

    log("\n🔗 Uso il client Odoo già connesso.")
    log(f"⚙️ Modalità overwrite: {'ATTIVA' if overwrite else 'disattivata'}\n")

    for path in files:
        log(f"\n=== Elaboro file: {path.name} ===")
        try:
            # 1) Leggi la BOM dal file Excel
            doc = carica_bom_da_excel(str(path))

            log(f"  CODE:    {doc.code}")
            log(f"  REV:     {doc.revision}")
            log(f"  TITLE:   {doc.title}")
            log(f"  P/N:     {doc.pn}")
            log(f"  # RIGHE: {len(doc.items)}")

            if overwrite:
                # 2a) Import con sovrascrittura
                status, bom_id, line_ids = import_with_overwrite(client, doc, log=log)

                if status == "error":
                    log("  ❌ BOM non importata per errore.")
                    stats["errors"] += 1
                elif status == "imported":
                    log(f"  ✅ BOM creata (ID {bom_id}) con {len(line_ids)} righe.")
                    stats["imported"] += 1
                elif status == "overwritten":
                    log(f"  🔄 BOM sovrascritta (ID {bom_id}) con {len(line_ids)} nuove righe.")
                    stats["overwritten"] += 1
                else:
                    # safety net
                    log(f"  ❌ Stato sconosciuto '{status}', conto come errore.")
                    stats["errors"] += 1

            else:
                # 2b) Import "storico" create-or-skip
                bom_id, line_ids = import_or_skip_bom(client, doc, log=log)

                if bom_id is None:
                    log("  ⚠ BOM non importata (mancano dati essenziali).")
                    stats["errors"] += 1
                elif line_ids:
                    log(f"  ✅ BOM creata (ID {bom_id}) con {len(line_ids)} righe.")
                    stats["imported"] += 1
                else:
                    log(f"  ⏭ BOM già presente (ID {bom_id}), nessuna riga creata.")
                    stats["skipped"] += 1

        except Exception as e:  # noqa: BLE001
            log(f"  ❌ Errore durante l'elaborazione del file {path.name}: {e}")
            stats["errors"] += 1

    log("\n=== RIEPILOGO IMPORT ===")
    log(f"  ✅ Nuove BOM create    : {stats['imported']}")
    log(f"  🔄 BOM sovrascritte    : {stats['overwritten']}")
    log(f"  ⏭ BOM già presenti (skip): {stats['skipped']}")
    log(f"  ❌ Errori              : {stats['errors']}")

    return stats
