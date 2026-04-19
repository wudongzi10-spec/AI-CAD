import datetime
import json
import os
import sqlite3

from config import BASE_DIR


class DatabaseManager:
    """
    Database access layer for history, aggregate stats, and app settings.
    """

    def __init__(self, db_name="cad_system.db"):
        self.db_path = os.path.join(BASE_DIR, "database", db_name)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            self._create_history_table(cursor, "model_history")
            self._create_settings_table(cursor, "app_settings")
            conn.commit()

            self._ensure_column(conn, "model_history", "template_id", "TEXT DEFAULT ''")
            self._ensure_column(conn, "model_history", "source_record_id", "INTEGER")
            self._reindex_history_table(conn)

    def _create_history_table(self, cursor, table_name):
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_instruction TEXT NOT NULL,
                parsed_json TEXT,
                file_path TEXT,
                status TEXT NOT NULL,
                template_id TEXT DEFAULT '',
                source_record_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _create_settings_table(self, cursor, table_name):
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    def _ensure_column(self, conn, table_name, column_name, definition):
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = {row["name"] for row in cursor.fetchall()}
        if column_name not in columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
            conn.commit()

    def _reindex_history_table(self, conn):
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, user_instruction, parsed_json, file_path, status, template_id, source_record_id, created_at
            FROM model_history
            ORDER BY created_at ASC, id ASC
            """
        )
        rows = cursor.fetchall()
        if not rows:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'model_history'")
            conn.commit()
            return {}

        id_mapping = {row["id"]: index for index, row in enumerate(rows, start=1)}
        cursor.execute("DROP TABLE IF EXISTS model_history_reindexed")
        self._create_history_table(cursor, "model_history_reindexed")

        for old_row in rows:
            new_source_record_id = old_row["source_record_id"]
            if new_source_record_id is not None:
                new_source_record_id = id_mapping.get(new_source_record_id)

            cursor.execute(
                """
                INSERT INTO model_history_reindexed (
                    id,
                    user_instruction,
                    parsed_json,
                    file_path,
                    status,
                    template_id,
                    source_record_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    id_mapping[old_row["id"]],
                    old_row["user_instruction"],
                    old_row["parsed_json"],
                    old_row["file_path"],
                    old_row["status"],
                    old_row["template_id"] or "",
                    new_source_record_id,
                    old_row["created_at"],
                ),
            )

        cursor.execute("DROP TABLE model_history")
        cursor.execute("ALTER TABLE model_history_reindexed RENAME TO model_history")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name = 'model_history'")
        cursor.execute(
            "INSERT INTO sqlite_sequence(name, seq) VALUES ('model_history', ?)",
            (len(rows),),
        )
        conn.commit()
        return id_mapping

    def _vacuum_database(self):
        with self._connect() as conn:
            conn.execute("VACUUM")
            conn.commit()

    def _row_to_dict(self, row):
        parsed_json = row["parsed_json"]
        parsed_json_obj = None
        if parsed_json:
            try:
                parsed_json_obj = json.loads(parsed_json)
            except (TypeError, json.JSONDecodeError):
                parsed_json_obj = None

        return {
            "id": row["id"],
            "instruction": row["user_instruction"],
            "parsed_json": parsed_json,
            "parsed_json_obj": parsed_json_obj,
            "file_path": row["file_path"],
            "status": row["status"],
            "template_id": row["template_id"] or "",
            "source_record_id": row["source_record_id"],
            "created_at": row["created_at"],
        }

    def insert_history(
        self,
        instruction,
        parsed_json="",
        file_path="",
        status="success",
        template_id="",
        source_record_id=None,
    ):
        json_str = json.dumps(parsed_json, ensure_ascii=False) if isinstance(parsed_json, dict) else parsed_json

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO model_history (
                    user_instruction,
                    parsed_json,
                    file_path,
                    status,
                    template_id,
                    source_record_id,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    instruction,
                    json_str,
                    file_path,
                    status,
                    template_id or "",
                    source_record_id,
                    datetime.datetime.now(),
                ),
            )
            inserted_id = cursor.lastrowid
            id_mapping = self._reindex_history_table(conn)
            return id_mapping.get(inserted_id, inserted_id)

    def get_all_history(self, keyword="", status_filter="all", limit=50):
        query = """
            SELECT id, user_instruction, parsed_json, file_path, status, template_id, source_record_id, created_at
            FROM model_history
        """
        conditions = []
        params = []

        if keyword:
            conditions.append("user_instruction LIKE ?")
            params.append(f"%{keyword}%")

        if status_filter == "success":
            conditions.append("status = 'success'")
        elif status_filter == "error":
            conditions.append("status != 'success'")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [self._row_to_dict(row) for row in cursor.fetchall()]

    def get_history_by_id(self, record_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, user_instruction, parsed_json, file_path, status, template_id, source_record_id, created_at
                FROM model_history
                WHERE id = ?
                """,
                (record_id,),
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def delete_history(self, record_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM model_history WHERE id = ?", (record_id,))
            deleted_rows = cursor.rowcount
            if deleted_rows:
                self._reindex_history_table(conn)

        if deleted_rows:
            self._vacuum_database()
        return deleted_rows

    def get_file_path(self, record_id):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_path FROM model_history WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return row["file_path"] if row else None

    def get_history_stats(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success_count,
                    SUM(CASE WHEN status != 'success' THEN 1 ELSE 0 END) AS failure_count,
                    SUM(CASE WHEN DATE(created_at) = DATE('now', 'localtime') THEN 1 ELSE 0 END) AS today_count,
                    SUM(CASE WHEN template_id IS NOT NULL AND template_id != '' THEN 1 ELSE 0 END) AS template_count,
                    SUM(CASE WHEN source_record_id IS NOT NULL THEN 1 ELSE 0 END) AS regenerated_count
                FROM model_history
                """
            )
            summary = cursor.fetchone()

            cursor.execute(
                """
                SELECT user_instruction, created_at, file_path
                FROM model_history
                WHERE status = 'success'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            latest_success = cursor.fetchone()

            cursor.execute(
                """
                SELECT template_id, COUNT(*) AS usage_count
                FROM model_history
                WHERE template_id IS NOT NULL AND template_id != ''
                GROUP BY template_id
                ORDER BY usage_count DESC, template_id ASC
                LIMIT 1
                """
            )
            top_template = cursor.fetchone()

        total_count = summary["total_count"] or 0
        success_count = summary["success_count"] or 0
        failure_count = summary["failure_count"] or 0

        return {
            "total_count": total_count,
            "success_count": success_count,
            "failure_count": failure_count,
            "today_count": summary["today_count"] or 0,
            "template_count": summary["template_count"] or 0,
            "regenerated_count": summary["regenerated_count"] or 0,
            "success_rate": round((success_count / total_count) * 100, 2) if total_count else 0.0,
            "latest_success": {
                "instruction": latest_success["user_instruction"],
                "created_at": latest_success["created_at"],
                "file_path": latest_success["file_path"],
            }
            if latest_success
            else None,
            "top_template_id": top_template["template_id"] if top_template else "",
        }

    def get_setting(self, key, default=None):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM app_settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default

    def set_setting(self, key, value):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (key, value),
            )
            conn.commit()

    def delete_setting(self, key):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM app_settings WHERE key = ?", (key,))
            conn.commit()
            return cursor.rowcount

    def healthcheck(self):
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except sqlite3.Error:
            return False
