import pytest
from dotenv import find_dotenv, load_dotenv
from envparse import env

from simplepg import DbConnection


load_dotenv(find_dotenv())


@pytest.fixture(scope="session")
def db_connection():
    return DbConnection(
        user="postgres",
        password=env.str("POSTGRES_PASSWORD"),
        host="localhost",
        port=5432,
        database="postgres",
        connect_kwargs={},
        pool_min_connections=1,
        pool_max_connections=1,
    )


@pytest.mark.integration
def test_insert_and_fetch(db_connection: DbConnection):
    db_connection.execute("DROP TABLE IF EXISTS test_table")
    db_connection.execute("CREATE TABLE test_table (id SERIAL PRIMARY KEY, name VARCHAR)")
    db_connection.execute("INSERT INTO test_table (name) VALUES ('test')")
    records, columns = db_connection.execute_and_fetchall("SELECT * FROM test_table")
    db_connection.execute("DROP TABLE IF EXISTS test_table")
    assert records == [(1, "test")]
    assert columns == ["id", "name"]


@pytest.mark.integration
def test_executemany(db_connection: DbConnection):
    db_connection.execute("DROP TABLE IF EXISTS test_table")
    db_connection.execute("CREATE TABLE test_table (id SERIAL PRIMARY KEY, name VARCHAR)")
    db_connection.executemany(
        "INSERT INTO test_table (name) VALUES (%s)", [("test1",), ("test2",)]
    )
    records, columns = db_connection.execute_and_fetchall("SELECT * FROM test_table")
    db_connection.execute("DROP TABLE IF EXISTS test_table")
    assert records == [(1, "test1"), (2, "test2")]
    assert columns == ["id", "name"]


@pytest.mark.integration
def test_execute_values(db_connection: DbConnection):
    db_connection.execute("DROP TABLE IF EXISTS test_table")
    db_connection.execute("CREATE TABLE test_table (id SERIAL PRIMARY KEY, name VARCHAR)")
    db_connection.execute_values(
        "INSERT INTO test_table (name) VALUES %s", [("test1",), ("test2",)]
    )
    records, columns = db_connection.execute_and_fetchall("SELECT * FROM test_table")
    db_connection.execute("DROP TABLE IF EXISTS test_table")
    assert records == [(1, "test1"), (2, "test2")]
    assert columns == ["id", "name"]
