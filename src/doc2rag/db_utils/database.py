from abc import ABC, abstractmethod
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.engine import URL

from doc2rag.config_utils import PathConfig, MSSQLConfig
from .models import Base


class BaseSQLAgent(ABC):
    """
    Abstract Base Class for SQL Agents.
    Defines the interface that all concrete SQL Agents must implement.
    """

    @abstractmethod
    def __init__(self) -> None:
        pass

    @abstractmethod
    def SessionLocal(self):
        """
        Returns the sessionmaker instance for the database.
        This method must be implemented by all subclasses.
        """
        pass


class SQLiteAgent(BaseSQLAgent):
    """
    Concrete implementation of BaseSQLAgent for SQLite.
    """

    def __init__(self) -> None:
        self._sql_db_path = PathConfig().sql_db_path
        self._engine = create_engine(
            f"sqlite:///{self._sql_db_path}",
            pool_size=10,  # Max number of connections
            max_overflow=5,  # Extra connections allowed temporarily
            echo=False,  # Log SQL queries to console
        )
        self._SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self._engine
        )
        Base.metadata.create_all(bind=self._engine)

    @property
    def SessionLocal(self):
        """
        Returns the sessionmaker instance.
        """
        return self._SessionLocal


class MSSQLAgent(BaseSQLAgent):
    """
    Concrete implementation of BaseSQLAgent for SQL Server.
    """

    def __init__(self) -> None:
        self._connection_str = URL.create(
            "mssql+pyodbc",
            query={"odbc_connect": MSSQLConfig().connection_str},
        )
        self._engine = create_engine(
            self._connection_str,
            pool_size=10,  # Max number of connections
            max_overflow=5,  # Extra connections allowed temporarily
            echo=False,
        )
        self._SessionLocal = sessionmaker(bind=self._engine)
        Base.metadata.create_all(bind=self._engine)

    @property
    def SessionLocal(self):
        """
        Returns the sessionmaker instance.
        """
        return self._SessionLocal
