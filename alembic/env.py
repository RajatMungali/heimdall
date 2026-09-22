import os
import sys
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# ── Load .env files — but do NOT let SQLite DATABASE_URL win
load_dotenv("backend/.env")
load_dotenv(".env")

# ── Alembic Config object
config = context.config

# ── Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Make backend package importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Import all ORM models (autogenerate reads their metadata)
from backend.database import Base  # noqa: F401
import backend.models  # noqa: F401 — registers all ORM tables
target_metadata = Base.metadata

# ── Resolve DATABASE_URL — always prefer Postgres for Alembic migrations
# Never fall back to SQLite; use local Docker container URL as default
_raw_url = os.getenv("DATABASE_URL", "")
if not _raw_url or _raw_url.startswith("sqlite"):
    _raw_url = "postgresql://postgres:postgrespassword@localhost:5432/lead_intelligence"

config.set_main_option("sqlalchemy.url", _raw_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
