# db.py

from sqlmodel import SQLModel, create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

# Database connection string
DATABASE_URL = "postgresql://postgres:SSV8JF7TE64TwfxsMzhH@urlshortener-postgre-db.c4puk800oguo.us-east-1.rds.amazonaws.com:5432/url-shortner"

# Create engine and session factory
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency that yields a database session
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Function to create tables
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
