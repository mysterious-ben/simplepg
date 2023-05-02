import functools
from contextlib import contextmanager
from time import sleep
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple, Union

import psycopg2
from loguru import logger
from psycopg2 import pool
from psycopg2.errors import InterfaceError, OperationalError
from psycopg2.extras import execute_values


def set_cast_decimal_to_float():
    DEC2FLOAT = psycopg2.extensions.new_type(
        psycopg2.extensions.DECIMAL.values,
        "DEC2FLOAT",
        lambda value, curs: float(value) if value is not None else None,
    )
    psycopg2.extensions.register_type(DEC2FLOAT)


def _reconnect_retry(f: Callable) -> Callable:
    @functools.wraps(f)
    def wrapper(self: "DbConnection", *args, **kwargs):
        try:
            return f(self, *args, **kwargs)
        except (OperationalError, InterfaceError) as e:  # type: ignore
            if self.postgres_reconnect_delay is None:
                raise e from e
            else:
                logger.info(f"db connection lost: {str(e)}")
                sleep(self.postgres_reconnect_delay)  # pylint: disable=protected-access
                self._reconnect()  # pylint: disable=protected-access
                logger.warning(f"db reconnected: {str(e)}")
            return f(self, *args, **kwargs)

    return wrapper


class FetchResult(NamedTuple):
    records: List
    columns: List[str]

    def as_records(self) -> List[Dict]:
        return [dict(zip(self.columns, x)) for x in self.records]


class DbConnection:
    """Postgres DB connection manager"""

    def __init__(
        self,
        user: str,
        password: str,
        host: str,
        port: int,
        database: str,
        connect_kwargs: dict,
        pool_min_connections: int,
        pool_max_connections: int,
        postgres_reconnect_delay: Optional[int] = 5,
    ):
        """
        Postgres DB connection manager

        Args:
            user: str - username
            password: str - password
            host: str - host
            port: int - port
            database: str - database name
            connect_kwargs: dict - connection kwargs
            pool_min_connections: int - minimum number of pool connections
            pool_max_connections: int - maximum number of pool connections
            postgres_reconnect_delay: Optional[int] = 5 - postgres reconnect delay (seconds)
        """

        self.psycopg2_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self.connect_kwargs = connect_kwargs
        self.pool_min_connections = pool_min_connections
        self.pool_max_connections = pool_max_connections
        # self._conn = psycopg2.connect(self._psycopg2_url, **self._connect_kwargs)
        self._conn_pool = pool.ThreadedConnectionPool(
            self.pool_min_connections,
            self.pool_max_connections,
            self.psycopg2_url,
            **self.connect_kwargs,
        )
        self.postgres_reconnect_delay = postgres_reconnect_delay

    def is_valid(self) -> bool:
        return True

    def _reconnect(self):
        # self._conn.close()
        # self._conn = psycopg2.connect(self._psycopg2_url, **self._connect_kwargs)
        self._conn_pool.closeall()
        self._conn_pool = pool.ThreadedConnectionPool(
            self.pool_min_connections,
            self.pool_max_connections,
            self.psycopg2_url,
            **self.connect_kwargs,
        )

    @property
    @contextmanager
    def _conn(self):
        conn = self._conn_pool.getconn()
        try:
            yield conn
        except Exception as e:
            conn.rollback()
            raise e
        else:
            conn.commit()
        self._conn_pool.putconn(conn)

    @_reconnect_retry
    def execute(self, sql: str, vars_: Optional[Union[List, Dict]] = None) -> int:
        """Execute an arbitrary SQL query

        Args:
            sql: an SQL statement
            vars: https://www.psycopg.org/docs/usage.html#query-parameters

        Returns:
            Number of rows affected

        Example:
            db.execute("DROP TABLE IF EXISTS table")
        """
        with self._conn as conn:
            with conn.cursor() as c:
                c.execute(sql, vars_)
                rowcount = c.rowcount
        return rowcount

    @_reconnect_retry
    def execute_and_fetchall(
        self, sql: str, vars_: Optional[Union[List, Dict]] = None
    ) -> FetchResult:
        """Execute a SELECT SQL query and fetch results

        Args:
            sql: an SQL statement
            vars: https://www.psycopg.org/docs/usage.html#query-parameters

        Returns:
            Fetched records and column names

        Example:
            records, columns = db.execute_and_fetchall("SELECT * FROM table")
        """

        with self._conn as conn:
            with conn.cursor() as c:
                c.execute(sql, vars_)
                records: List = c.fetchall()
                columns: List[str] = [column.name for column in c.description]
        return FetchResult(records, columns)

    @_reconnect_retry
    def executemany(self, sql: str, rows: Tuple[Tuple]) -> int:
        """Execute an SQL query with multiple rows (slow version)

        This method is slow: it's the same as executing commands in a loop.
        Use execute_values to speed the things up.

        Returns:
            Number of rows affected

        Example:
            row_count = db.executemany("INSERT INTO table VALUES (%s, %s)", [(1, 2), (3, 4)])
        """

        with self._conn as conn:
            with conn.cursor() as c:
                c.executemany(sql, rows)
                rowcount = c.rowcount
        return rowcount

    @_reconnect_retry
    def execute_values(self, sql: str, rows: Tuple[Tuple], page_size: int = 10000) -> int:
        """Execute an SQL query with multiple rows (fast version)

        Returns:
            Number of rows affected

        Example:
            row_count = db.execute_values("INSERT INTO table VALUES %s", [(1, 2), (3, 4)])
        """

        with self._conn as conn:
            with conn.cursor() as c:
                execute_values(c, sql, rows, template=None, page_size=page_size, fetch=False)
                rowcount = c.rowcount
        return rowcount
