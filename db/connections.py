import json
import psycopg2

def load_config():
    with open("db/config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def connect_to_db(dbname: str | None = None):
    cfg = load_config()
    if dbname is None:
        dbname = cfg.get("database", "postgres")
    return psycopg2.connect(
        dbname=dbname,
        user=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg["port"],
    )

def ensure_database_exists() -> bool:
    cfg = load_config()
    target_db = cfg.get("database", "postgres")

    try:
        con = connect_to_db(target_db)
        con.close()
        return False
    except Exception:
        pass

    con = connect_to_db("postgres")
    con.autocommit = True
    cur = con.cursor()
    try:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (target_db,))
        exists = cur.fetchone() is not None
        if not exists:
            cur.execute(f"CREATE DATABASE {target_db}")
            created = True
        else:
            created = False
    finally:
        cur.close()
        con.close()
    return created
