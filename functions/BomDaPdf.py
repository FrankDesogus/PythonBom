#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
from typing import List, Optional
from pathlib import Path

import pdfplumber

from functions.data.BOM_partslist import DocumentoBOM, RigaBOM, _to_date
from .BomDaExcel import import_or_skip_bom, import_with_overwrite   # 👈 riuso stessa logica Excel


# helper locale per le quantità
def _parse_qty_str(val: str) -> Optional[float]:
    """
    Converte una quantità letta dal PDF (stringa) in float.
    Accetta formati tipo '1', '1,0', '1.0', '1,25', ecc.
    """
    if val is None:
        return None
    txt = str(val).strip()
    if not txt:
        return None
    # tieni solo cifre, virgola, punto, segno
    txt = re.sub(r"[^0-9,.\-]", "", txt)
    # usa il punto come separatore decimale
    txt = txt.replace(",", ".")
    if not txt:
        return None
    try:
        return float(txt)
    except ValueError:
        return None


def carica_bom_da_pdf(path: str) -> DocumentoBOM:
    """
    Legge un PDF PART LIST nel formato 'E0223806 01-03_BOM.pdf'
    e costruisce un DocumentoBOM compatibile con l'import da Excel.
    - Header: Code, Revision, Tipo/Type, Title, Printing Date (doc_date), P/N=Code
    - Righe: 15 colonne (Riga, Tipo, Codice, Rev, Desc, Rif.DIS, Rif.Schema,
              Rif.Access, U.M., Q.tà, Note, CE, MP, Den.Comm, Rag.Soc).
    - Gestisce le righe di continuazione per Den.Comm / Rag.Soc.
    """
    path = str(path)

    with pdfplumber.open(path) as pdf:
        # ============================
        # 1) INTESTAZIONE (pagina 1)
        # ============================
        page0 = pdf.pages[0]
        text0 = page0.extract_text() or ""

        # Code
        m_code = re.search(
            r"Codice\s*/\s*Code\s+(.+?)\s+Revisione\s*/\s*Revision",
            text0,
            flags=re.IGNORECASE | re.DOTALL,
        )
        code = m_code.group(1).strip() if m_code else None

        # Revision
        m_rev = re.search(
            r"Revisione\s*/\s*Revision\s+(\S+)",
            text0,
            flags=re.IGNORECASE,
        )
        revision = m_rev.group(1).strip() if m_rev else None

        # Tipo / Type (intestazione BOM)
        m_bom_type = re.search(
            r"Tipo\s*/\s*Type\s+(.+?)\s+Descrizione\s*/\s*Description",
            text0,
            flags=re.IGNORECASE | re.DOTALL,
        )
        bom_type = m_bom_type.group(1).strip() if m_bom_type else None

        # Descrizione / Description (Titolo)
        m_title = re.search(
            r"Descrizione\s*/\s*Description\s+(.+)",
            text0,
            flags=re.IGNORECASE,
        )
        title = m_title.group(1).strip() if m_title else None

        # Solo rilasciati / Only Released
        m_only = re.search(
            r"Solo\s+rilasciati\s*/\s*Only\s+Released\s+(\S+)",
            text0,
            flags=re.IGNORECASE,
        )
        only_released = m_only.group(1).strip() if m_only else None

        # Data (uso il primo dd/mm/yyyy che trovo come Printing Date)
        m_date = re.search(r"(\d{2}/\d{2}/\d{4})", text0)
        doc_date = _to_date(m_date.group(1)) if m_date else None

        # P/N = Code (come tua logica)
        pn = code

        # ============================
        # 2) PART LIST (tutte le pagine)
        # ============================
        items: List[RigaBOM] = []
        current_item: Optional[RigaBOM] = None

        table_settings = {
            "vertical_strategy": "lines",
            "horizontal_strategy": "text",
        }

        for page in pdf.pages:
            tables = page.extract_tables(table_settings=table_settings) or []
            for tbl in tables:
                if not tbl:
                    continue

                # prima riga (header principale) come stringa unica
                first_row_text = " ".join((c or "") for c in tbl[0]).lower()

                # tabella PART LIST riconosciuta se contiene 'riga' e 'codice / code'
                has_bom_header = (
                    "riga" in first_row_text and "codice / code" in first_row_text
                )

                # se c'è l'header su 2 righe (pagina 1), salto le prime 2
                data_rows = tbl[2:] if has_bom_header else tbl

                for row in data_rows:
                    if not row:
                        continue

                    # normalizzo a 15 colonne
                    if len(row) < 15:
                        row = list(row) + [None] * (15 - len(row))

                    # riga completamente vuota → skip
                    if all((c is None) or (str(c).strip() == "") for c in row):
                        continue

                    c0 = (row[0] or "").strip()

                    # Nuova riga BOM se la prima colonna è un numero a 4 cifre (0010, 0020, 0145, ecc.)
                    if c0.isdigit() and len(c0) == 4:
                        tipo = (row[1] or "").strip()
                        codice = (row[2] or "").strip()
                        rev_item = (row[3] or "").strip()
                        descr = (row[4] or "").strip()
                        rif_dis = (row[5] or "").strip()
                        rif_schema = (row[6] or "").strip()
                        rif_access = (row[7] or "").strip()
                        um = (row[8] or "").strip()
                        qty = _parse_qty_str(row[9] or "")
                        note = (row[10] or "").strip()
                        ce = (row[11] or "").strip()
                        mp = (row[12] or "").strip()
                        den_comm = (row[13] or "").strip()
                        rag_soc = (row[14] or "").strip()

                        current_item = RigaBOM(
                            pos=c0,
                            qty=qty,
                            um=um or None,
                            internal_code=codice or None,
                            description=descr or None,
                            val=None,
                            rat=None,
                            tol=None,
                            ref_designator=rif_schema or None,
                            tecn=None,
                            notes=note or None,
                            manufacturer=rag_soc or None,          # Rag.Soc / Comp.Name
                            manufacturer_code=den_comm or None,    # Den.Comm / Trade Number
                            tipo=tipo or None,
                            rev=rev_item or None,
                            rif_dis=rif_dis or None,
                            rif_access=rif_access or None,
                            ce=ce or None,
                            mp=mp or None,
                        )
                        items.append(current_item)

                    else:
                        # Righe di continuazione: niente nuova pos, ma Den.Comm / Rag.Soc proseguono
                        if not current_item:
                            continue

                        extra_den = (row[13] or "").strip()
                        if extra_den:
                            current_item.manufacturer_code = (
                                ((current_item.manufacturer_code or "") + " " + extra_den).strip()
                            )

                        extra_rag = (row[14] or "").strip()
                        if extra_rag:
                            current_item.manufacturer = (
                                ((current_item.manufacturer or "") + " " + extra_rag).strip()
                            )

    # Nessun autore/RAM nel PDF → liste vuote / None
    return DocumentoBOM(
        code=code,
        revision=revision,
        doc_date=doc_date,
        title=title,
        pn=pn,
        authors=[],                # il PDF non ha tabella autori nel layout che mi hai mostrato
        ram_number=None,
        ram_validity=None,
        part_list_revisions=[],
        items=items,
        bom_type=bom_type,
        only_released=only_released,
    )


# ======================================================================
# IMPORT DI TUTTI I PDF IN UNA CARTELLA (stessa logica degli Excel)
# ======================================================================

def import_boms_from_pdf_folder(
    folder: str | Path,
    client,
    log=print,
    overwrite: bool = False,
) -> dict:
    """
    Cerca tutti i PDF in `folder` (e sottocartelle), per ognuno:
      - legge la BOM con carica_bom_da_pdf(...)
      - se overwrite=False:
          usa import_or_skip_bom(...) (create-or-skip, come Excel storico)
        se overwrite=True:
          usa import_with_overwrite(...) (create-or-overwrite, come Excel overwrite)

    :param folder: cartella radice con i PDF
    :param client: client Odoo già connesso (il tuo OdooClient della GUI)
    :param log: funzione di logging (es. print o dialog_log.append)
    :param overwrite: se False, non tocca le BOM esistenti (skip);
                      se True, sovrascrive testata + righe delle BOM esistenti
                      con lo stesso P/N.
    :return: dict con riepilogo
             {
                 "imported": int,
                 "skipped": int,
                 "overwritten": int,
                 "errors": int,
             }
    """
    base_dir = Path(folder)

    if not base_dir.is_dir():
        raise FileNotFoundError(f"La cartella PDF non esiste: {base_dir}")

    # cerca tutti i PDF ma tieni solo quelli col nome che contiene "BOM"
    pdf_files = [
        p for p in base_dir.rglob("*.pdf")
        if "BOM" in p.name.upper()
    ]

    stats = {
        "imported": 0,
        "skipped": 0,
        "overwritten": 0,
        "errors": 0,
    }

    if not pdf_files:
        log(f"⚠ Nessun PDF con 'BOM' nel nome trovato in {base_dir}")
        return stats

    log(f"📄 Trovati {len(pdf_files)} PDF candidati (nome contiene 'BOM') in: {base_dir}")
    log(f"⚙️ Modalità overwrite PDF: {'ATTIVA' if overwrite else 'disattivata'}")

    for path in pdf_files:
        log(f"\n=== Elaboro PDF: {path.name} ===")
        try:
            # 1) Leggi il PDF e costruisci DocumentoBOM
            doc = carica_bom_da_pdf(str(path))

            log(f"  CODE:    {doc.code}")
            log(f"  REV:     {doc.revision}")
            log(f"  TITLE:   {doc.title}")
            log(f"  P/N:     {doc.pn}")
            log(f"  # RIGHE: {len(doc.items)}")

            if overwrite:
                # 2a) Import con sovrascrittura (stessa semantica di Excel)
                status, bom_id, line_ids = import_with_overwrite(client, doc, log=log)

                if status == "error":
                    log("  ❌ BOM da PDF non importata per errore.")
                    stats["errors"] += 1
                elif status == "imported":
                    log(f"  ✅ BOM da PDF creata (ID {bom_id}) con {len(line_ids)} righe.")
                    stats["imported"] += 1
                elif status == "overwritten":
                    log(f"  🔄 BOM da PDF sovrascritta (ID {bom_id}) con {len(line_ids)} nuove righe.")
                    stats["overwritten"] += 1
                else:
                    log(f"  ❌ Stato sconosciuto '{status}', conto come errore.")
                    stats["errors"] += 1

            else:
                # 2b) Import "storico" create-or-skip (comportamento precedente)
                bom_id, line_ids = import_or_skip_bom(client, doc, log=log)

                if bom_id is None:
                    log("  ⚠ BOM da PDF non importata (mancano dati essenziali).")
                    stats["errors"] += 1
                elif line_ids:
                    log(f"  ✅ BOM creata da PDF (ID {bom_id}) con {len(line_ids)} righe.")
                    stats["imported"] += 1
                else:
                    log(f"  ⏭ BOM da PDF già presente (ID {bom_id}), nessuna riga creata.")
                    stats["skipped"] += 1

        except Exception as e:  # noqa: BLE001
            log(f"  ❌ Errore durante l'elaborazione del file {path.name}: {e}")
            stats["errors"] += 1

    log("\n=== RIEPILOGO IMPORT PDF ===")
    log(f"  ✅ Nuove BOM da PDF create     : {stats['imported']}")
    log(f"  🔄 BOM da PDF sovrascritte     : {stats['overwritten']}")
    log(f"  ⏭ BOM da PDF già presenti (skip): {stats['skipped']}")
    log(f"  ❌ Errori                      : {stats['errors']}")

    return stats
