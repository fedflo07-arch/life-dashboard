"""
database.py

Gestisce la connessione a SQLite e l'inizializzazione dello schema.
Tutte le tabelle vengono create automaticamente se non esistono già,
quindi non serve nessun passaggio manuale di setup: basta avviare l'app.
"""

import sqlite3
import os

# Il file del database vive nella cartella data/, così è facile
# escluderlo da git (vedi .gitignore) e tenerlo separato dal codice.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "life_dashboard.db")


def get_connection():
    """Crea una connessione a SQLite con accesso alle colonne per nome."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Abilita i vincoli di chiave esterna (SQLite li ignora di default).
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Crea le tabelle se non esistono e inserisce le impostazioni di default."""
    os.makedirs(DATA_DIR, exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    # --- Diario alimentare -------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS food_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            meal TEXT NOT NULL,
            food_name TEXT NOT NULL,
            quantity TEXT,
            calories REAL NOT NULL DEFAULT 0,
            protein REAL NOT NULL DEFAULT 0,
            carbs REAL NOT NULL DEFAULT 0,
            fats REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- Peso corporeo -------------------------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS weight_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            weight_kg REAL NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- Spese ed entrate -------------------------------------------------
    # type: 'expense' (spesa) o 'income' (entrata). Stessa tabella per
    # entrambe così i filtri per data/categoria funzionano su tutto il
    # flusso di denaro, non solo sulle uscite.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            type TEXT NOT NULL DEFAULT 'expense',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Retrocompatibilità: se il database esisteva già prima dell'introduzione
    # della colonna 'type' (versioni precedenti dell'app), la aggiunge senza
    # perdere i dati già inseriti. Tutte le righe esistenti sono spese, quindi
    # il default 'expense' è corretto per loro.
    cur.execute("PRAGMA table_info(expenses)")
    existing_columns = [row["name"] for row in cur.fetchall()]
    if "type" not in existing_columns:
        cur.execute("ALTER TABLE expenses ADD COLUMN type TEXT NOT NULL DEFAULT 'expense'")

    # --- Statistiche giornaliere (una riga per giorno) -------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS daily_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            sleep_hours REAL,
            study_hours REAL,
            reading_minutes REAL,
            water_liters REAL,
            gym INTEGER DEFAULT 0,
            steps INTEGER,
            mood INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- Impostazioni (una sola riga, id=1) -------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            calorie_target REAL NOT NULL DEFAULT 2200,
            protein_target REAL NOT NULL DEFAULT 160,
            currency TEXT NOT NULL DEFAULT 'EUR'
        )
    """)

    # --- Esami universitari (libretto) -------------------------------
    # status: 'planned' (data prevista, non ancora sostenuto) o 'passed' (superato, con voto)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS exams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cfu REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'planned',
            exam_date TEXT,
            grade INTEGER,
            honors INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- Orario lezioni settimanale (si ripete ogni settimana) -------------------------------
    # day_of_week: 0=Lunedì ... 6=Domenica (stessa convenzione di date.weekday() in Python)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS class_schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name TEXT NOT NULL,
            day_of_week INTEGER NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            location TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # --- Impostazioni università (obiettivi accademici) -------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS university_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            target_average REAL,
            total_cfu_required REAL NOT NULL DEFAULT 180,
            thesis_points REAL NOT NULL DEFAULT 0,
            bonus_points REAL NOT NULL DEFAULT 0
        )
    """)

    cur.execute("SELECT COUNT(*) AS c FROM university_settings WHERE id = 1")
    if cur.fetchone()["c"] == 0:
        cur.execute("""
            INSERT INTO university_settings (id, target_average, total_cfu_required, thesis_points, bonus_points)
            VALUES (1, NULL, 180, 0, 0)
        """)

    # Inserisce la riga di default delle impostazioni se non esiste ancora.
    cur.execute("SELECT COUNT(*) AS c FROM settings WHERE id = 1")
    if cur.fetchone()["c"] == 0:
        cur.execute("""
            INSERT INTO settings (id, calorie_target, protein_target, currency)
            VALUES (1, 2200, 160, 'EUR')
        """)

    conn.commit()
    conn.close()
