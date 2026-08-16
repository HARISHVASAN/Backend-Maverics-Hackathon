from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BACKEND_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "citizen_intelligence.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_keywords_column() -> None:
    """Additive, non-destructive migration for pre-existing SQLite files that
    predate the Complaint.keywords column. Safe to call on every startup:
    it's a no-op once the column exists (including on a brand-new database,
    where create_all() already includes it)."""
    with engine.connect() as conn:
        columns = [row[1] for row in conn.exec_driver_sql("PRAGMA table_info(complaints)")]
        if columns and "keywords" not in columns:
            conn.exec_driver_sql("ALTER TABLE complaints ADD COLUMN keywords TEXT")
            conn.commit()
