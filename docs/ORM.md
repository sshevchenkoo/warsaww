# How the backend talks to Postgres (SQLAlchemy)

> Related: [data-model.md](data-model.md) has the tables, [SEARCH.md](SEARCH.md) §4.2 the
> short-lived session on `/search`, [SECURITY.md](SECURITY.md) §5 the Row-Level Security policies.

The backend uses SQLAlchemy 2 as its ORM. This page follows one request, `DELETE /me/avatar`,
from the HTTP call to the SQL that reaches the database, and ends with how the endpoint is tested
without one.

## 1. The three layers

| Layer | Where | What it does |
|---|---|---|
| **Engine + connection pool** | `backend/app/catalog/db.py` (`create_engine`) | Keeps open connections to Postgres and lends them to sessions. `db_pool_size=5` plus `db_max_overflow=5` per process. |
| **Session** | `SessionLocal()`, handed out by `get_session()` | One unit of work per request: runs the transaction, tracks loaded objects, sends SQL. |
| **Models** | `backend/app/catalog/models.py` | A Python class per table. `UserAvatar` is `user_avatars`, its `Mapped[...]` attributes are columns. |

`session.get(User, id)` becomes `SELECT … FROM users WHERE id = …` and returns a `User` object.

## 2. One session per request

```python
def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
```

FastAPI runs this for every `Depends(get_session)`. It caches a dependency within a request, so the
endpoint and `current_user` (which also depends on `get_session`) share **the same session**. When the
response is done, the `with` block closes the session: anything not committed is rolled back and the
connection goes back to the pool.

## 3. `DELETE /me/avatar`, step by step

```python
@router.delete("/me/avatar")
def delete_avatar(user: User = Depends(current_user), session: Session = Depends(get_session)):
    session.query(UserAvatar).filter(UserAvatar.user_id == user.id).delete()
    db_user = session.get(User, user.id)
    db_user.avatar_url = None
    session.commit()
```

**Before the endpoint runs**, `current_user` (`backend/app/auth/deps.py`) calls
`session.get(User, …)` and then `SELECT set_config('app.user_id', …, true)` for RLS. The first
statement makes the session open a transaction on its own (*autobegin*), so everything below runs
inside that same transaction.

**`UserAvatar.user_id == user.id`** does not evaluate to `True`/`False`. SQLAlchemy overloads `==` on
columns to build an SQL expression, `user_avatars.user_id = :param`.

**`.query(...).filter(...).delete()`** is a *bulk delete*. It sends `DELETE FROM user_avatars WHERE …`
right away without loading any rows, and returns the number of rows deleted (the endpoint ignores
it). The row is gone inside the transaction only. Other connections still see it until the commit.

**`session.get(User, user.id)`** looks in the session's *identity map* first: a dict of
`(class, primary key) → object` for everything this session has loaded. `current_user` already loaded
this user, so `get` returns that same object (`db_user is user`) and sends no SQL.

**`db_user.avatar_url = None`** sends nothing yet. The session marks the object *dirty* and remembers
which column changed.

**`session.commit()`** does three things:

1. **Flush.** Turns pending changes into SQL: `UPDATE users SET avatar_url = NULL WHERE id = …`.
2. **COMMIT.** Postgres applies the DELETE and the UPDATE together, or neither.
3. **Expire.** Every object in the identity map is marked stale, so the next attribute read reloads
   it from the database. This is why [SEARCH.md](SEARCH.md) §4.2 commits *before* loading items.

What reaches Postgres for this request:

```sql
BEGIN;
SELECT … FROM users WHERE users.id = 'e45b…';          -- current_user
SELECT set_config('app.user_id', 'e45b…', true);       -- current_user, RLS
DELETE FROM user_avatars WHERE user_avatars.user_id = 'e45b…';
UPDATE users SET avatar_url = NULL WHERE users.id = 'e45b…';
COMMIT;
```

## 4. When something goes wrong

- **No `commit()`.** The `with` block in `get_session` rolls back at the end of the request. The DELETE
  and the UPDATE are both undone and the photo stays.
- **An exception half-way** (say the UPDATE is refused). The commit never runs, the rollback also undoes
  the DELETE, and the database is never left with the bytes gone but `avatar_url` still pointing at them.

## 5. Testing without a database

`backend/tests/test_avatars.py` calls `delete_avatar()` directly with a fake session instead of a real
one. The endpoint touches the session through five methods only, so the fake implements just those:

| Real session | Fake `_Session` |
|---|---|
| `query().filter()` builds a query | `return self`: the condition is ignored |
| `.delete()` sends DELETE, returns the row count | drops the id from a set, returns 0 or 1 |
| `get()` checks the identity map, then SELECTs | returns the one `_User` it holds |
| attribute change, UPDATE at flush | attribute changes in memory at once |
| `commit()`: flush + COMMIT + expire | `commits += 1` |

The fake proves the endpoint calls the right methods and commits exactly once
(`assert session.commits == 1`). If the endpoint forgot to commit, the in-memory change would still
make the other asserts pass, which is why the counter is there. What the fake cannot prove: that the SQL is right, or that the
`WHERE` limits the delete to the caller, since `filter()` ignores its argument. That needs the
DB-integration tests on the `clean_db` fixture (`backend/tests/conftest.py`), which are skipped when no
test database is available.
