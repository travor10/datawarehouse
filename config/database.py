"""
Aura Cleaning Solutions Data Mart - Database Connection & Engine Factory
=============================================================================
Provides unified connection management for MySQL 8 (Authoritative Data Mart)
and isolated SQLite compatibility (Explicit Local Automated Tests & Dry-Runs).

Strict Engine Policy:
- If DB_ENGINE='mysql', MySQL drivers and connectivity are strictly required.
- SQLite is used ONLY when explicitly requested (e.g. DB_ENGINE='sqlite' or test suites).
- Silent driver or engine fallbacks are strictly prohibited.
- Script execution strips client-only DELIMITER directives and executes statements individually.
- Migrations are tracked with cryptographic SHA-256 checksums to enforce forward-only immutability.
"""

import hashlib
import logging
import re
import sqlite3
import time
from pathlib import Path
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


class ConfigurationError(Exception):
    """Raised when database engine configuration or required drivers are missing."""
    pass


class MigrationChecksumError(Exception):
    """Raised when an already applied migration file has been altered or tampered with."""
    pass


class MigrationExecutionError(Exception):
    """Raised when a schema migration statement fails execution."""
    pass


class DatabaseManager:
    """
    Manages database connections, transactions, schema script executions,
    and checksum-verified migrations for MySQL 8 (Authoritative) and isolated SQLite test databases.
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
    def compute_file_checksum(filepath: Path) -> str:
        """Computes the SHA-256 cryptographic digest of a migration file."""
        sha256 = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    @staticmethod
    def parse_mysql_statements(content: str) -> List[str]:
        """
        Parses multi-statement MySQL script content safely:
        - Strips comment lines.
        - Dynamically tracks DELIMITER directives (e.g. DELIMITER $$ ... DELIMITER ;).
        - Strips client-only DELIMITER commands so they are never sent to MySQL server.
        - Extracts complete stored procedure definitions without splitting internal semicolons.
        """
        cleaned = re.sub(r"--.*?$", "", content, flags=re.MULTILINE)

        statements = []
        delimiter = ";"
        current_stmt: List[str] = []

        for line in cleaned.split("\n"):
            stripped = line.strip()
            if not stripped:
                continue

            delim_match = re.match(r"^DELIMITER\s+(.+)$", stripped, flags=re.IGNORECASE)
            if delim_match:
                delimiter = delim_match.group(1).strip()
                continue

            current_stmt.append(line)
            joined = "\n".join(current_stmt).strip()

            if joined.endswith(delimiter):
                stmt = joined[:-len(delimiter)].strip()
                if stmt:
                    statements.append(stmt)
                current_stmt = []

        if current_stmt:
            remaining = "\n".join(current_stmt).strip()
            if remaining:
                statements.append(remaining)

        return statements

    @staticmethod
    def adapt_mysql_ddl_for_sqlite(sql_text: str) -> str:
        """
        Adapts standard MySQL 8 DDL scripts into SQLite dialect for unit tests.
        Converts AUTO_INCREMENT, ENGINES, CHARACTER SETS, and data types while
        preserving relational foreign key constraints and check constraints.
        """
        cleaned = re.sub(r"--.*?$", "", sql_text, flags=re.MULTILINE)

        cleaned = re.sub(r"USE\s+[a-zA-Z0-9_]+;", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"SET\s+FOREIGN_KEY_CHECKS\s*=\s*[01];", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"DELIMITER\s+.*", "", cleaned)
        cleaned = re.sub(r"CREATE\s+OR\s+REPLACE\s+VIEW", "CREATE VIEW IF NOT EXISTS", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"ON\s+DUPLICATE\s+KEY\s+UPDATE.*?(?=;|$)", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"CALL\s+sp_populate_dim_date\(.*?\);?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"CALL\s+sp_extend_dim_date\(.*?\);?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"DROP\s+PROCEDURE\s+(?:IF\s+EXISTS\s+)?[a-zA-Z0-9_]+;?", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"CREATE\s+PROCEDURE\s+.*?\bEND(?:\$\$|;)", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"ENGINE\s*=\s*InnoDB.*?;", ";", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"DEFAULT\s+CHARSET\s*=\s*[a-zA-Z0-9_]+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"COLLATE\s*=\s*[a-zA-Z0-9_]+", "", cleaned, flags=re.IGNORECASE)

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

        cleaned = re.sub(r"\bTINYINT\s+UNSIGNED\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bSMALLINT\s+UNSIGNED\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bTINYINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bSMALLINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bBIGINT\b", "INTEGER", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bDECIMAL\(\d+,\s*\d+\)\b", "NUMERIC", cleaned, flags=re.IGNORECASE)

        if standalone_indexes:
            cleaned += "\n" + "\n".join(standalone_indexes)

        return cleaned

    def execute_script(self, script_path: Path, conn=None):
        """
        Executes a SQL file safely:
        - In SQLite: Adapts syntax, strips MySQL specifics, executes individual statements.
        - In MySQL: Parses individual statements, strips DELIMITER client directives,
                    and executes each statement (including CREATE PROCEDURE) reliably.
        """
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
                    if s.strip()
                    and not s.strip().upper().startswith("CREATE PROCEDURE")
                    and not s.strip().upper().startswith("DROP PROCEDURE")
                ]
                for stmt in statements:
                    try:
                        cursor.execute(stmt)
                    except Exception as stmt_err:
                        err_msg = str(stmt_err).lower()
                        if stmt.upper().startswith("DROP ") and "no such" in err_msg:
                            continue
                        logger.error(f"Error executing SQLite statement in {script_path.name}: {stmt_err}\nQuery: {stmt[:150]}")
                        raise MigrationExecutionError(f"Failed statement in {script_path.name}: {stmt_err}") from stmt_err
                conn.commit()
            else:
                statements = self.parse_mysql_statements(content)
                for stmt in statements:
                    stmt_clean = stmt.strip()
                    if not stmt_clean or stmt_clean.upper().startswith("USE "):
                        continue
                    try:
                        cursor.execute(stmt_clean)
                    except Exception as err:
                        logger.error(f"Error executing statement in {script_path}: {err}\nQuery: {stmt_clean[:150]}")
                        raise MigrationExecutionError(f"Failed statement in {script_path.name}: {err}") from err
                conn.commit()
        finally:
            if close_at_end:
                conn.close()

    def init_migration_table(self, conn=None):
        """Initializes the schema migration tracking table with checksum tracking."""
        close_at_end = False
        if conn is None:
            conn = self.get_connection()
            close_at_end = True

        cursor = conn.cursor()
        if self.engine_type == "sqlite":
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                migration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                version VARCHAR(50) NOT NULL UNIQUE,
                description VARCHAR(255) NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms INTEGER NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS'
            );
            """)
        else:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                migration_id INT AUTO_INCREMENT PRIMARY KEY,
                version VARCHAR(50) NOT NULL UNIQUE,
                description VARCHAR(255) NOT NULL,
                checksum VARCHAR(64) NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms INT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'SUCCESS'
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)
        conn.commit()
        if close_at_end:
            conn.close()

    def _record_migration_result(
        self,
        cursor,
        version: str,
        description: str,
        checksum: str,
        execution_time_ms: int,
        status: str,
    ):
        """Inserts or updates migration audit records safely without duplicate key violations."""
        if self.engine_type == "sqlite":
            cursor.execute("SELECT migration_id FROM _schema_migrations WHERE version = ?;", (version,))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE _schema_migrations SET description = ?, checksum = ?, "
                    "execution_time_ms = ?, status = ?, applied_at = CURRENT_TIMESTAMP WHERE version = ?;",
                    (description, checksum, execution_time_ms, status, version),
                )
            else:
                cursor.execute(
                    "INSERT INTO _schema_migrations (version, description, checksum, execution_time_ms, status) "
                    "VALUES (?, ?, ?, ?, ?);",
                    (version, description, checksum, execution_time_ms, status),
                )
        else:
            cursor.execute("SELECT migration_id FROM _schema_migrations WHERE version = %s;", (version,))
            row = cursor.fetchone()
            if row:
                cursor.execute(
                    "UPDATE _schema_migrations SET description = %s, checksum = %s, "
                    "execution_time_ms = %s, status = %s, applied_at = CURRENT_TIMESTAMP WHERE version = %s;",
                    (description, checksum, execution_time_ms, status, version),
                )
            else:
                cursor.execute(
                    "INSERT INTO _schema_migrations (version, description, checksum, execution_time_ms, status) "
                    "VALUES (%s, %s, %s, %s, %s);",
                    (version, description, checksum, execution_time_ms, status),
                )

    def run_migrations(self, migrations_dir: Optional[Path] = None, conn=None) -> List[str]:
        """
        Executes pending forward schema migrations in alphanumeric order with SHA-256 checksum protection.
        
        Failure & Retry Policy:
        - If a previously SUCCESSFUL migration file has been altered, raises MigrationChecksumError and aborts.
        - If a migration statement fails, it is recorded as 'FAILED' and raises MigrationExecutionError.
        - Failed migrations can be safely retried once fixed; a successful retry updates the existing
          audit record to 'SUCCESS' without duplicate key violations.
        - In SQLite, statement failures rollback transactionally.
        - In MySQL, MySQL DDL statements (CREATE/ALTER/DROP) invoke implicit commits at the engine level;
          failed migrations require non-destructive idempotent statements or administrator inspection.
        """
        mgr_dir = migrations_dir or (DATABASE_DIR / "migrations")
        if not mgr_dir.exists():
            return []

        close_at_end = False
        if conn is None:
            conn = self.get_connection()
            close_at_end = True

        self.init_migration_table(conn=conn)
        cursor = conn.cursor()

        # Step 1: Query already applied successful migrations and their recorded checksums
        cursor.execute("SELECT version, checksum FROM _schema_migrations WHERE status = 'SUCCESS';")
        applied_records = {
            (row["version"] if isinstance(row, dict) else row[0]): (row["checksum"] if isinstance(row, dict) else row[1])
            for row in cursor.fetchall()
        }

        migration_files = sorted(mgr_dir.glob("*.sql"))

        # Step 2: Cryptographic Checksum Integrity Check on all previously successful migrations
        for m_file in migration_files:
            version = m_file.stem
            if version in applied_records:
                current_checksum = self.compute_file_checksum(m_file)
                recorded_checksum = applied_records[version]
                if current_checksum != recorded_checksum:
                    raise MigrationChecksumError(
                        f"CRITICAL: Schema Migration Checksum Violation!\n"
                        f"Migration '{version}' ({m_file.name}) was already applied to the database, "
                        f"but the file contents have been modified.\n"
                        f"Expected SHA-256: {recorded_checksum}\n"
                        f"Calculated SHA-256: {current_checksum}\n"
                        f"Data warehouse migrations are strictly immutable and forward-only. "
                        f"Revert '{m_file.name}' or apply a new forward migration script."
                    )

        # Step 3: Apply pending or previously failed migrations
        applied_this_run = []
        for m_file in migration_files:
            version = m_file.stem
            if version in applied_records or version.startswith("_"):
                continue

            file_checksum = self.compute_file_checksum(m_file)
            logger.info(f"Applying schema migration: {version} ({m_file.name}) [SHA-256: {file_checksum[:8]}...]")
            t0 = time.time()

            try:
                self.execute_script(m_file, conn=conn)
                elapsed_ms = int((time.time() - t0) * 1000)

                self._record_migration_result(
                    cursor,
                    version=version,
                    description=f"Applied from {m_file.name}",
                    checksum=file_checksum,
                    execution_time_ms=elapsed_ms,
                    status="SUCCESS",
                )
                conn.commit()
                applied_this_run.append(version)
            except Exception as e:
                if self.engine_type == "sqlite":
                    conn.rollback()
                logger.error(f"Migration {version} failed: {e}")
                try:
                    self._record_migration_result(
                        cursor,
                        version=version,
                        description=f"FAILED: {str(e)[:200]}",
                        checksum=file_checksum,
                        execution_time_ms=0,
                        status="FAILED",
                    )
                    conn.commit()
                except Exception as record_err:
                    logger.warning(f"Failed to record migration failure state: {record_err}")
                raise MigrationExecutionError(f"Migration '{version}' failed: {e}") from e

        if close_at_end:
            conn.close()

        return applied_this_run


def get_db_manager(engine_type: Optional[str] = None) -> DatabaseManager:
    return DatabaseManager(engine_type=engine_type)
