#!/usr/bin/env python3
"""
Aura Cleaning Solutions Data Mart - Database Migration Runner CLI
=============================================================================
Authoritative entry point for applying versioned database migrations.

Usage:
    python database/run_migrations.py [--engine mysql|sqlite]

Behavior:
    - Reads migrations in forward alphanumeric order from database/migrations/
    - Verifies SHA-256 cryptographic checksums of previously applied migrations
    - Safely handles failed migration retries via upsert into _schema_migrations
    - Outputs migration execution progress and timing
"""

import argparse
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.database import (
    ConfigurationError,
    DatabaseManager,
    MigrationChecksumError,
    MigrationExecutionError,
    get_db_manager,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("aura_data_mart.migrations")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Aura Cleaning Solutions Data Mart - Migration Runner"
    )
    parser.add_argument(
        "--engine",
        choices=["mysql", "sqlite"],
        default=None,
        help="Target database engine (defaults to DB_ENGINE in .env)",
    )
    args = parser.parse_args()

    try:
        mgr = get_db_manager(engine_type=args.engine)
        print(f"============================================================")
        print(f" Aura Cleaning Solutions Data Mart - Migration Pipeline")
        print(f" Engine: {mgr.engine_type.upper()}")
        print(f"============================================================")

        applied = mgr.run_migrations()

        if applied:
            print(f"\nSuccessfully applied {len(applied)} migration(s):")
            for ver in applied:
                print(f"  [APPLIED] {ver}")
        else:
            print("\nDatabase schema is up to date. No pending migrations.")

        print(f"============================================================\n")
        return 0

    except ConfigurationError as e:
        logger.error(f"Database Configuration Error: {e}")
        return 1
    except MigrationChecksumError as e:
        logger.error(f"CRITICAL: Schema Tampering / Checksum Mismatch: {e}")
        return 2
    except MigrationExecutionError as e:
        logger.error(f"Migration Execution Failed: {e}")
        return 3
    except Exception as e:
        logger.error(f"Unexpected error during migration execution: {e}", exc_info=True)
        return 4


if __name__ == "__main__":
    sys.exit(main())
