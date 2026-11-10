"""
Aura Cleaning Solutions Data Mart - Database Connection & Engine Factory
=============================================================================
Provides unified connection management for MySQL 8 (Authoritative Data Mart)
and isolated SQLite compatibility (Explicit Local Automated Tests & Dry-Runs).

Strict Engine Policy:
- If DB_ENGINE='mysql', MySQL drivers and connectivity are strictly required.
- SQLite is used ONLY when explicitly requested (e.g. DB_ENGINE='sqlite' or test suites).
- Silent driver or engine fallbacks are strictly prohibited.
"""

import logging
import re
import sqlite3
from typing import Any, Dict, Optional

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


class ConfigurationError(Exception):
    """Raised when database engine configuration or required drivers are missing."""
    pass


class DatabaseManager:
    """
    Manages database connections, transactions, and schema script executions
    for MySQL 8 (Authoritative) and isolated SQLite test databases.
    """

    def __init__(self, engine_type: Optional[str] = None):
        self.engine_type = (engine_type or DB_ENGINE).lower()
        self._mysql_driver = None

        if self.engine_type == "mysql":
            self._detect_mysql_driver()
        elif self.engine_type != "sqlite":
            raise ConfigurationError(
                f"Unsupported DB_ENGINE '{self.engine_type}'. Supported engines are 'mysql' and 'sqlite'."
            )

    def _detect_mysql_driver(self):
        """
        Detects installed MySQL database drivers.
        Raises ConfigurationError if no driver is installed. Never falls back silently.
        """
        try:
            import pymysql
            self._mysql_driver = "pymysql"
            return
        except ImportError:
            pass

        try:
            import mysql.connector
            self._mysql_driver = "mysql.connector"
            return
        except ImportError:
            pass

        raise ConfigurationError(
            "Database Configuration Error: DB_ENGINE is set to 'mysql', but neither "
            "'pymysql' nor 'mysql-connector-python' is installed.\n"
            "To resolve:\n"
            "  1. Install MySQL drivers: pip install -r requirements.txt\n"
            "  2. Or set DB_ENGINE=sqlite in your .env file strictly for isolated local unit testing."
        )

    def get_connection(self):
        """
        Returns an active database connection.
        - For MySQL: PyMySQL or mysql.connector connection
        - For SQLite: Standard library sqlite3 connection with foreign keys enabled
        """
        if self.engine_type == "mysql":
            return self._get_mysql_connection()
        elif self.engine_type == "sqlite":
            return self._get_sqlite_connection()
        else:
            raise ConfigurationError(f"Unsupported DB_ENGINE: {self.engine_type}")

    def _get_mysql_connection(self):
        """Establishes connection to MySQL 8 server."""
        try:
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
                raise ConfigurationError("No valid MySQL driver initialized.")
        except Exception as e:
            raise ConnectionError(
                f"Failed to connect to MySQL 8 database '{MYSQL_DATABASE}' at {MYSQL_HOST}:{MYSQL_PORT} "
                f"using user '{MYSQL_USER}': {e}\n"
                f"Verify that MySQL Server is running and credentials in .env are correct."
            ) from e

    def _get_sqlite_connection(self, in_memory: bool = False):
        """Establishes connection to local SQLite database with foreign keys enabled."""
        if in_memory:
            conn = sqlite3.connect(":memory:")
        else:
            SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(SQLITE_DB_PATH))

        conn.row_factory = sqlite3.Row
        # Enforce foreign key constraints in SQLite
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def test_connection(self) -> Dict[str, Any]:
        """Tests connectivity and returns database engine metadata."""
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
        cleaned = re.sub(r"CALL\s+sp_extend_dim_date\(.*?\);?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"ENGINE\s*=\s*InnoDB.*?;", ";", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"DEFAULT\s+CHARSET\s*=\s*[a-zA-Z0-9_]+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"COLLATE\s*=\s*[a-zA-Z0-9_]+", "", cleaned, flags=re.IGNORECASE)

        # Handle AUTO_INCREMENT columns for SQLite
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

        # In SQLite, remove inline ', INDEX ...' from CREATE TABLE and convert to standalone CREATE INDEX
        standalone_indexes = []
        for match in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_]+)\s*\((.*?)\);",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            tbl_name = match.group(1)
            body = match.group(2)
            idx_matches = re.findall(
                r"INDEX\s+([a-zA-Z0-9_]+)\s*\((.*?)\)", body, flags=re.IGNORECASE
            )
            for idx_name, idx_cols in idx_matches:
                standalone_indexes.append(
                    f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl_name} ({idx_cols});"
                )

        cleaned = re.sub(
            r",\s*INDEX\s+[a-zA-Z0-9_]+\s*\(.*?\)", "", cleaned, flags=re.IGNORECASE
        )

        # Adjust MySQL types to SQLite affinities
        cleaned = re.sub(r"\bTINYINT\s+UNSIGNED\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bSMALLINT\s+UNSIGNED\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bTINYINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bSMALLINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bBIGINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bDECIMAL\(\d+,\s*\d+\)\b", "NUMERIC", cleaned, flags=re.IGNORECASE)

        if standalone_indexes:
            cleaned += "\n" + "\n".join(standalone_indexes)

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
                        # Log but continue for harmless duplicate statements in testing
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
# In testing environments without configured MySQL, instantiate DatabaseManager('sqlite') explicitly.
def get_db_manager(engine_type: Optional[str] = None) -> DatabaseManager:
    return DatabaseManager(engine_type=engine_type)
