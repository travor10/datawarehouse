"""
Aura Cleaning Solutions Data Mart - [OFFLINE / LOCAL] SQLite Relational Unit Test Suite
=============================================================================
Tests dimensional schema creation, primary/foreign key integrity, source-record
SHA-256 idempotency constraints, strict null preservation, the 5 expense completeness
states, and schema migration tracking.

Runs on Python's built-in unittest framework using SQLite in-memory / local mode,
ensuring zero external pip dependency blockers while enforcing identical relational
logic to MySQL 8.
"""

import sqlite3
import unittest
from pathlib import Path

from config.database import DatabaseManager
from config.settings import DATABASE_DIR


class TestDatabaseSchema(unittest.TestCase):
    """Verifies relational integrity, foreign keys, unique constraints, and views."""

    @classmethod
    def setUpClass(cls):
        """Initializes test database schema using the project DDL scripts."""
        cls.db_manager = DatabaseManager(engine_type="sqlite")
        cls.conn = sqlite3.connect(":memory:")
        cls.conn.row_factory = sqlite3.Row
        cls.conn.execute("PRAGMA foreign_keys = ON;")

        # Deploy DDL scripts in dependency order
        cls._deploy_ddl(cls.conn)

    @classmethod
    def _deploy_ddl(cls, conn):
        """Adapts and deploys dimension, fact, and view DDL to test database."""
        # 1. Dimensions
        dim_script = DATABASE_DIR / "create_dimensions.sql"
        cls.db_manager.execute_script(dim_script, conn=conn)

        # 2. Facts
        fact_script = DATABASE_DIR / "create_facts.sql"
        cls.db_manager.execute_script(fact_script, conn=conn)

        # 3. View (Executes create_views.sql directly)
        view_script = DATABASE_DIR / "create_views.sql"
        cls.db_manager.execute_script(view_script, conn=conn)

    def setUp(self):
        """Cleans working tables between individual test cases."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM Fact_Job_Expenses;")
        cursor.execute("DELETE FROM Fact_Job_Performance;")
        cursor.execute("DELETE FROM Dim_Job;")
        cursor.execute("DELETE FROM Dim_Service;")
        cursor.execute("DELETE FROM Dim_Customer;")
        cursor.execute("DELETE FROM Dim_Location;")
        cursor.execute("DELETE FROM Dim_Expense_Category;")
        cursor.execute("DELETE FROM Dim_Date;")
        self.conn.commit()

    def test_01_all_tables_exist(self):
        """Verifies all 6 Dimensions and 2 Facts exist in the database."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}

        expected_dimensions = {
            "Dim_Date",
            "Dim_Location",
            "Dim_Customer",
            "Dim_Service",
            "Dim_Expense_Category",
            "Dim_Job",
        }
        expected_facts = {"Fact_Job_Performance", "Fact_Job_Expenses"}

        for dim in expected_dimensions:
            self.assertIn(dim, tables, f"Dimension table {dim} is missing!")

        for fact in expected_facts:
            self.assertIn(fact, tables, f"Fact table {fact} is missing!")

    def test_02_surrogate_key_generation(self):
        """Verifies that dimension surrogate keys auto-increment sequentially."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO Dim_Customer (customer_code, customer_name_clean, customer_name_raw, customer_type) "
            "VALUES ('CUST-001', 'Bank of Uganda', 'Bank of Uganda HQ', 'Commercial');"
        )
        cursor.execute(
            "INSERT INTO Dim_Customer (customer_code, customer_name_clean, customer_name_raw, customer_type) "
            "VALUES ('CUST-002', 'Sarah Namubiru', 'Sarah Namubiru', 'Individual');"
        )
        self.conn.commit()

        cursor.execute("SELECT customer_key, customer_code FROM Dim_Customer ORDER BY customer_key;")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["customer_key"], 1)
        self.assertEqual(rows[1]["customer_key"], 2)

    def test_03_natural_key_uniqueness_enforced(self):
        """Verifies natural keys (e.g. customer_code, service_code) enforce uniqueness."""
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO Dim_Customer (customer_code, customer_name_clean, customer_name_raw) "
            "VALUES ('CUST-DUP', 'Alpha Corp', 'Alpha Corp');"
        )
        self.conn.commit()

        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO Dim_Customer (customer_code, customer_name_clean, customer_name_raw) "
                "VALUES ('CUST-DUP', 'Another Alpha', 'Another Alpha');"
            )
            self.conn.commit()

    def test_04_idempotent_sha256_provenance_uniqueness(self):
        """
        Critical Safeguard: Verifies that (source_file_hash, source_record_locator)
        uniqueness prevents duplicate loading even if a source file is renamed.
        """
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO Dim_Location (location_name_clean, location_name_raw) VALUES ('Kololo', 'Kololo');")
        loc_id = cursor.lastrowid
        cursor.execute("INSERT INTO Dim_Customer (customer_code, customer_name_clean, customer_name_raw) VALUES ('C-1', 'Test Client', 'Test Client');")
        cust_id = cursor.lastrowid
        cursor.execute("INSERT INTO Dim_Service (service_code, service_name_clean, service_name_raw, service_category) VALUES ('S-1', 'Sofa Clean', 'Sofa Clean', 'Sofa & Upholstery Cleaning');")
        srv_id = cursor.lastrowid

        file_hash = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        locator = "Sheet:Jobs|Row:14"

        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, source_file, source_file_hash, source_record_locator) "
            "VALUES ('AUR-001', ?, ?, 'march_jobs.xlsx', ?, ?);",
            (cust_id, loc_id, file_hash, locator),
        )
        job_id = cursor.lastrowid

        # Insert first performance row
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 150000, 'march_jobs.xlsx', ?, ?, 'batch_001');",
            (job_id, cust_id, srv_id, loc_id, file_hash, locator),
        )
        self.conn.commit()

        # Attempt duplicate insertion of identical content from a RENAMED file copy
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
                "VALUES (?, ?, ?, ?, 150000, 'Copy_of_march_jobs.xlsx', ?, ?, 'batch_002');",
                (job_id, cust_id, srv_id, loc_id, file_hash, locator),
            )
            self.conn.commit()

    def test_05_referential_integrity_foreign_keys(self):
        """Verifies that orphan fact records without valid dimension parents are rejected."""
        cursor = self.conn.cursor()
        with self.assertRaises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
                "VALUES (9999, 1, 1, 1, 50000, 'file.xlsx', 'hash1', 'loc1', 'b1');"
            )
            self.conn.commit()

    def test_06_null_preservation_for_unknown_financials(self):
        """
        Critical Financial Safeguard: Verifies that missing quotes and revenues
        remain NULL and are NEVER coerced to 0.00.
        """
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO Dim_Location (location_name_clean, location_name_raw) VALUES ('Ntinda', 'Ntinda');")
        loc_id = cursor.lastrowid
        cursor.execute("INSERT INTO Dim_Customer (customer_code, customer_name_clean, customer_name_raw) VALUES ('C-2', 'John', 'John');")
        cust_id = cursor.lastrowid
        cursor.execute("INSERT INTO Dim_Service (service_code, service_name_clean, service_name_raw, service_category) VALUES ('S-2', 'Carpet', 'Carpet', 'Carpet Cleaning');")
        srv_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, source_file, source_file_hash, source_record_locator) "
            "VALUES ('AUR-002', ?, ?, 'rep.xlsx', 'hash2', 'loc2');",
            (cust_id, loc_id),
        )
        job_id = cursor.lastrowid

        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, quoted_amount, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, NULL, NULL, 'march_jobs.xlsx', 'hash3', 'loc3', 'batch_001');",
            (job_id, cust_id, srv_id, loc_id),
        )
        self.conn.commit()

        cursor.execute("SELECT quoted_amount, revenue_earned FROM Fact_Job_Performance WHERE job_key = ?;", (job_id,))
        row = cursor.fetchone()
        self.assertIsNone(row["quoted_amount"], "Missing quoted amount must be NULL!")
        self.assertIsNone(row["revenue_earned"], "Missing revenue earned must be NULL!")

    def test_07_five_expense_completeness_states(self):
        """
        Rigorous Financial Integrity Test:
        Verifies the exact behavior of vw_job_profitability_summary across all 5 states:
        1. COMPLETE: Revenue & all verified expenses complete -> contribution calculated, variance calculated.
        2. CONFIRMED_ZERO: Work confirmed with 0 expenses -> verified costs = 0.00, contribution = revenue.
        3. UNKNOWN: Expense status undetermined -> verified costs = NULL, contribution = NULL, variance = NULL.
        4. INCOMPLETE: Some vouchers present but others missing -> verified costs displayed, contribution = NULL, variance = NULL.
        5. UNVERIFIED: Vouchers recorded but receipts unverified -> verified costs = 0, unverified costs > 0, contribution = NULL.
        """
        cursor = self.conn.cursor()

        # Seed master data
        cursor.execute("INSERT INTO Dim_Location (location_name_clean, location_name_raw) VALUES ('Nakasero', 'Nakasero');")
        loc_id = cursor.lastrowid
        cursor.execute("INSERT INTO Dim_Customer (customer_code, customer_name_clean, customer_name_raw) VALUES ('C-3', 'Stanbic Bank', 'Stanbic Bank');")
        cust_id = cursor.lastrowid
        cursor.execute("INSERT INTO Dim_Service (service_code, service_name_clean, service_name_raw, service_category) VALUES ('S-3', 'Fumigation', 'Fumigation', 'Pest Control & Fumigation');")
        srv_id = cursor.lastrowid
        cursor.execute("INSERT INTO Dim_Expense_Category (expense_category_name, cost_type) VALUES ('Labour Wages', 'Direct Operational Cost');")
        exp_cat_id = cursor.lastrowid

        # -------------------------------------------------------------
        # State 1: COMPLETE (Fully verified and confirmed)
        # -------------------------------------------------------------
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('JOB-COMPLETE', ?, ?, 1, 'COMPLETE', 'CONFIRMED', 180000, 'f1.xlsx', 'h1', 'l1');",
            (cust_id, loc_id),
        )
        j1 = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 500000, 'f1.xlsx', 'h1', 'p1', 'b1');",
            (j1, cust_id, srv_id, loc_id),
        )
        cursor.execute(
            "INSERT INTO Fact_Job_Expenses (job_key, expense_cat_key, location_key, expense_amount, is_verified, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, 120000, 1, 'f1.xlsx', 'h1', 'e1', 'b1');",
            (j1, exp_cat_id, loc_id),
        )

        # -------------------------------------------------------------
        # State 2: CONFIRMED_ZERO (Confirmed zero direct cost)
        # -------------------------------------------------------------
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('JOB-ZERO', ?, ?, 1, 'CONFIRMED_ZERO', 'CONFIRMED', 200000, 'f2.xlsx', 'h2', 'l2');",
            (cust_id, loc_id),
        )
        j2 = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 200000, 'f2.xlsx', 'h2', 'p2', 'b1');",
            (j2, cust_id, srv_id, loc_id),
        )

        # -------------------------------------------------------------
        # State 3: UNKNOWN (No expense data recorded yet)
        # -------------------------------------------------------------
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('JOB-UNKNOWN', ?, ?, 1, 'UNKNOWN', 'UNDETERMINED', 100000, 'f3.xlsx', 'h3', 'l3');",
            (cust_id, loc_id),
        )
        j3 = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 350000, 'f3.xlsx', 'h3', 'p3', 'b1');",
            (j3, cust_id, srv_id, loc_id),
        )

        # -------------------------------------------------------------
        # State 4: INCOMPLETE (Some expenses recorded, but known vouchers missing)
        # -------------------------------------------------------------
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('JOB-INCOMPLETE', ?, ?, 1, 'INCOMPLETE', 'PROVISIONAL_INCOMPLETE_COSTS', 150000, 'f4.xlsx', 'h4', 'l4');",
            (cust_id, loc_id),
        )
        j4 = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 400000, 'f4.xlsx', 'h4', 'p4', 'b1');",
            (j4, cust_id, srv_id, loc_id),
        )
        cursor.execute(
            "INSERT INTO Fact_Job_Expenses (job_key, expense_cat_key, location_key, expense_amount, is_verified, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, 60000, 1, 'f4.xlsx', 'h4', 'e4', 'b1');",
            (j4, exp_cat_id, loc_id),
        )

        # -------------------------------------------------------------
        # State 5: UNVERIFIED (Vouchers exist but receipts are unverified)
        # -------------------------------------------------------------
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('JOB-UNVERIFIED', ?, ?, 1, 'UNVERIFIED', 'UNDETERMINED', 80000, 'f5.xlsx', 'h5', 'l5');",
            (cust_id, loc_id),
        )
        j5 = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 300000, 'f5.xlsx', 'h5', 'p5', 'b1');",
            (j5, cust_id, srv_id, loc_id),
        )
        cursor.execute(
            "INSERT INTO Fact_Job_Expenses (job_key, expense_cat_key, location_key, expense_amount, is_verified, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, 70000, 0, 'f5.xlsx', 'h5', 'e5', 'b1');",
            (j5, exp_cat_id, loc_id),
        )
        self.conn.commit()

        # Query and assert State 1: COMPLETE
        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'JOB-COMPLETE';")
        r1 = cursor.fetchone()
        self.assertEqual(r1["total_revenue_earned"], 500000)
        self.assertEqual(r1["total_verified_expenses"], 120000)
        self.assertEqual(r1["confirmed_gross_contribution"], 380000)
        self.assertEqual(r1["confirmed_gross_margin_pct"], 76.0)
        self.assertEqual(r1["profit_variance_discrepancy"], -200000)

        # Query and assert State 2: CONFIRMED_ZERO
        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'JOB-ZERO';")
        r2 = cursor.fetchone()
        self.assertEqual(r2["total_revenue_earned"], 200000)
        self.assertEqual(r2["total_verified_expenses"], 0.0)
        self.assertEqual(r2["confirmed_gross_contribution"], 200000)
        self.assertEqual(r2["confirmed_gross_margin_pct"], 100.0)
        self.assertEqual(r2["profit_variance_discrepancy"], 0.0)

        # Query and assert State 3: UNKNOWN
        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'JOB-UNKNOWN';")
        r3 = cursor.fetchone()
        self.assertEqual(r3["total_revenue_earned"], 350000)
        self.assertIsNone(r3["total_verified_expenses"], "UNKNOWN expenses must be NULL")
        self.assertIsNone(r3["confirmed_gross_contribution"], "Contribution must be NULL when expenses unknown")
        self.assertIsNone(r3["profit_variance_discrepancy"], "Variance must be withheld when expenses unknown")

        # Query and assert State 4: INCOMPLETE
        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'JOB-INCOMPLETE';")
        r4 = cursor.fetchone()
        self.assertEqual(r4["total_verified_expenses"], 60000)
        self.assertIsNone(r4["confirmed_gross_contribution"], "Contribution must be NULL when expenses incomplete")
        self.assertIsNone(r4["profit_variance_discrepancy"], "Variance must be withheld when expenses incomplete")

        # Query and assert State 5: UNVERIFIED
        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'JOB-UNVERIFIED';")
        r5 = cursor.fetchone()
        self.assertEqual(r5["total_verified_expenses"], 0.0)
        self.assertEqual(r5["total_unverified_expenses"], 70000)
        self.assertIsNone(r5["confirmed_gross_contribution"], "Contribution must be NULL when unverified")
        self.assertIsNone(r5["profit_variance_discrepancy"], "Variance must be withheld when unverified")

    def test_08_reference_data_seeding(self):
        """Verifies that reference data insertion scripts correctly seed canonical dimensions."""
        ref_script = DATABASE_DIR / "insert_reference_data.sql"
        self.db_manager.execute_script(ref_script, conn=self.conn)

        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) AS cnt FROM Dim_Expense_Category;")
        exp_count = cursor.fetchone()["cnt"]
        self.assertEqual(exp_count, 6, "Expected 6 canonical expense categories seeded.")

        cursor.execute("SELECT DISTINCT service_category FROM Dim_Service WHERE service_category != 'Under Review';")
        categories = {row["service_category"] for row in cursor.fetchall()}
        expected_categories = {
            "Residential Cleaning",
            "Commercial Cleaning",
            "Sofa & Upholstery Cleaning",
            "Carpet Cleaning",
            "Pest Control & Fumigation",
            "Post-Construction Cleaning",
            "Laundry Services",
        }
        self.assertEqual(categories, expected_categories, "All 7 canonical service categories must be seeded.")

    def test_09_migration_runner_idempotency(self):
        """Verifies that run_migrations tracks applied versions in _schema_migrations."""
        # Create a fresh isolated connection
        test_conn = sqlite3.connect(":memory:")
        test_conn.row_factory = sqlite3.Row
        test_conn.execute("PRAGMA foreign_keys = ON;")

        # Run migrations first time
        applied_1 = self.db_manager.run_migrations(conn=test_conn)
        self.assertIn("001_initial_schema", applied_1, "001_initial_schema should be applied on first run")

        # Run migrations second time (must be idempotent no-op)
        applied_2 = self.db_manager.run_migrations(conn=test_conn)
        self.assertEqual(len(applied_2), 0, "Second migration run must be a no-op")

        # Verify _schema_migrations record
        cursor = test_conn.cursor()
        cursor.execute("SELECT version, status FROM _schema_migrations WHERE version = '001_initial_schema';")
        row = cursor.fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["status"], "SUCCESS")
        test_conn.close()


if __name__ == "__main__":
    unittest.main()
