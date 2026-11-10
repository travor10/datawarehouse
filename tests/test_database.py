"""
Aura Cleaning Solutions Data Mart - Database & Schema Verification Tests
=============================================================================
Tests dimensional schema creation, primary/foreign key integrity, source-record
SHA-256 idempotency constraints, strict null preservation, and reporting view accuracy.

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

    def test_07_job_profitability_view_completeness_and_null_withholding(self):
        """
        Critical Financial Safeguard:
        1. When expenses are missing entirely, total_verified_expenses must be NULL (not 0.00).
        2. When expenses are INCOMPLETE, confirmed_gross_contribution must be NULL.
        3. When expenses are COMPLETE and CONFIRMED, contribution and margin calculate accurately.
        4. When figures are incomplete, profit variance discrepancy is withheld (NULL).
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

        # Case A: Job with MISSING Expenses (No expense rows loaded yet)
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('AUR-NO-EXP', ?, ?, 1, 'UNKNOWN', 'UNDETERMINED', 100000, 'rep_no_exp.xlsx', 'h_a', 'loc_a');",
            (cust_id, loc_id),
        )
        job_no_exp_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 200000, 'no_exp.xlsx', 'h_p1', 'l_p1', 'b1');",
            (job_no_exp_id, cust_id, srv_id, loc_id),
        )

        # Case B: Incomplete Expenses Job (Expenses exist but flagged INCOMPLETE)
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('AUR-INC', ?, ?, 1, 'INCOMPLETE', 'PROVISIONAL_INCOMPLETE_COSTS', 120000, 'rep_inc.xlsx', 'h_b', 'loc_b');",
            (cust_id, loc_id),
        )
        job_inc_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 300000, 'inc.xlsx', 'h_p2', 'l_p2', 'b1');",
            (job_inc_id, cust_id, srv_id, loc_id),
        )
        cursor.execute(
            "INSERT INTO Fact_Job_Expenses (job_key, expense_cat_key, location_key, expense_amount, is_verified, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, 50000, 1, 'inc.xlsx', 'h_e1', 'l_e1', 'b1');",
            (job_inc_id, exp_cat_id, loc_id),
        )

        # Case C: Fully Complete and Confirmed Job
        cursor.execute(
            "INSERT INTO Dim_Job (job_reference, customer_key, location_key, is_revenue_complete, expense_completeness_status, profitability_status, reported_job_profit, source_file, source_file_hash, source_record_locator) "
            "VALUES ('AUR-CONF', ?, ?, 1, 'COMPLETE', 'CONFIRMED', 180000, 'rep_conf.xlsx', 'h_c', 'loc_c');",
            (cust_id, loc_id),
        )
        job_conf_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO Fact_Job_Performance (job_key, customer_key, service_key, location_key, revenue_earned, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, ?, 500000, 'conf.xlsx', 'h_p3', 'l_p3', 'b1');",
            (job_conf_id, cust_id, srv_id, loc_id),
        )
        cursor.execute(
            "INSERT INTO Fact_Job_Expenses (job_key, expense_cat_key, location_key, expense_amount, is_verified, source_file, source_file_hash, source_record_locator, etl_batch_id) "
            "VALUES (?, ?, ?, 120000, 1, 'conf.xlsx', 'h_e2', 'l_e2', 'b1');",
            (job_conf_id, exp_cat_id, loc_id),
        )
        self.conn.commit()

        # Query Case A: Missing expenses
        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'AUR-NO-EXP';")
        no_exp_row = cursor.fetchone()
        self.assertIsNone(
            no_exp_row["total_verified_expenses"],
            "Missing expense records must return NULL, never 0.00!",
        )
        self.assertIsNone(
            no_exp_row["confirmed_gross_contribution"],
            "Confirmed contribution must be NULL when expenses are unknown!",
        )
        self.assertIsNone(
            no_exp_row["profit_variance_discrepancy"],
            "Profit variance discrepancy must be withheld (NULL) when expenses are unknown!",
        )

        # Query Case B: Incomplete expenses
        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'AUR-INC';")
        inc_row = cursor.fetchone()
        self.assertEqual(inc_row["total_revenue_earned"], 300000)
        self.assertEqual(inc_row["total_verified_expenses"], 50000)
        self.assertEqual(inc_row["provisional_gross_contribution"], 250000)
        self.assertIsNone(
            inc_row["confirmed_gross_contribution"],
            "Confirmed contribution must be NULL when expense completeness is not COMPLETE!",
        )
        self.assertIsNone(
            inc_row["profit_variance_discrepancy"],
            "Profit variance discrepancy must be withheld when expenses are incomplete!",
        )

        # Query Case C: Fully confirmed and complete
        cursor.execute("SELECT * FROM vw_job_profitability_summary WHERE job_reference = 'AUR-CONF';")
        conf_row = cursor.fetchone()
        self.assertEqual(conf_row["total_revenue_earned"], 500000)
        self.assertEqual(conf_row["total_verified_expenses"], 120000)
        # Confirmed contribution: 500,000 - 120,000 = 380,000
        self.assertEqual(conf_row["confirmed_gross_contribution"], 380000)
        # Margin: (380,000 / 500,000) * 100 = 76%
        self.assertEqual(conf_row["confirmed_gross_margin_pct"], 76.0)
        # Variance discrepancy: Reported profit (180,000) - Calculated contribution (380,000) = -200,000
        self.assertEqual(conf_row["profit_variance_discrepancy"], -200000)

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


if __name__ == "__main__":
    unittest.main()
