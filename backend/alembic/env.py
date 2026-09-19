import asyncio
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
import os
import sys
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
load_dotenv()

from app.db.session import Base
from app.models.report import Report, ReportSequence
from app.models.audit_log import AuditLog
from app.models.chat_session import ChatSession
from app.models.contact import Contact
from app.models.attachment_model import Attachment
from app.models.settings_models import SystemSetting, Location, Classification, User, FormatVariable, AlutPalsarTemplate, WidgetIntegrationRequest
from app.models.knowledge_models import DictionaryWord, SOPDocument
from app.models.vector_memory import VectorMemory
from app.models.master_models import Tenant

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def get_url():
    cmd_line_url = context.get_x_argument(as_dictionary=True).get("db_url")
    if cmd_line_url:
        if cmd_line_url.startswith("postgresql://") and not cmd_line_url.startswith("postgresql+asyncpg://"):
            cmd_line_url = cmd_line_url.replace("postgresql://", "postgresql+asyncpg://")
        return cmd_line_url
    url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://laporsar_admin:laporsar_admin@localhost:5432/laporsar_master")
    if url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://")
    return url

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
