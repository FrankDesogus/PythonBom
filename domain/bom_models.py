"""
Dataclass di dominio utilizzate da tutta l'applicazione.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


# ======================================================================
# TESTATA BOM (x_boms)
# ======================================================================

@dataclass
class Bom:
    id: int
    pn: str
    title: str
    x_name: str
    name: str
    revision: str

# ======================================================================
# RIGA BOM (x_bom_line)
# ======================================================================

@dataclass
class BomLine:
    """
    Rappresenta una riga BOM (x_bom_line).

    È pensata per:
    - esplosione (serve tutto: pos, description, refdes, type, ecc.)
    - totalizzazione (qty, internal_code, manufacturer, manufacturer_code)
    """

    id: int
    bom_id: int

    pos: str
    qty: float
    unit: str

    internal_code: str
    description: str

    val: float | None
    rat: float | None
    tol: float | None

    refdesignator: str
    tecn: str
    notes: str

    manufacturer: str
    manufacturer_code: str

    type: str
    rev: str
    access_ref: str
    ce: str
    mp: str

    name: str

# ======================================================================
# TOTALIZZAZIONE (RISULTATO DI BOMExploder)
# ======================================================================

@dataclass
class TotalEntry:
    internal_code: str
    description: str
    qty: float
    unit: str
    manufacturer: str
    manufacturer_code: str
    type: str
    rev: str
    access_ref: str
    ce: str
    mp: str
    notes: str

    def add_quantity(self, q: float) -> None:
        self.qty += q
