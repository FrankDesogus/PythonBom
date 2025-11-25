"""
Entrypoint dell'applicazione Odoo BOM Explorer.

Crea:
- QApplication
- OdooClient
- BomRepository
- BomExploder
- ImportService
- MainWindow

e avvia il loop dell'interfaccia grafica.
"""

from __future__ import annotations

import sys
from PySide6.QtWidgets import QApplication, QMessageBox

import config
from odoo_client import OdooClient
from services.bom_repository import BomRepository
from services.bom_exploder import BomExploder
from services.import_service import ImportService
from ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)

    # ------------------------------------------------------------
    # Connessione a Odoo
    # ------------------------------------------------------------
    try:
        client = OdooClient(
            config.ODOO_URL,
            config.ODOO_DB,
            config.ODOO_USERNAME,
            config.ODOO_PASSWORD,
        )
    except Exception as e:
        QMessageBox.critical(None, "Errore Odoo", f"Errore di connessione/autenticazione:\n{e}")
        return 1

    # ------------------------------------------------------------
    # Creazione servizi e repository
    # ------------------------------------------------------------
    repository = BomRepository(client)
    exploder = BomExploder()
    import_service = ImportService(client)

    # ------------------------------------------------------------
    # Finestra principale
    # ------------------------------------------------------------
    win = MainWindow(
        repository=repository,
        exploder=exploder,
        import_service=import_service,
    )
    win.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
