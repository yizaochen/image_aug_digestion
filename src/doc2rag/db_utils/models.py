import uuid
from typing import List
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, Float, DateTime, Enum
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from ..time_utils import get_current_time


class Base(DeclarativeBase):
    pass


class File(Base):
    """
    Represents a file entity in the database.

    Attributes:
        - id: Primary key identifier for the file.
        - index_name: A unique index or identifier for the file (up to 128 characters).
        - name: The name of the file (filename only, up to 128 characters).
        - file_dir_name: The directory where the file is stored (up to 128 characters).
        - n_pages: The number of pages in the file.
        - size: The size of the file in MB.
        - process_type: text, text_image
        - status: The current status of the file (enum values defined).
        - last_change_at: The timestamp of the last change to the file.
    """

    __tablename__ = "file"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    index_name: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    file_dir_name: Mapped[str] = mapped_column(String(128), nullable=False)
    n_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    process_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[Enum] = mapped_column(
        Enum(
            "wait-for-process",
            "processing",
            "upload-failed",
            "uploaded",
            "wait-for-delete",
            "deleted",
            "delete-failed",
            "failed",
            name="file_status_enum",
        ),
        nullable=False,
        default="wait-for-process",
        index=True,
    )
    last_change_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=get_current_time()
    )

    split_files: Mapped[List["SplitFile"]] = relationship(
        "SplitFile", back_populates="file", cascade="all, delete-orphan", lazy="select"
    )
    backups: Mapped[List["BackupFile"]] = relationship(
        "BackupFile", back_populates="file", cascade="all, delete-orphan", lazy="select"
    )


class BackupFile(Base):
    __tablename__ = "backup_file"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    file_id: Mapped[int] = mapped_column(ForeignKey("file.id"), nullable=False)
    status: Mapped[Enum] = mapped_column(
        Enum(
            "wait-for-backup",
            "backup-in-progress",
            "backed-up",
            "backup-failed",
            "wait-for-delete",
            "deleted",
            "delete-failed",
        ),
        nullable=False,
        default="wait-for-backup",
        index=True,
    )
    backup_path: Mapped[str] = mapped_column(String(512), nullable=True)
    backup_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    backup_finished_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_change_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=get_current_time()
    )

    # Relationship to original file
    file: Mapped["File"] = relationship("File", back_populates="backups")


class SplitFile(Base):
    """
    If the page number of file is larger than 200, the original file (File) will be split into multiple SplitFile.
    If the page number of file is less than or equal to 200, the original file (File) still have one SplitFile, and the split_id of the SplitFile is 0.

    id: the id of the split file, the primary key of the table
    split_id: the id of the split file, the first split file has split_id=0, the second split file has split_id=1, and so on
    start_page_number: the start page number of the split file
    n_pages: the number of pages in the split file
    status: ["wait-for-pymupdf4llm", "wait-for-di", "di-processing", "di-success", "di-failed", "page-split-failed", "page-split-success", "bundle-failed", "bundle-success", "chunk-success", "wait-for-delete", "failed"]
    last_change_at: the last time the file is changed (be added, be processed, be deleted)
    """

    __tablename__ = "split_file"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    split_id: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    start_page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    n_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[Enum] = mapped_column(
        Enum(
            "wait-for-pymupdf4llm",
            "wait-for-di",
            "di-processing",
            "di-success",
            "di-failed",
            "page-split-failed",
            "page-split-success",
            "bundle-failed",
            "bundle-success",
            "chunk-success",
            "chunk-failed",
            "wait-for-delete",
            "failed",
            "file-not-found",
            name="splitfile_status_enum",
        ),
        nullable=False,
        default="wait-for-process",
        index=True,
    )
    last_change_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=get_current_time()
    )

    file_id: Mapped[int] = mapped_column(Integer, ForeignKey("file.id"), index=True)
    file: Mapped["File"] = relationship("File", lazy="select")
    pages: Mapped[List["Page"]] = relationship(
        "Page", back_populates="split_file", cascade="all, delete-orphan", lazy="select"
    )
    chunks: Mapped[List["Chunk"]] = relationship(
        "Chunk",
        back_populates="split_file",
        cascade="all, delete-orphan",
        lazy="select",
    )


class Page(Base):
    """
    If the file is deleted, the corresponding pages will be deleted (remove from the database).
    If the file is updated, the corresponding pages will be deleted (remove from the database) and re-added.

    id: the id of the page, the primary key of the table
    page_number: the page number of the page in the file (original file not the split file)
    status: ["raw-md-extracted", "figs-processed", "bundle-success", "failed"]
    """

    __tablename__ = "page"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_id_in_split_file: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[Enum] = mapped_column(
        Enum(
            "raw-md-extracted",
            "figs-processed",
            "bundle-success",
            "failed",
            name="page_status_enum",
        ),
        nullable=False,
        index=True,
    )
    split_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("split_file.id"), index=True
    )

    split_file: Mapped["SplitFile"] = relationship("SplitFile", lazy="select")
    tables: Mapped[List["Table"]] = relationship(
        "Table", back_populates="page", cascade="all, delete-orphan", lazy="select"
    )
    figures: Mapped[List["Figure"]] = relationship(
        "Figure", back_populates="page", cascade="all, delete-orphan", lazy="select"
    )


class Table(Base):
    """
    If the page is deleted, the corresponding tables will be deleted (remove from the database).

    id: the id of the table, the primary key of the table
    file_id: the id of the file that the table belongs to
    split_file_id: the id of the split file that the table belongs to
    page_id: the id of the page that the table belongs to
    table_id_in_page: the id of the table in the page
    table_name: the name of the table (if any) example: table-{page_number}-{table_id_in_page}.md
    """

    __tablename__ = "table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    table_id_in_page: Mapped[int] = mapped_column(Integer, nullable=False)
    page_id: Mapped[int] = mapped_column(Integer, ForeignKey("page.id"), index=True)

    page: Mapped["Page"] = relationship("Page", back_populates="tables", lazy="select")


class Figure(Base):
    """
    If the page is deleted, the corresponding figures will be deleted (remove from the database).

    id: the id of the figure, the primary key of the figure
    file_id: the id of the file that the figure belongs to
    split_file_id: the id of the split file that the figure belongs to
    page_id: the id of the page that the figure belongs to
    figure_id_in_page: the id of the figure in the page
    figure_name: the name of the figure (if any) example: figure-{page_number}-{figure_id_in_page}.md
    description: the description of the figure by gpt-4o
    """

    __tablename__ = "figure"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_id: Mapped[int] = mapped_column(Integer, ForeignKey("page.id"), index=True)
    figure_id_in_page: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(None), nullable=True)

    page: Mapped["Page"] = relationship("Page", back_populates="figures", lazy="select")


class Chunk(Base):
    """
    status: ["wait-for-upload", "uploaded", "wait-for-delete", "deleted"]
    wait-for-upload: waiting for uploading to Azure AI Search
    uploaded: uploaded to Azure AI Search
    wait-for-delete: waiting for deletion from Azure AI Search
    deleted: deleted from Azure AI Search
    """

    __tablename__ = "chunk"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, index=True, autoincrement=True
    )
    ai_search_id: Mapped[str] = mapped_column(
        String(36), nullable=False, default=lambda: str(uuid.uuid4()), index=True
    )
    content: Mapped[str] = mapped_column(String(None), nullable=True)
    status: Mapped[Enum] = mapped_column(
        Enum(
            "wait-for-upload",
            "uploaded",
            "wait-for-delete",
            "deleted",
            name="chunk_status_enum",
        ),
        nullable=False,
        default="wait-for-upload",
        index=True,
    )
    split_file_id: Mapped[int] = mapped_column(Integer, ForeignKey("split_file.id"))
    split_file: Mapped["SplitFile"] = relationship(
        "SplitFile", back_populates="chunks", lazy="select"
    )


class DIRequest(Base):
    """
    status: ["processing", "success", "failed", "over-max-wait-time"]
    """

    __tablename__ = "di_request"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    finish_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    status: Mapped[Enum] = mapped_column(
        Enum(
            "processing",
            "success",
            "failed",
            "over-max-wait-time",
            name="di_request_status_enum",
        ),
        nullable=False,
        default="processing",  # Change to enum value if using Enum class
    )
    split_file_id: Mapped[int] = mapped_column(
        Integer, nullable=True
    )  # only for record the split file id
