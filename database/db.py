import sqlite3
from flask import g, current_app

def get_db():
    if "db" not in g:
        conn = sqlite3.connect(current_app.config["DATABASE"])
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        g.db = conn
    return g.db

def close_db(error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS projects (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      description TEXT DEFAULT '',
      repo_url TEXT DEFAULT '',
      language TEXT DEFAULT 'Python',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS analyses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      health_score INTEGER NOT NULL,
      files_scanned INTEGER NOT NULL,
      issue_count INTEGER NOT NULL,
      findings_json TEXT NOT NULL,
      summary_json TEXT NOT NULL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS issues (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
      analysis_id INTEGER REFERENCES analyses(id) ON DELETE CASCADE,
      title TEXT NOT NULL,
      severity TEXT NOT NULL,
      category TEXT NOT NULL,
      file_path TEXT DEFAULT '',
      line_number INTEGER DEFAULT 0,
      description TEXT DEFAULT '',
      status TEXT NOT NULL DEFAULT 'Open',
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    columns = {row[1] for row in db.execute("PRAGMA table_info(analyses)")}
    if "defected_files" not in columns:
        db.execute("ALTER TABLE analyses ADD COLUMN defected_files INTEGER NOT NULL DEFAULT 0")
    db.commit()
