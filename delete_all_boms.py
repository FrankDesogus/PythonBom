import xmlrpc.client

# ==========================================================
# CONFIGURAZIONE ODOO (già impostata con i tuoi dati)
# ==========================================================
ODOO_URL: str = "https://elthub-preproduzione.odoo.com"
ODOO_DB: str = "elthub-preproduzione"
ODOO_USERNAME: str = "odooadmin@elthub.it"
ODOO_PASSWORD: str = "4dm1nasdzxc2121!"
ASK_CONFIRMATION: bool = True   # metti False se vuoi saltare la conferma


# ==========================================================
# CLIENT ODOO XML-RPC
# ==========================================================
class OdooClient:
    def __init__(self, url, db, username, password):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password

        self.uid = None
        self.common = None
        self.models = None

    def authenticate(self):
        """Autentica l'utente su Odoo."""
        try:
            self.common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

            self.uid = self.common.authenticate(
                self.db, self.username, self.password, {}
            )
            if not self.uid:
                print("[Odoo] ERRORE: autenticazione fallita.")
                return False

            print(f"[Odoo] Autenticazione OK (uid={self.uid})")
            return True

        except Exception as e:
            print(f"[Odoo] ERRORE: {e}")
            return False

    def is_authenticated(self):
        return self.uid is not None and self.models is not None

    # ----------------------------------------------------------
    # GENERICO: elimina tutti i record di un modello Odoo
    # ----------------------------------------------------------
    def delete_all_records(self, model_name: str):
        if not self.is_authenticated():
            print(f"[Odoo] ERRORE: non autenticato (delete_all_records {model_name})")
            return False, 0

        try:
            # dominio vuoto = tutti i record
            domain = []  # <-- QUI LA CORREZIONE: dominio vuoto, NON [[]]
            ids = self.models.execute_kw(
                self.db, self.uid, self.password,
                model_name, "search", [domain]  # <-- [domain] = [[]] sul wire, ma corretto
            )
        except Exception as e:
            print(f"[Odoo] ERRORE search({model_name}): {e}")
            return False, 0

        if not ids:
            print(f"[Odoo] Nessun record da cancellare in {model_name}.")
            return True, 0

        try:
            res = self.models.execute_kw(
                self.db, self.uid, self.password,
                model_name, "unlink", [ids]
            )
            if res:
                print(f"[Odoo] Cancellati {len(ids)} record da {model_name}.")
                return True, len(ids)
            else:
                print(f"[Odoo] ERRORE unlink({model_name}) -> False")
                return False, 0

        except Exception as e:
            print(f"[Odoo] ERRORE unlink({model_name}): {e}")
            return False, 0

    # ----------------------------------------------------------
    # SPECIFICO: elimina BOM + BOMLINE
    # ----------------------------------------------------------
    def delete_all_boms_and_lines(self):
        print("\n=== INIZIO ELIMINAZIONE BOM SU ODOO ===\n")

        # 1) BOMLINE
        ok1, n1 = self.delete_all_records("x_bom_line")
        if not ok1:
            print("[FALLITO] Errore nella cancellazione di x_bom_line\n")
            return False

        # 2) BOMS
        ok2, n2 = self.delete_all_records("x_boms")
        if not ok2:
            print("[FALLITO] Errore nella cancellazione di x_boms\n")
            return False

        print(f"\n=== COMPLETATO ===")
        print(f"Righe BOM eliminate: {n1}")
        print(f"BOM eliminate: {n2}\n")

        return True


# ==========================================================
# SCRIPT PRINCIPALE
# ==========================================================
def main():
    print("=======================================================")
    print("      ELIMINAZIONE COMPLETA BOM DA ODOO")
    print("=======================================================\n")
    print(f"URL: {ODOO_URL}")
    print(f"DB : {ODOO_DB}")
    print(f"USER: {ODOO_USERNAME}\n")

    client = OdooClient(ODOO_URL, ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD)

    if not client.authenticate():
        print("ERRORE: impossibile autenticarsi. Interrotto.")
        return

    # Conferma opzionale
    if ASK_CONFIRMATION:
        print("ATTENZIONE: questa operazione ELIMINA TUTTE LE BOM e TUTTE LE BOMLINE dal database Odoo!")
        print("È IRREVERSIBILE.")
        answer = input("Scrivi SI per proseguire: ")

        if answer.strip().upper() != "SI":
            print("Operazione ANNULLATA.\n")
            return

    # Eseguo eliminazione
    success = client.delete_all_boms_and_lines()

    if success:
        print("[OK] Tutte le BOM e le BOMLINE sono state eliminate correttamente.")
    else:
        print("[ERRORE] Eliminazione non riuscita.")


if __name__ == "__main__":
    main()
