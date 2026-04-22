import os
import re
import psycopg2


class CompatRow(dict):
    def __init__(self, keys, values):
        super().__init__(zip(keys, values))
        self._values = list(values)

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return super().__getitem__(key)


class CompatCursor:
    def __init__(self, cursor):
        self._cursor = cursor
        self._keys = []
        self._empty_result = None

    def _rewrite_insert_or_replace(self, stmt):
        match = re.match(
            r'^INSERT\s+OR\s+REPLACE\s+INTO\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)\s*;?$',
            stmt,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        table_name = match.group(1)
        columns = [column.strip().strip('"') for column in match.group(2).split(',')]
        values_clause = match.group(3).strip()
        conflict_column = 'id' if 'id' in columns else columns[0]
        update_columns = [column for column in columns if column != conflict_column]

        if update_columns:
            updates = ', '.join(f'{column}=EXCLUDED.{column}' for column in update_columns)
            return (
                f'INSERT INTO {table_name} ({", ".join(columns)}) '
                f'VALUES ({values_clause}) '
                f'ON CONFLICT ({conflict_column}) DO UPDATE SET {updates}'
            )

        return (
            f'INSERT INTO {table_name} ({", ".join(columns)}) '
            f'VALUES ({values_clause}) '
            f'ON CONFLICT ({conflict_column}) DO NOTHING'
        )

    def _rewrite_sql(self, sql):
        stmt = (sql or "").strip()
        if not stmt:
            return stmt, None

        up = stmt.upper()
        if up.startswith("PRAGMA "):
            m = re.match(r"^PRAGMA\s+TABLE_INFO\(([^\)]+)\)\s*$", stmt, flags=re.IGNORECASE)
            if m:
                table_name = m.group(1).strip().strip('"\'')
                qry = (
                    "SELECT (ordinal_position - 1) AS cid, "
                    "column_name AS name, data_type AS type, "
                    "0 AS notnull, column_default AS dflt_value, 0 AS pk "
                    "FROM information_schema.columns "
                    "WHERE table_schema='public' AND table_name=%s "
                    "ORDER BY ordinal_position"
                )
                return qry, (table_name,)
            return None, []

        if "FROM SQLITE_MASTER" in up:
            if "COUNT(*)" in up and "AND NAME=" in up:
                return (
                    "SELECT COUNT(*) "
                    "FROM information_schema.tables "
                    "WHERE table_schema='public' "
                    "AND table_type='BASE TABLE' "
                    "AND table_name=%s"
                ), None
            return (
                "SELECT table_name AS name "
                "FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE'"
            ), None

        stmt = re.sub(
            r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT",
            "BIGSERIAL PRIMARY KEY",
            stmt,
            flags=re.IGNORECASE,
        )

        if re.search(r"INSERT\s+OR\s+REPLACE\s+INTO", stmt, flags=re.IGNORECASE):
            rewritten = self._rewrite_insert_or_replace(stmt)
            if rewritten:
                stmt = rewritten
            else:
                stmt = re.sub(r"INSERT\s+OR\s+REPLACE\s+INTO", "INSERT INTO", stmt, flags=re.IGNORECASE)

        if re.search(r"INSERT\s+OR\s+IGNORE\s+INTO", stmt, flags=re.IGNORECASE):
            stmt = re.sub(r"INSERT\s+OR\s+IGNORE\s+INTO", "INSERT INTO", stmt, flags=re.IGNORECASE)
            if "ON CONFLICT" not in stmt.upper():
                stmt = stmt.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

        stmt = stmt.replace("?", "%s")
        return stmt, None

    def execute(self, sql, params=None):
        rewritten, forced_params = self._rewrite_sql(sql)
        if rewritten is None:
            self._keys = []
            self._empty_result = forced_params or []
            return self

        run_params = forced_params if forced_params is not None else params
        if run_params is None:
            self._cursor.execute(rewritten)
        else:
            self._cursor.execute(rewritten, run_params)
        self._keys = [d[0] for d in self._cursor.description] if self._cursor.description else []
        self._empty_result = None
        return self

    def executemany(self, sql, seq_of_params):
        rewritten, forced_params = self._rewrite_sql(sql)
        if rewritten is None:
            self._keys = []
            self._empty_result = []
            return self
        if forced_params is not None:
            raise RuntimeError("Forced SQL params are not supported with executemany")
        self._cursor.executemany(rewritten, seq_of_params)
        self._keys = [d[0] for d in self._cursor.description] if self._cursor.description else []
        self._empty_result = None
        return self

    def fetchone(self):
        if self._empty_result is not None:
            return None
        row = self._cursor.fetchone()
        if row is None:
            return None
        return CompatRow(self._keys, row)

    def fetchall(self):
        if self._empty_result is not None:
            return []
        rows = self._cursor.fetchall()
        return [CompatRow(self._keys, row) for row in rows]

    @property
    def rowcount(self):
        return self._cursor.rowcount

    def close(self):
        self._cursor.close()


class CompatConnection:
    def __init__(self, dsn):
        self._conn = psycopg2.connect(dsn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self._conn.commit()
            else:
                self._conn.rollback()
        finally:
            self._conn.close()

    def cursor(self):
        return CompatCursor(self._conn.cursor())

    def execute(self, sql, params=None):
        cur = self.cursor()
        return cur.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        cur = self.cursor()
        return cur.executemany(sql, seq_of_params)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


def connect_db(database_url=None):
    dsn = (database_url or os.getenv("DATABASE_URL") or "postgresql://postgres:postgres@localhost:5432/davs").strip()
    return CompatConnection(dsn)
