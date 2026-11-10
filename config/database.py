"""
Aura Cleaning Solutions Data Mart - Database Connection & Engine Factory
=============================================================================
Provides unified connection management for MySQL 8 (Authoritative Data Mart)
and isolated SQLite compatibility (Local Automated Tests & Dry-Runs).
"""

import logging
import re
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from config.settings import (
    DATABASE_DIR,
    DB_ENGINE,
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
    SQLITE_DB_PATH,
)

logger = logging.getLogger("aura_data_mart.database")


class DatabaseManager:
    """
    Manages database connections, transactions, and schema script executions
    for both MySQL 8 and local SQLite test databases.
    """

    def __init__(self, engine_type: Optional[str] = None):
        self.engine_type = (engine_type or DB_ENGINE).lower()
        self._mysql_driver = None
        self._detect_drivers()

    def _detect_drivers(self):
        """Detects available MySQL database drivers."""
        if self.engine_type == "mysql":
            try:
                import pymysql

                self._mysql_driver = "pymysql"
            except ImportError:
                try:
                    import mysql.connector

                    self._mysql_driver = "mysql.connector"
                except ImportError:
                    logger.warning(
                        "No MySQL driver found (neither pymysql nor mysql-connector-python). "
                        "Falling back to SQLite for local operations."
                    )
                    self.engine_type = "sqlite"

    def get_connection(self):
        """
        Returns an active database connection.
        - For MySQL: PyMySQL or mysql.connector connection
        - For SQLite: Standard library sqlite3 connection with foreign keys enabled
        """
        if self.engine_type == "mysql":
            return self._get_mysql_connection()
        else:
            return self._get_sqlite_connection()

    def _get_mysql_connection(self):
        """Establishes connection to MySQL 8 server."""
        if self._mysql_driver == "pymysql":
            import pymysql

            return pymysql.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                charset="utf8mb4",
                autocommit=False,
                cursorclass=pymysql.cursors.DictCursor,
            )
        elif self._mysql_driver == "mysql.connector":
            import mysql.connector

            return mysql.connector.connect(
                host=MYSQL_HOST,
                port=MYSQL_PORT,
                user=MYSQL_USER,
                password=MYSQL_PASSWORD,
                database=MYSQL_DATABASE,
                charset="utf8mb4",
                autocommit=False,
            )
        else:
            raise RuntimeError("Cannot establish MySQL connection: driver missing.")

    def _get_sqlite_connection(self, in_memory: bool = False):
        """Establishes connection to local SQLite database with foreign keys enabled."""
        if in_memory:
            conn = sqlite3.connect(":memory:")
        else:
            SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(SQLITE_DB_PATH))

        conn.row_factory = sqlite3.Row
        # Critical for relational integrity in SQLite
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def test_connection(self) -> Dict[str, Any]:
        """Tests connectivity and returns database metadata."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            if self.engine_type == "mysql":
                cursor.execute(
                    "SELECT VERSION() as version, DATABASE() as db, USER() as user;"
                )
                row = cursor.fetchone()
                conn.close()
                return {
                    "status": "connected",
                    "engine": "MySQL 8",
                    "version": row.get("version") if isinstance(row, dict) else row[0],
                    "database": row.get("db") if isinstance(row, dict) else row[1],
                    "user": row.get("user") if isinstance(row, dict) else row[2],
                }
            else:
                cursor.execute("SELECT sqlite_version() as version;")
                row = cursor.fetchone()
                conn.close()
                return {
                    "status": "connected",
                    "engine": "SQLite",
                    "version": row["version"] if isinstance(row, sqlite3.Row) else row[0],
                    "database": str(SQLITE_DB_PATH),
                }
        except Exception as e:
            return {"status": "error", "engine": self.engine_type, "error": str(e)}

    @staticmethod
    def adapt_mysql_ddl_for_sqlite(sql_text: str) -> str:
        """
        Adapts standard MySQL 8 DDL scripts into SQLite dialect for unit tests.
        Converts AUTO_INCREMENT, ENGINES, CHARACTER SETS, and data types while
        preserving relational foreign key constraints and check constraints.
        """
        # Strip line comments first so statements are clean
        cleaned = re.sub(r"--.*?$", "", sql_text, flags=re.MULTILINE)

        # Remove MySQL-specific commands
        cleaned = re.sub(r"USE\s+[a-zA-Z0-9_]+;", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"SET\s+FOREIGN_KEY_CHECKS\s*=\s*[01];", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"DELIMITER\s+.*", "", cleaned)
        cleaned = re.sub(r"CREATE\s+OR\s+REPLACE\s+VIEW", "CREATE VIEW IF NOT EXISTS", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"ON\s+DUPLICATE\s+KEY\s+UPDATE.*?(?=;|$)", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"CALL\s+sp_populate_dim_date\(.*?\);?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"ENGINE\s*=\s*InnoDB.*?;", ";", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"DEFAULT\s+CHARSET\s*=\s*[a-zA-Z0-9_]+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"COLLATE\s*=\s*[a-zA-Z0-9_]+", "", cleaned, flags=re.IGNORECASE)

        # In SQLite, an AUTOINCREMENT column MUST be PRIMARY KEY directly on the column definition:
        auto_cols = re.findall(
            r"(\b[a-zA-Z0-9_]+_key\b)\s+(?:BIGINT|INT)\s+AUTO_INCREMENT\s+NOT\s+NULL",
            cleaned,
            flags=re.IGNORECASE,
        )
        for col in auto_cols:
            cleaned = re.sub(
                rf"\b{col}\b\s+(?:BIGINT|INT)\s+AUTO_INCREMENT\s+NOT\s+NULL",
                f"{col} INTEGER PRIMARY KEY AUTOINCREMENT",
                cleaned,
                flags=re.IGNORECASE,
            )
            cleaned = re.sub(
                rf",\s*CONSTRAINT\s+pk_[a-zA-Z0-9_]+\s+PRIMARY\s+KEY\s*\({col}\)",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )

        # Adjust MySQL types to SQLite affinities
        cleaned = re.sub(r"\bTINYINT\s+UNSIGNED\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bSMALLINT\s+UNSIGNED\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bTINYINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bSMALLINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bBIGINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bDECIMAL\(\d+,\s*\d+\)\b", "NUMERIC", cleaned, flags=re.IGNORECASE)

        return cleaned

    def execute_script(self, script_path, conn=None):
        """Executes a SQL file against the current connection."""
        close_at_end = False
        if conn is None:
            conn = self.get_connection()
            close_at_end = True

        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()

        cursor = conn.cursor()
        try:
            if self.engine_type == "sqlite":
                adapted_sql = self.adapt_mysql_ddl_for_sqlite(content)
                statements = [
                    s.strip()
                    for s in adapted_sql.split(";")
                    if s.strip() and not s.strip().upper().startswith("CREATE PROCEDURE")
                ]
                for stmt in statements:
                    try:
                        cursor.execute(stmt)
                    except Exception as stmt_err:
                        # Log but continue for harmless drop statements
                        if "already exists" not in str(stmt_err).lower() and "no such table" not in str(stmt_err).lower():
                            logger.debug(f"Statement execution notice: {stmt_err}")
                conn.commit()
            else:
                # MySQL multi-statement execution
                cursor.execute(content)
                conn.commit()
        finally:
            if close_at_end:
                conn.close()


# Default singleton instance
db_manager = DatabaseManager()
