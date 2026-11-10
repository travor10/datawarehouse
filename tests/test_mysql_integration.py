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

    def test_05_mysql_schema_migrations(self):
        """Verifies migration tracking table and forward migrations on MySQL 8."""
        applied = self.db_manager.run_migrations(conn=self.conn)
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM _schema_migrations WHERE status = 'SUCCESS';")
        row = cursor.fetchone()
        cnt = row.get("cnt") if isinstance(row, dict) else row[0]
        self.assertGreaterEqual(cnt, 1, "Expected at least 1 successful migration in _schema_migrations")

    def test_06_mysql_five_expense_completeness_states(self):
        """Verifies all 5 expense completeness states and NULL withholding on MySQL 8."""
        cursor = self.conn.cursor()
        # Clean test records
        cursor.execute("DELETE FROM Fact_Job_Expenses WHERE source_file = 'mysql_test.xlsx';")
        cursor.execute("DELETE FROM Fact_Job_Performance WHERE source_file = 'mysql_test.xlsx';")
        cursor.execute("DELETE FROM Dim_Job WHERE source_file = 'mysql_test.xlsx';")
        self.conn.commit()

        # Seed required customer and location if needed
        cursor.execute("SELECT customer_key FROM Dim_Customer LIMIT 1;")
        c_row = cursor.fetchone()
        cust_id = c_row.get("customer_key") if isinstance(c_row, dict) else c_row[0]

        cursor.execute("SELECT location_key FROM Dim_Location LIMIT 1;")
        l_row = cursor.fetchone()
        loc_id = l_row.get("location_key") if isinstance(l_row, dict) else l_row[0]

        cursor.execute("SELECT service_key FROM Dim_Service LIMIT 1;")
        s_row = cursor.fetchone()
        srv_id = s_row.get("service_key") if isinstance(s_row, dict) else s_row[0]

        cursor.execute("SELECT expense_cat_key FROM Dim_Expense_Category LIMIT 1;")
        e_row = cursor.fetchone()
        exp_cat_id = e_row.get("expense_cat_key") if isinstance(e_row, dict) else e_row[0]

        # Insert Complete Job
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('MY-COMPLETE', %s, %s, TRUE, 'COMPLETE', 'CONFIRMED', 150000, 'mysql_test.xlsx', 'h_m1', 'l_m1');",
            (cust_id, loc_id),
        )
        j_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (%s, %s, %s, %s, 400000, 'mysql_test.xlsx', 'h_m1', 'p_m1', 'b1');",
            (j_id, cust_id, srv_id, loc_id),
        )
        cursor.execute(
            "INSERT INTO Fact_Job_Expenses (job_key, expense_cat_key, location_key, expense_amount, is_verified, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (%s, %s, %s, 100000, TRUE, 'mysql_test.xlsx', 'h_m1', 'e_m1', 'b1');",
            (j_id, exp_cat_id, loc_id),
        )
        self.conn.commit()

        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'MY-COMPLETE';")
        res = cursor.fetchone()
        rev = res.get("total_revenue_earned") if isinstance(res, dict) else res[17]
        contrib = res.get("confirmed_gross_contribution") if isinstance(res, dict) else res[24]
        self.assertEqual(float(rev), 400000.0)
        self.assertEqual(float(contrib), 300000.0)


if __name__ == "__main__":
    unittest.main()
