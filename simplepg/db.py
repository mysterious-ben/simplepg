import functools
from time import sleep
from typing import Callable, Dict, List, NamedTuple, Optional, Union

import psycopg2
from loguru import logger
from psycopg2.errors import InterfaceError, OperationalError


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
            logger.info(f"db connection lost: {str(e)}")
            sleep(self._postgres_reconnect_delay)  # pylint: disable=protected-access
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
        postgres_reconnect_delay: int,
        cast_decimal_to_float: bool = True,
    ):
        self._psycopg2_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"
        self._connect_kwargs = connect_kwargs
        self._conn = psycopg2.connect(self._psycopg2_url, **self._connect_kwargs)
        self._postgres_reconnect_delay = postgres_reconnect_delay

    def is_valid(self) -> bool:
        return True

    def _reconnect(self):
        self._conn.close()
        self._conn = psycopg2.connect(self._psycopg2_url, **self._connect_kwargs)

    @_reconnect_retry
    def execute(self, sql: str, vars_: Optional[Union[List, Dict]] = None) -> int:
        """Execute an arbitrary SQL query

        Args:
            sql: an SQL statement
            vars: https://www.psycopg.org/docs/usage.html#query-parameters
        """
        with self._conn, self._conn.cursor() as c:
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
            Fetched records and their description
        """

        with self._conn, self._conn.cursor() as c:
            c.execute(sql, vars_)
            records: List = c.fetchall()
            columns: List[str] = [column.name for column in c.description]
            return FetchResult(records, columns)
