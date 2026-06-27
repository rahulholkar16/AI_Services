import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker;

DB_URI = os.getenv("DATABASE_URL");

if not DB_URI:
    raise RuntimeError( "DATABASE_URL is required. Please configure your .env file.")

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