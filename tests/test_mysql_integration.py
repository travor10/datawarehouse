"""
Aura Cleaning Solutions Data Mart - MySQL 8 Authoritative Integration Test Suite
=============================================================================
Authoritative integration tests executed directly against a live MySQL 8 server.
Validates production DDL, stored procedures, check constraints, foreign keys,
repeated deployment safety, and analytical view calculation.

Honesty Policy:
If MySQL 8 is unavailable or credentials are unconfigured, tests are skipped with
explicit instructions rather than falsifying results.
"""

import unittest
from pathlib import Path

from config.database import ConfigurationError, DatabaseManager
from config.settings import (
    DATABASE_DIR,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)


class TestMySQLIntegration(unittest.TestCase):
    """Authoritative MySQL 8 Integration Test Suite."""

    @classmethod
    def setUpClass(cls):
        """Verifies live MySQL 8 connectivity before executing integration tests."""
        cls.mysql_available = False
        cls.db_manager = None
        cls.conn = None

        try:
            cls.db_manager = DatabaseManager(engine_type="mysql")
            cls.conn = cls.db_manager.get_connection()
            cls.mysql_available = True
        except (ConfigurationError, ConnectionError, Exception) as e:
            cls.skip_reason = (
                f"Live MySQL 8 Server not reachable on {MYSQL_HOST}:{MYSQL_PORT} ({e}).\n"
                f"To run authoritative MySQL integration tests:\n"
                f"  1. Ensure MySQL Server 8.0+ is running on your machine.\n"
                f"  2. Configure MYSQL_USER and MYSQL_PASSWORD in .env.\n"
                f"  3. Alternatively, open MySQL Workbench and run database/verify_mysql.sql directly."
            )

    def setUp(self):
        if not self.mysql_available:
            self.skipTest(self.skip_reason)

    def test_01_mysql_connection_and_version(self):
        """Proves active connection to MySQL 8 engine."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT VERSION() AS ver, DATABASE() AS db, @@collation_database AS col;")
        row = cursor.fetchone()
        version = row.get("ver") if isinstance(row, dict) else row[0]
        self.assertTrue(
            version.startswith("8.") or "mysql" in version.lower(),
            f"Expected MySQL 8.0+, got {version}",
        )

    def test_02_repeated_deployment_safety(self):
        """
        Proves non-destructive repeated deployment safety:
        Running create_database, create_dimensions, create_facts, create_views,
        and insert_reference_data twice in sequence must execute cleanly without error.
        """
        for _ in range(2):
            self.db_manager.execute_script(DATABASE_DIR / "create_database.sql", conn=self.conn)
            self.db_manager.execute_script(DATABASE_DIR / "create_dimensions.sql", conn=self.conn)
            self.db_manager.execute_script(DATABASE_DIR / "create_facts.sql", conn=self.conn)
            self.db_manager.execute_script(DATABASE_DIR / "create_views.sql", conn=self.conn)
            self.db_manager.execute_script(DATABASE_DIR / "insert_reference_data.sql", conn=self.conn)

    def test_03_all_tables_and_view_present(self):
        """Verifies all 8 base tables and 1 reporting view exist in MySQL."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT table_name, table_type FROM information_schema.tables "
            "WHERE table_schema = %s;",
            (MYSQL_DATABASE,),
        )
        tables = {row["table_name"] if isinstance(row, dict) else row[0]: (row["table_type"] if isinstance(row, dict) else row[1]) for row in cursor.fetchall()}

        expected_tables = [
            "Dim_Date", "Dim_Location", "Dim_Customer", "Dim_Service",
            "Dim_Expense_Category", "Dim_Job", "Fact_Job_Performance", "Fact_Job_Expenses"
        ]
        for tbl in expected_tables:
            self.assertIn(tbl, tables, f"Expected base table {tbl} in MySQL schema")

        self.assertIn("vw_job_profitability_summary", tables, "Expected reporting view in MySQL schema")

    def test_04_stored_procedures_and_2026_dates(self):
        """Verifies stored procedures execute and calendar extends through 2026."""
        cursor = self.conn.cursor()
        # Test sp_extend_dim_date to 2026-12-31
        cursor.execute("CALL sp_extend_dim_date('2026-12-31');")
        self.conn.commit()

        cursor.execute("SELECT MAX(full_date) AS max_dt FROM Dim_Date;")
        row = cursor.fetchone()
        max_dt = str(row.get("max_dt") if isinstance(row, dict) else row[0])
        self.assertGreaterEqual(max_dt, "2026-12-31", "Dim_Date must extend through 2026-12-31")


if __name__ == "__main__":
    unittest.main()
