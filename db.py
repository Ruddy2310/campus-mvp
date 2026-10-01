"""Small MySQL helper layer (PyMySQL). All queries use %s placeholders."""
from contextlib import contextmanager

import pymysql
import pymysql.cursors
from flask import current_app, g


def get_db():
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["DB_HOST"],
            port=cfg["DB_PORT"],
            user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"],
            database=cfg["DB_NAME"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query_all(sql, params=()):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    conn.commit()  # ends the read snapshot so later reads see fresh data
    return rows


def query_one(sql, params=()):
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
    conn.commit()
    return row


def execute(sql, params=()):
    """Run one write statement and commit. Returns (rowcount, lastrowid)."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            result = (cur.rowcount, cur.lastrowid)
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise


@contextmanager
def transaction():
    """Several statements, one commit. Rolls back on any error."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
