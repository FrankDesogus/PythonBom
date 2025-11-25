"""
Modulo che fornisce un wrapper semplice per l'interfaccia XML-RPC di Odoo.

La classe OdooClient gestisce l'autenticazione e fornisce i metodi:
- search
- read
- search_read

Non contiene logica applicativa, solo accesso ai dati.
"""

from __future__ import annotations

import xmlrpc.client
from typing import Any, List, Dict, Optional


class OdooClient:
    """
    Wrapper minimale per le chiamate XML-RPC verso Odoo.

    Esempio:
        client = OdooClient(url, db, username, password)
        products = client.search_read("product.product", [], ["name", "default_code"])
    """

    def __init__(self, url: str, db: str, username: str, password: str) -> None:
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password

        # Autenticazione
        try:
            common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common")
            self.uid = common.authenticate(self.db, self.username, self.password, {})
        except Exception as e:
            raise RuntimeError(f"Errore durante l'autenticazione XML-RPC: {e}")

        if not self.uid:
            raise RuntimeError("Autenticazione Odoo fallita. Verificare credenziali e database.")

        # Proxy per i modelli
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object")

    # ------------------------------------------------------------
    # XML-RPC wrapper methods
    # ------------------------------------------------------------

    def search(self, model: str, domain: List[Any], **kwargs) -> List[int]:
        """Esegue una search Odoo e restituisce una lista di ID."""
        try:
            return self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                model,
                "search",
                [domain],
                kwargs,
            )
        except Exception as e:
            raise RuntimeError(f"Errore Odoo search({model}): {e}")

    def read(
        self,
        model: str,
        ids: List[int],
        fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Legge record Odoo dati gli ID."""
        if not ids:
            return []

        try:
            return self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                model,
                "read",
                [ids],
                {"fields": fields} if fields else {},
            )
        except Exception as e:
            raise RuntimeError(f"Errore Odoo read({model}): {e}")

    def search_read(
        self,
        model: str,
        domain: List[Any],
        fields: Optional[List[str]] = None,
        limit: Optional[int] = None,
        **kwargs,
    ) -> List[Dict[str, Any]]:
        """Combina search + read in un'unica chiamata."""
        params: Dict[str, Any] = {"fields": fields or []}
        if limit is not None:
            params["limit"] = limit
        params.update(kwargs)

        try:
            return self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                model,
                "search_read",
                [domain],
                params,
            )
        except Exception as e:
            raise RuntimeError(f"Errore Odoo search_read({model}): {e}")
    def create(self, model: str, vals: Dict[str, Any]) -> int:
        """
        Crea un record in Odoo.

        È il metodo che usano BomDaExcel/BomDaPdf:
            client.create("x_boms", header_data)
        """
        try:
            new_id = self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                model,
                "create",
                [vals],
            )
            return new_id
        except Exception as e:
            raise RuntimeError(f"Errore Odoo create({model}): {e}")

    def write(self, model: str, ids: List[int], vals: Dict[str, Any]) -> bool:
        """
        Aggiorna uno o più record in Odoo.

        Al momento i tuoi import non lo usano, ma può tornare utile in futuro.
        """
        if not ids:
            return True

        try:
            result = self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                model,
                "write",
                [ids, vals],
            )
            return bool(result)
        except Exception as e:
            raise RuntimeError(f"Errore Odoo write({model}): {e}")

    def unlink(self, model: str, ids: list[int]) -> bool:
        """
        Cancella i record con gli id passati.
        In Odoo unlink restituisce True se l'operazione va a buon fine.
        """
        if not ids:
            return True

        try:
            result = self.models.execute_kw(
                self.db,
                self.uid,
                self.password,
                model,
                "unlink",
                [ids],
            )
            return bool(result)
        except Exception as e:
            raise RuntimeError(f"Errore Odoo unlink({model}): {e}")
