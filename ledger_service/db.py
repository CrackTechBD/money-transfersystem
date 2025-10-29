from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from common.settings import settings

URL = f"mysql+mysqldb://{settings.mysql_user}:{settings.mysql_password}@{settings.mysql_host}:{settings.mysql_port}/{settings.mysql_db}"
engine = create_engine(URL, pool_pre_ping=True, isolation_level="READ COMMITTED")
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
