"""
Aura Cleaning Solutions Data Mart - Project Settings & Canonical Taxonomy
=============================================================================
Defines system paths, environment variable defaults, service portfolio taxonomies,
and expense categorization rules.
"""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Data Pipeline Paths
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
REJECTED_DATA_DIR = DATA_DIR / "rejected"

# Database Scripts Path
DATABASE_DIR = BASE_DIR / "database"

# Audit & Reporting Paths
REPORTS_DIR = BASE_DIR / "reports"
DATA_QUALITY_REPORTS_DIR = REPORTS_DIR / "data_quality_report"
ETL_LOGS_DIR = REPORTS_DIR / "etl_logs"

# Ensure all operational directories exist
for directory in [
    RAW_DATA_DIR,
    PROCESSED_DATA_DIR,
    REJECTED_DATA_DIR,
    DATA_QUALITY_REPORTS_DIR,
    ETL_LOGS_DIR,
]:
    directory.mkdir(parents=True, exist_ok=True)


# =============================================================================
# Database Configuration Loader (Reads Environment or .env)
# =============================================================================
def load_env_file(filepath: Path = BASE_DIR / ".env") -> dict:
    """Simple parser for .env files without requiring external python-dotenv."""
    env_vars = {}
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    env_vars[key.strip()] = val.strip().strip("'\"")
    return env_vars


_env_file_vars = load_env_file()

DB_ENGINE = os.environ.get("DB_ENGINE", _env_file_vars.get("DB_ENGINE", "mysql")).lower()

MYSQL_HOST = os.environ.get("MYSQL_HOST", _env_file_vars.get("MYSQL_HOST", "localhost"))
MYSQL_PORT = int(os.environ.get("MYSQL_PORT", _env_file_vars.get("MYSQL_PORT", 3306)))
MYSQL_DATABASE = os.environ.get("MYSQL_DATABASE", _env_file_vars.get("MYSQL_DATABASE", "aura_data_mart"))
MYSQL_USER = os.environ.get("MYSQL_USER", _env_file_vars.get("MYSQL_USER", "root"))
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", _env_file_vars.get("MYSQL_PASSWORD", ""))

SQLITE_DB_PATH = Path(
    os.environ.get(
        "SQLITE_DB_PATH",
        _env_file_vars.get("SQLITE_DB_PATH", str(DATABASE_DIR / "aura_data_mart_test.db")),
    )
)

LOG_LEVEL = os.environ.get("LOG_LEVEL", _env_file_vars.get("LOG_LEVEL", "INFO")).upper()


# =============================================================================
# Canonical Service Portfolio (Aura's 7 Core Service Categories)
# =============================================================================
CANONICAL_SERVICE_CATEGORIES = [
    "Residential Cleaning",
    "Commercial Cleaning",
    "Sofa & Upholstery Cleaning",
    "Carpet Cleaning",
    "Pest Control & Fumigation",
    "Post-Construction Cleaning",
    "Laundry Services",
]

# Configurable keyword mapping dictionary for raw service descriptions
SERVICE_TAXONOMY_RULES = {
    "Residential Cleaning": [
        "residential",
        "home",
        "house",
        "apartment",
        "domestic",
        "move-in",
        "move-out",
        "tenancy",
        "kitchen deep",
    ],
    "Commercial Cleaning": [
        "commercial",
        "office",
        "corporate",
        "floor scrubbing",
        "buffing",
        "stripping",
        "warehouse",
        "retail",
        "clinic",
    ],
    "Sofa & Upholstery Cleaning": [
        "sofa",
        "couch",
        "upholstery",
        "cushion",
        "armchair",
        "mattress",
        "fabric seat",
        "leather seat",
        "dining chair",
    ],
    "Carpet Cleaning": [
        "carpet",
        "rug",
        "wall-to-wall",
        "area rug",
        "mat extraction",
    ],
    "Pest Control & Fumigation": [
        "fumigation",
        "pest control",
        "bedbug",
        "cockroach",
        "termite",
        "rodent",
        "mosquito",
        "insecticide",
    ],
    "Post-Construction Cleaning": [
        "post-construction",
        "post construction",
        "after build",
        "renovation",
        "cement residue",
        "paint scraping",
        "site clean",
    ],
    "Laundry Services": [
        "laundry",
        "linen",
        "curtains",
        "drapes",
        "wash & press",
        "dry clean",
        "duvet",
        "bedsheet",
    ],
}


# =============================================================================
# Canonical Direct Expense Categories
# =============================================================================
CANONICAL_EXPENSE_CATEGORIES = [
    "Labour Wages",
    "Transport & Fuel",
    "Cleaning Materials & Chemicals",
    "Equipment Maintenance & Rentals",
    "Subcontractor Fees",
    "Other Direct Expenses",
]

EXPENSE_TAXONOMY_RULES = {
    "Labour Wages": [
        "labour",
        "labor",
        "wage",
        "wages",
        "casual",
        "technician allowance",
        "overtime",
        "helper",
        "cleaner pay",
    ],
    "Transport & Fuel": [
        "fuel",
        "petrol",
        "diesel",
        "transport",
        "fare",
        "boda",
        "uber",
        "vehicle",
        "van hire",
        "toll",
    ],
    "Cleaning Materials & Chemicals": [
        "chemical",
        "detergent",
        "soap",
        "shampoo",
        "bleach",
        "degreaser",
        "pads",
        "gloves",
        "masks",
        "mop",
        "sponge",
    ],
    "Equipment Maintenance & Rentals": [
        "rental",
        "generator hire",
        "machine repair",
        "pressure washer",
        "scrubber rental",
        "vacuum servicing",
    ],
    "Subcontractor Fees": [
        "subcontractor",
        "specialist",
        "outsourced",
        "external technician",
    ],
}
