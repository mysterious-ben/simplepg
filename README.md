# SimplePG

Simple PostgreSQL connections: a wrapper around psycopg2.

Features:
- Thread-safe connection pooling
- Auto-reconnect on connection loss
- Unified interface for execute, executemany, and execute_values

## Installation

```bash
pip install simplepg
```

## Example

```python
from simplepg import DbConnection

db = DbConnection(
    user="postgres",
    password="postgres",
    host="localhost",
    port=5432,
    database="postgres",
    connect_kwargs={},
    pool_min_connections=1,
    pool_max_connections=1,
)

db.execute("CREATE TABLE test_table (id SERIAL PRIMARY KEY, name VARCHAR)")
db.execute_values("INSERT INTO test_table (name) VALUES %s", [("test1",), ("test2",)])
records, columns = db.execute("SELECT * FROM test_table")
db.execute("DROP TABLE test_table")
```
