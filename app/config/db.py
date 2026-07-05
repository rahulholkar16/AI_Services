import os;
from dotenv import load_dotenv;
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker;
load_dotenv();

DB_URI = os.getenv("DATABASE_URL");

if not DB_URI:
    raise RuntimeError( "DATABASE_URL is required. Please configure your .env file.")

if DB_URI.startswith("postgresql://"):
    DB_URI = DB_URI.replace("postgresql://", "postgresql+asyncpg://", 1)
elif DB_URI.startswith("postgres://"):
    DB_URI = DB_URI.replace("postgres://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    DB_URI, echo=False, 
    pool_pre_ping=True, 
    pool_size=10,
    max_overflow=20,
    pool_timeout=30,
    pool_recycle=1800,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session