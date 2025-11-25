from __future__ import annotations

from pathlib import Path
from typing import Callable, Dict, Any

from odoo_client import OdooClient
from functions.BomDaExcel import import_boms_from_folder as import_boms_from_excel_folder
from functions.BomDaPdf import import_boms_from_pdf_folder


class ImportService:
    """
    Servizio che coordina l'import di BOM da Excel e PDF.

    Non contiene logica di parsing: delega tutto a BomDaExcel/BomDaPdf.
    Qui:
      - gestiamo log
      - unifichiamo i risultati
      - gestiamo overwrite
    """

    def __init__(self, client: OdooClient) -> None:
        self.client = client

    # ------------------------------------------------------------------
    # IMPORTER UNIFICATO
    # ------------------------------------------------------------------
    def import_from_folder(
            self,
            folder_path: str | Path,
            log_callback: Callable[[str], Any] | None = None,
            overwrite: bool = False,
    ) -> Dict[str, Dict[str, int]]:
        """
        Importa BOM da una cartella supportando:
            - Excel
            - PDF
            - modalità overwrite (True/False)

        Ritorna un riepilogo del tipo:
            {
                "excel": {...},
                "pdf": {...},
                "total": {
                    "imported": int,
                    "overwritten": int,
                    "skipped": int,
                    "errors": int
                }
            }
        """
        folder = Path(folder_path)
        if not folder.exists() or not folder.is_dir():
            raise ValueError(f"La cartella '{folder}' non esiste o non è una directory.")

        # Wrapper log
        def log(msg: str):
            if log_callback:
                log_callback(msg)

        log(f"📁 Avvio import da cartella: {folder}")
        log(f"🔧 Modalità overwrite: {'ATTIVA' if overwrite else 'disattivata'}")

        # --------------------------------------------------------------
        # IMPORT EXCEL
        # --------------------------------------------------------------
        log("📄 Import da Excel in corso...")
        try:
            excel_result = import_boms_from_excel_folder(
                folder,
                self.client,
                log=log,
                overwrite=overwrite,
            )
        except Exception as e:
            raise RuntimeError(f"Errore durante import Excel: {e}")

        # --------------------------------------------------------------
        # IMPORT PDF
        # --------------------------------------------------------------
        log("📄 Import da PDF in corso...")
        try:
            pdf_result = import_boms_from_pdf_folder(
                folder,
                self.client,
                log=log,
                overwrite=overwrite,
            )
        except Exception as e:
            raise RuntimeError(f"Errore durante import PDF: {e}")

        # --------------------------------------------------------------
        # COMBINAZIONE RISULTATI
        # --------------------------------------------------------------
        total = {
            "imported": excel_result.get("imported", 0) + pdf_result.get("imported", 0),
            "overwritten": excel_result.get("overwritten", 0) + pdf_result.get("overwritten", 0),
            "skipped": excel_result.get("skipped", 0) + pdf_result.get("skipped", 0),
            "errors": excel_result.get("errors", 0) + pdf_result.get("errors", 0),
        }

        # --------------------------------------------------------------
        # LOG DI CHIUSURA
        # --------------------------------------------------------------
        log("\n=== RIEPILOGO IMPORT COMPLESSIVO ===")
        log(f"  Excel: {excel_result}")
        log(f"  PDF  : {pdf_result}")
        log(
            f"  Totale: "
            f"{total['imported']} nuove, "
            f"{total['overwritten']} sovrascritte, "
            f"{total['skipped']} saltate, "
            f"{total['errors']} errori."
        )

        return {
            "excel": excel_result,
            "pdf": pdf_result,
            "total": total,
        }
