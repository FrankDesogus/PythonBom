"""
MainWindow dell'applicazione Odoo BOM Explorer.

Questa classe contiene SOLO logica UI (PySide6).
Tutta la logica di dominio è delegata a:
- BomRepository
- BomExploder
- ImportService
- export_totals_to_excel
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTreeWidget, QTreeWidgetItem,
    QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QFileDialog,
    QSplitter, QMessageBox, QPlainTextEdit,
    QAbstractItemView
)

import config
from domain.bom_models import Bom, TotalEntry
from services.bom_repository import BomRepository
from services.bom_exploder import BomExploder
from services.import_service import ImportService
from services.export_service import export_totals_to_excel


class MainWindow(QMainWindow):
    """
    UI principale dell'applicazione.
    """

    def __init__(
        self,
        repository: BomRepository,
        exploder: BomExploder,
        import_service: ImportService,
        parent=None
    ):
        super().__init__(parent)

        self.repository = repository
        self.exploder = exploder
        self.import_service = import_service

        # Cache e stato attuale
        self.current_totals: Dict[str, TotalEntry] = {}
        self.selected_folder: Optional[Path] = None

        self.setWindowTitle(config.APP_NAME)
        self.resize(1400, 800)

        self._setup_ui()
        self._load_root_boms()

    # ----------------------------------------------------------------------
    # UI SETUP
    # ----------------------------------------------------------------------

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # --------------------------------------------------------------
        # Barra superiore: pulsanti
        # --------------------------------------------------------------
        top_bar = QHBoxLayout()

        self.btn_reload = QPushButton("Ricarica BOM da Odoo")
        self.btn_reload.clicked.connect(self._load_root_boms)
        top_bar.addWidget(self.btn_reload)

        self.btn_explode = QPushButton("Esplodi BOM selezionata")
        self.btn_explode.clicked.connect(self._on_explode_clicked)
        top_bar.addWidget(self.btn_explode)

        self.btn_choose_folder = QPushButton("Scegli cartella import")
        self.btn_choose_folder.clicked.connect(self._on_choose_folder_clicked)
        top_bar.addWidget(self.btn_choose_folder)

        self.btn_import = QPushButton("Importa BOM da Excel/PDF")
        self.btn_import.clicked.connect(self._on_import_clicked)
        top_bar.addWidget(self.btn_import)

        # 👇 NUOVO PULSANTE PER OVERWRITE
        self.btn_import_overwrite = QPushButton("Sovrascrivi BOM da Excel/PDF")
        self.btn_import_overwrite.clicked.connect(self._on_import_overwrite_clicked)
        top_bar.addWidget(self.btn_import_overwrite)

        self.btn_export = QPushButton("Esporta Totalizzazione Excel")
        self.btn_export.clicked.connect(self._on_export_clicked)
        top_bar.addWidget(self.btn_export)


        main_layout.addLayout(top_bar)

        # --------------------------------------------------------------
        # Campo di ricerca per le root BOM
        # --------------------------------------------------------------
        search_bar = QHBoxLayout()
        search_bar.addWidget(QLabel("Filtra P/N:"))
        self.search_box = QLineEdit()
        self.search_box.textChanged.connect(self._on_search_text_changed)
        search_bar.addWidget(self.search_box)
        main_layout.addLayout(search_bar)

        # --------------------------------------------------------------
        # Splitter centrale: tabella BOM | albero esploso
        # --------------------------------------------------------------
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter, 1)

        # Tabella BOM radice
        self.table_boms = QTableWidget()
        self.table_boms.setColumnCount(3)
        self.table_boms.setHorizontalHeaderLabels(["P/N", "Titolo", "REV."])
        self.table_boms.horizontalHeader().setStretchLastSection(True)
        self.table_boms.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_boms.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table_boms.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.table_boms.itemSelectionChanged.connect(self._on_bom_selection_changed)
        self.table_boms.itemDoubleClicked.connect(self._on_bom_double_clicked)
        splitter.addWidget(self.table_boms)

        # Albero esploso
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            "Pos",
            "Codice Interno",
            "Descrizione",
            "Q.tà",
            "UM",
            "Manufacturer",
            "Codice Produttore",
            "Ref.Des",
            "Note",
            "Tipo",
            "Rev",
            "Access Ref",
            "CE",
            "MP",
        ])
        splitter.addWidget(self.tree)

        # --------------------------------------------------------------
        # Tabella totalizzazione
        # --------------------------------------------------------------
        self.table_totals = QTableWidget()
        self.table_totals.setColumnCount(6)
        self.table_totals.setHorizontalHeaderLabels([
            "Codice Interno",
            "Descrizione",
            "Quantità",
            "UM",
            "Manufacturer",
            "Codice Produttore",
        ])
        self.table_totals.horizontalHeader().setStretchLastSection(True)
        main_layout.addWidget(self.table_totals)


        # --------------------------------------------------------------
        # Log
        # --------------------------------------------------------------
        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.table_totals.setEditTriggers(QAbstractItemView.NoEditTriggers)

        main_layout.addWidget(self.log_box, 1)

    # ----------------------------------------------------------------------
    # LOG HELPER
    # ----------------------------------------------------------------------

    def append_log(self, msg: str):
        self.log_box.appendPlainText(msg)
        self.log_box.verticalScrollBar().setValue(
            self.log_box.verticalScrollBar().maximum()
        )

    # ----------------------------------------------------------------------
    # CARICAMENTO ROOT BOM
    # ----------------------------------------------------------------------

    def _load_root_boms(self):
        self.append_log("🔄 Caricamento BOM da Odoo...")
        try:
            self.repository.load_all()
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore nel caricamento Odoo:\n{e}")
            return

        boms = self.repository.get_root_boms()
        self._populate_bom_table(boms)
        self.append_log(f"✔ Caricate {len(boms)} BOM radice.")

    def _populate_bom_table(self, boms):
        self.table_boms.clearContents()
        self.table_boms.setRowCount(len(boms))

        for row, bom in enumerate(boms):
            pn_item = QTableWidgetItem(bom.pn)
            pn_item.setData(Qt.UserRole, bom.id)
            self.table_boms.setItem(row, 0, pn_item)
            self.table_boms.setItem(row, 1, QTableWidgetItem(bom.title))
            self.table_boms.setItem(row, 2, QTableWidgetItem(bom.revision))
    # ----------------------------------------------------------------------
    # FILTRO RICERCA
    # ----------------------------------------------------------------------

    def _on_search_text_changed(self, text: str):
        text = text.lower().strip()
        all_boms = self.repository.get_root_boms()

        if not text:
            filtered = all_boms
        else:
            filtered = [
                b for b in all_boms
                if text in (b.pn or "").lower()
                or text in (b.title or "").lower()
                or text in (b.revision or "").lower()
            ]

        self._populate_bom_table(filtered)


    # ----------------------------------------------------------------------
    # SELEZIONE BOM TABELLA
    # ----------------------------------------------------------------------

    def _on_bom_selection_changed(self):
        # Non esplodiamo nulla qui, solo logghiamo
        bom = self._get_selected_bom()
        if bom:
            self.append_log(f"Selezionata BOM: {bom.pn}")
    def _on_bom_double_clicked(self, item: QTableWidgetItem):
        """
        Doppio click su una riga della tabella BOM → esplodi direttamente.
        L'item cliccato può essere P/N o Titolo, ma la selezione è per riga.
        """
        # ci basta chiamare la stessa logica del bottone "Esplodi BOM selezionata"
        self._on_explode_clicked()

    def _get_selected_bom(self) -> Optional[Bom]:
        # Con SelectRows + SingleSelection basta la riga corrente
        row = self.table_boms.currentRow()
        if row < 0:
            return None

        pn_item = self.table_boms.item(row, 0)
        if pn_item is None:
            return None

        bom_id = pn_item.data(Qt.UserRole)
        if bom_id is None:
            return None

        return self.repository.get_bom_by_id(int(bom_id))

    # ----------------------------------------------------------------------
    # ESPLOSIONE BOM
    # ----------------------------------------------------------------------

    def _on_explode_clicked(self):
        bom = self._get_selected_bom()
        if not bom:
            QMessageBox.warning(self, "Attenzione", "Seleziona una BOM nella tabella.")
            return

        self.append_log(f"🔍 Esplosione BOM: {bom.pn}")

        try:
            tree_dict, totals = self.exploder.explode_bom(
                root_bom=bom,
                get_lines_for_bom=self.repository.get_lines_for_bom,
                get_bom_by_code=self.repository.get_bom_by_code,
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Errore durante esplosione:\n{e}")
            return

        self.current_totals = totals

        self._populate_tree(tree_dict)
        self._populate_totals_table(totals)

        self.append_log(f"✔ Esplosione completata. {len(totals)} codici totalizzati.")

    # ----------------------------------------------------------------------
    # POPOLA TREE
    # ----------------------------------------------------------------------

    def _populate_tree(self, node_dict: Dict[str, Any]):
        self.tree.clear()

        root_item = self._create_tree_item(node_dict)
        self.tree.addTopLevelItem(root_item)
        self.tree.expandAll()

    def _create_tree_item(self, node_dict: Dict[str, Any]) -> QTreeWidgetItem:
        item = QTreeWidgetItem([
            node_dict.get("pos", ""),
            node_dict.get("internal_code", ""),
            node_dict.get("description", ""),
            str(node_dict.get("qty", "")),
            node_dict.get("unit", ""),
            node_dict.get("manufacturer", ""),
            node_dict.get("manufacturer_code", ""),
            node_dict.get("refdes", ""),
            node_dict.get("notes", ""),
            node_dict.get("type", ""),
            node_dict.get("rev", ""),
            node_dict.get("access_ref", ""),
            node_dict.get("ce", ""),
            node_dict.get("mp", ""),
        ])
        for child in node_dict.get("children", []):
            item.addChild(self._create_tree_item(child))
        return item



    # ----------------------------------------------------------------------
    # POPOLA TOTALS TABLE
    # ----------------------------------------------------------------------

    def _populate_totals_table(self, totals: Dict[str, TotalEntry]):
        self.table_totals.clearContents()
        self.table_totals.setRowCount(len(totals))

        for row, (_, entry) in enumerate(totals.items()):
            self.table_totals.setItem(row, 0, QTableWidgetItem(entry.internal_code))
            self.table_totals.setItem(row, 1, QTableWidgetItem(entry.description))
            self.table_totals.setItem(row, 2, QTableWidgetItem(str(entry.qty)))
            self.table_totals.setItem(row, 3, QTableWidgetItem(entry.unit))
            self.table_totals.setItem(row, 4, QTableWidgetItem(entry.manufacturer))
            self.table_totals.setItem(row, 5, QTableWidgetItem(entry.manufacturer_code))

    # ----------------------------------------------------------------------
    # IMPORT
    # ----------------------------------------------------------------------

    def _on_choose_folder_clicked(self):
        folder = QFileDialog.getExistingDirectory(self, "Seleziona cartella import")
        if folder:
            self.selected_folder = Path(folder)
            self.append_log(f"📁 Cartella selezionata: {self.selected_folder}")

    def _on_import_clicked(self):
        """
        Import "normale": create-or-skip.
        Non modifica le BOM esistenti, si limita a creare BOM nuove.
        """
        if not self.selected_folder:
            QMessageBox.warning(self, "Attenzione", "Seleziona una cartella prima.")
            return

        try:
            summary = self.import_service.import_from_folder(
                self.selected_folder,
                log_callback=self.append_log,
                overwrite=False,  # modalità standard: non sovrascrive
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore import", str(e))
            return

        total = summary["total"]
        self.append_log(
            "Import completato (modalità normale): "
            f"{total['imported']} nuove, "
            f"{total['overwritten']} sovrascritte, "
            f"{total['skipped']} saltate, "
            f"{total['errors']} errori."
        )
        # Ricarichiamo root BOM
        self._load_root_boms()


    # ----------------------------------------------------------------------
    # EXPORT
    # ----------------------------------------------------------------------

    def _on_export_clicked(self):
        if not self.current_totals:
            QMessageBox.warning(self, "Attenzione", "Nessuna totalizzazione da esportare.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Esporta Excel",
            "totalizzazione.xlsx",
            "Excel (*.xlsx)"
        )
        if not path:
            return

        try:
            export_totals_to_excel(self.current_totals, path)
        except Exception as e:
            QMessageBox.critical(self, "Errore export", str(e))
            return

        QMessageBox.information(self, "Esportazione", "File Excel esportato con successo!")
        self.append_log(f"📤 File esportato: {path}")

    def _on_import_overwrite_clicked(self):
        """
        Import delle BOM con sovrascrittura delle BOM esistenti (stesso P/N).
        Usa la modalità overwrite=True nell'ImportService.
        """
        if not self.selected_folder:
            QMessageBox.warning(self, "Attenzione", "Seleziona una cartella prima.")
            return

        # Conferma di sicurezza
        reply = QMessageBox.question(
            self,
            "Conferma sovrascrittura BOM",
            (
                "ATTENZIONE:\n"
                "Le BOM esistenti in Odoo con lo stesso P/N dei file Excel/PDF\n"
                "verranno SOVRASCRITTE.\n\n"
                "Per ogni P/N già presente in Odoo verrà effettuato:\n"
                "  • aggiornamento della testata (x_boms)\n"
                "  • cancellazione di tutte le righe (x_bom_line) esistenti\n"
                "  • creazione di nuove righe dai documenti importati\n\n"
                "Vuoi continuare?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if reply != QMessageBox.Yes:
            self.append_log("Sovrascrittura BOM annullata dall'utente.")
            return

        self.append_log(
            f"🚨 Avvio import con SOVRASCRITTURA dalla cartella: {self.selected_folder}"
        )

        try:
            summary = self.import_service.import_from_folder(
                self.selected_folder,
                log_callback=self.append_log,
                overwrite=True,  # 👈 qui abilitiamo la sovrascrittura
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore import (sovrascrittura)", str(e))
            self.append_log(f"[ERRORE] Import con sovrascrittura fallito: {e}")
            return

        total = summary["total"]
        self.append_log(
            "Import con SOVRASCRITTURA completato: "
            f"{total['imported']} nuove, "
            f"{total['overwritten']} sovrascritte, "
            f"{total['skipped']} saltate, "
            f"{total['errors']} errori."
        )

        # Ricarichiamo root BOM per vedere subito gli effetti delle modifiche
        self._load_root_boms()
