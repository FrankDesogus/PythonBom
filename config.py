"""
Configurazione centralizzata dell'applicazione.
"""

# ==============================================
# CONFIGURAZIONE ODOO
# ==============================================

ODOO_URL: str = "https://elthub-preproduzione.odoo.com"
ODOO_DB: str = "elthub-preproduzione"
ODOO_USERNAME: str = "odooadmin@elthub.it"
ODOO_PASSWORD: str = "4dm1nasdzxc2121!"

# ==============================================
# MODEL NAMES
# ==============================================

MODEL_BOM = "x_boms"
MODEL_BOM_LINE = "x_bom_line"

# ==============================================
# CAMPI ODOO (NOMI CORRETTI)
# ==============================================

# BOM (x_boms)
FIELD_BOM_PN = "x_studio_x_pn"
FIELD_BOM_TITLE = "x_studio_x_titolo"
FIELD_BOM_X_NAME = "x_studio_x_name"
FIELD_BOM_NAME = "x_name"
FIELD_BOM_REVISION = "x_studio_x_revision"

# BOM Line (x_bom_line)
FIELD_LINE_BOM = "x_studio_x_boms_id"          # many2one verso x_boms
FIELD_LINE_POS = "x_studio_x_pos"
FIELD_LINE_QTY = "x_studio_x_qty"
FIELD_LINE_UNIT = "x_studio_x_um"
FIELD_LINE_INTERNAL_CODE = "x_studio_x_internal_code"
FIELD_LINE_DESCRIPTION = "x_studio_x_description"
FIELD_LINE_VAL = "x_studio_x_val"
FIELD_LINE_RAT = "x_studio_x_rat"
FIELD_LINE_TOL = "x_studio_x_tol"
FIELD_LINE_REFDES = "x_studio_x_refdesignator"
FIELD_LINE_TECN = "x_studio_x_tecn"
FIELD_LINE_NOTES = "x_studio_x_notes"
FIELD_LINE_MANUFACTURER = "x_studio_x_manufacturer"
FIELD_LINE_MANUFACTURER_CODE = "x_studio_x_manufacturer_code"
FIELD_LINE_TYPE = "x_studio_x_type"
FIELD_LINE_REV = "x_studio_x_rev"
FIELD_LINE_ACCESS_REF = "x_studio_x_access_ref"
FIELD_LINE_CE = "x_studio_x_ce"
FIELD_LINE_MP = "x_studio_x_mp"
FIELD_LINE_NAME = "x_name"


# ==============================================
# ALTRE COSTANTI
# ==============================================

APP_NAME = "Odoo BOM Explorer"
