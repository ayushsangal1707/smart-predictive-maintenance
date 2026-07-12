"""
Project-wide constants. Kept here (rather than duplicated per-app) so every
app references the same source of truth for role names.
"""

ROLE_ADMIN = "ADMIN"
ROLE_ENGINEER = "ENGINEER"
ROLE_MANAGER = "MANAGER"

ROLE_CHOICES = [
    (ROLE_ADMIN, "Admin"),
    (ROLE_ENGINEER, "Engineer"),
    (ROLE_MANAGER, "Manager"),
]

# Roles allowed to access admin-only views/actions (e.g. retraining models,
# managing users) via the has_role() helper / role_required decorator.
ADMIN_ONLY_ROLES = [ROLE_ADMIN]

# ---------------------------------------------------------------------------
# Machine Management constants
# ---------------------------------------------------------------------------

STATUS_ACTIVE = "ACTIVE"
STATUS_MAINTENANCE = "UNDER_MAINTENANCE"
STATUS_INACTIVE = "INACTIVE"
STATUS_DECOMMISSIONED = "DECOMMISSIONED"

MACHINE_STATUS_CHOICES = [
    (STATUS_ACTIVE, "Active"),
    (STATUS_MAINTENANCE, "Under Maintenance"),
    (STATUS_INACTIVE, "Inactive"),
    (STATUS_DECOMMISSIONED, "Decommissioned"),
]

# Bootstrap badge color per status, used in templates via a dict lookup.
MACHINE_STATUS_BADGE_CLASS = {
    STATUS_ACTIVE: "bg-success",
    STATUS_MAINTENANCE: "bg-warning text-dark",
    STATUS_INACTIVE: "bg-secondary",
    STATUS_DECOMMISSIONED: "bg-danger",
}

MACHINE_TYPE_CHOICES = [
    ("TURBINE", "Turbine"),
    ("MOTOR", "Motor"),
    ("PUMP", "Pump"),
    ("BOILER", "Boiler"),
    ("TRANSFORMER", "Transformer"),
    ("COMPRESSOR", "Compressor"),
    ("GENERATOR", "Generator"),
    ("OTHER", "Other"),
]

# Kept as a plain choices list (not a DB-backed model) since BHEL departments
# are a small, slow-changing set — a full Department model/table would be
# unnecessary complexity for this project's scope. Can be promoted to a
# model later without changing the rest of the app if departments need to
# be managed dynamically by an Admin.
DEPARTMENT_CHOICES = [
    ("BOILER_PLANT", "Boiler Plant"),
    ("TURBINE_PLANT", "Turbine Plant"),
    ("ELECTRICAL", "Electrical"),
    ("FABRICATION", "Fabrication"),
    ("QUALITY_CONTROL", "Quality Control"),
    ("MAINTENANCE", "Maintenance"),
    ("R_AND_D", "R&D"),
    ("OTHER", "Other"),
]
