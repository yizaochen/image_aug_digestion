from pathlib import Path
from shutil import copyfile
from logging import Logger

import html
from bs4 import BeautifulSoup
from jinja2 import Template
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import func
from sqlalchemy.exc import SQLAlchemyError
from .db_utils.models import File, SplitFile, Page

from .db_utils.database import BaseSQLAgent
from .logger_utils import LoggingAgent
from .config_utils import PathConfig
from .page_split import get_file_path


table_frame_template = Template(
    """### Table
```table content
{{ table_content }}
```
#### Table Source Info
- Source File: {{ source_file }}
- Page Number: {{ page_number }}
- Table ID in Page: {{ table_id_in_page }}
"""
)

figure_frame_template = Template(
    """### Figure
- Caption: {{ figcaption_text }}
```description
{{ description }}
```
#### Fig Source Info
- Source File: {{ source_file }}
- Page Number: {{ page_number }}
- Figure ID in Page: {{ figure_id_in_page }}
- Image Name: {{ figure_path }}
"""
)


class TextTableImageBundler:
    def __init__(self, sql_agent: BaseSQLAgent):
        self.logger = LoggingAgent("Bundler").logger
        self.SessionLocal = sql_agent.SessionLocal
        self.path_config = PathConfig()

    def bundle(self):
        """
        Process pages with the status `figs-processed` and bundle tables and figures sequentially.
        """
        with self.SessionLocal() as session:
            pages, file_dir_name_lst, file_name_lst = self._fetch_pages_to_process(
                session
            )

            if not pages:
                self.logger.info("No unprocessed pages found.")
                return

            n_pages = len(pages)
            self.logger.info(f"Found {n_pages} unprocessed pages.")

            # Sequential processing with progress logging
            for idx, (page, file_dir_name, file_name) in enumerate(
                zip(pages, file_dir_name_lst, file_name_lst), start=1
            ):
                try:
                    self._process_page(page, file_dir_name, file_name, session)
                    if idx % 10 == 0 or idx == n_pages:
                        self.logger.info(
                            f"Progress {idx}/{n_pages} (Page Number: {page.page_number})."
                        )
                except Exception as e:
                    self.logger.error(
                        f"Failed to process page {idx}/{n_pages} (Page Number: {page.page_number}) in file {file_name}: {e}"
                    )

    def _fetch_pages_to_process(
        self, session: Session
    ) -> tuple[list[Page], list[str], list[str]]:
        """
        Fetch pages with the status `figs-processed` and related file_dir_name.
        """
        result = (
            session.query(Page, File.file_dir_name, File.name)
            .join(SplitFile, Page.split_file_id == SplitFile.id)
            .join(File, SplitFile.file_id == File.id)
            .filter(Page.status == "figs-processed")
            .options(
                joinedload(Page.tables),
                joinedload(Page.figures),
            )
            .order_by(SplitFile.id, Page.page_number)
            .all()
        )
        return (
            [item[0] for item in result],
            [item[1] for item in result],
            [item[2] for item in result],
        )

    def _process_page(
        self, page: Page, file_dir_name: str, file_name: str, session: Session
    ) -> None:
        try:
            raw_md_path = self._get_raw_md_path(file_dir_name, page.page_number)
            bundle_md_path = self._get_bundle_md_path(file_dir_name, page.page_number)

            if not page.tables and not page.figures:
                self._copy_file(raw_md_path, bundle_md_path)
                self._update_page_status(page, session, "bundle-success")
                return

            raw_md_content = self._get_raw_md_content(raw_md_path)
            soup = BeautifulSoup(raw_md_content, "html.parser")

            # Process tables and figures
            if page.tables:
                self._process_tables(page, soup, file_dir_name, file_name)
            if page.figures:
                self._process_figures(page, soup, file_dir_name, file_name)

            # Write final bundled content
            self._write_bundle_content(bundle_md_path, soup)
            self._update_page_status(page, session, "bundle-success")

        except Exception as e:
            self.logger.error(f"Error processing page {page.id}: {e}")

    def _copy_file(self, source: Path, destination: Path):
        """Copy file from source to destination."""
        copyfile(source, destination)

    def _update_page_status(self, page: Page, session: Session, status: str) -> None:
        """Update page status and commit."""
        page.status = status
        session.commit()

    def _get_raw_md_content(self, raw_md_path: Path) -> str:
        with open(raw_md_path, "r", encoding="utf-8") as f:
            return f.read()

    def _get_raw_md_path(self, file_dir_name: str, page_number: int) -> Path:
        """Construct the raw markdown file path for a given page number."""
        raw_md_dir_path = self.path_config.get_raw_md_dir_path(file_dir_name)
        raw_md_path = get_file_path(raw_md_dir_path, page_number, extension=".md")
        if not raw_md_path.exists():
            raise FileNotFoundError(f"Raw markdown file not found at {raw_md_path}")
        return raw_md_path

    def _get_bundle_md_path(self, file_dir_name: str, page_number: int) -> Path:
        """Construct the bundle markdown file path for a given page number."""
        bundle_md_dir_path = self.path_config.get_bundle_md_dir_path(file_dir_name)
        return get_file_path(bundle_md_dir_path, page_number, extension=".md")

    def _write_bundle_content(self, bundle_md_path: str, soup: BeautifulSoup) -> None:
        with open(bundle_md_path, "w", encoding="utf-8") as f:
            bundle_md_content = html.unescape(str(soup))
            f.write(bundle_md_content)

    def _process_tables(
        self, page: Page, soup: BeautifulSoup, file_dir_name: str, file_name: str
    ) -> None:
        table_dir_path = self.path_config.get_table_dir_path(file_dir_name)
        tables_bs4 = soup.find_all("table")

        for table, table_bs4 in zip(page.tables, tables_bs4):
            table_path = self._get_table_path(
                table_dir_path, page.page_number, table.table_id_in_page
            )
            table_content = table_path.read_text(encoding="utf-8")
            table_bs4.replace_with(
                table_frame_template.render(
                    table_content=table_content,
                    source_file=file_name,
                    page_number=page.page_number,
                    table_id_in_page=table.table_id_in_page,
                )
            )

    def _process_figures(
        self, page: Page, soup: BeautifulSoup, file_dir_name: str, file_name: str
    ) -> None:
        figure_dir_path = self.path_config.get_figure_dir_path(file_dir_name)
        figures_bs4 = soup.find_all("figure")

        for figure, figure_bs4 in zip(page.figures, figures_bs4):
            description = figure.description or "No description"
            figure_path = get_file_path(
                figure_dir_path,
                page.page_number,
                figure.figure_id_in_page,
                extension=".png",
            )
            figcaption = self._get_figure_caption(figure_bs4)
            figure_bs4.replace_with(
                figure_frame_template.render(
                    figcaption_text=figcaption,
                    description=description,
                    source_file=file_name,
                    page_number=page.page_number,
                    figure_id_in_page=figure.figure_id_in_page,
                    figure_path=figure_path.name,
                )
            )

    def _get_table_path(
        self, table_dir_path: Path, page_number: int, table_id_in_page: int
    ) -> Path:
        """
        Construct the path for saving a table as a markdown file.
        """
        return get_file_path(
            table_dir_path, page_number, table_id_in_page, extension=".md"
        )

    def _get_figure_caption(self, figure_bs4) -> str:
        figcaption = figure_bs4.find("figcaption")
        return figcaption.text if figcaption else "No caption"


class BundleStatusUpdateAgent:
    def __init__(self, sql_agent: BaseSQLAgent):
        self.logger: Logger = LoggingAgent("Bundler").logger
        self.SessionLocal = sql_agent.SessionLocal

    def update_split_files_status(self) -> None:
        """
        Fetch split files with the required status and update their statuses
        based on the validation of associated pages.
        """
        with self.SessionLocal() as session:
            try:
                split_files = self._fetch_split_files_to_check(session)
                if not split_files:
                    self.logger.info("No split files found.")
                    return

                n_files = len(split_files)
                self.logger.info(f"Found {n_files} split files to process.")
                for progress, split_file in enumerate(split_files, start=1):
                    self._update_split_file_status(split_file, session)
                    self.logger.info(
                        f"Progress: {progress}/{n_files} split files processed."
                    )

                session.commit()  # Commit all changes in a single transaction

            except SQLAlchemyError as e:
                self.logger.error(f"Database error occurred: {e}")
                session.rollback()
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")

    def _fetch_split_files_to_check(self, session: Session) -> list[SplitFile]:
        """
        Fetch split files with the status `page-split-success` or `bundle-failed` and eagerly load their pages.
        """
        return (
            session.query(SplitFile)
            .options(joinedload(SplitFile.pages))
            .filter(SplitFile.status.in_(["page-split-success", "bundle-failed"]))
            .all()
        )

    def _update_split_file_status(
        self, split_file: SplitFile, session: Session
    ) -> None:
        """
        Update the status of a split file based on the validation of its pages.
        """
        n_validated_pages = (
            session.query(func.count(Page.id))
            .filter(
                Page.split_file_id == split_file.id,
                Page.status == "bundle-success",
            )
            .scalar()
        )

        # Update the split file status based on the number of validated pages
        split_file.status = (
            "bundle-success"
            if n_validated_pages == split_file.n_pages
            else "bundle-failed"
        )
        self.logger.debug(
            f"Split file {split_file.id} status set to {split_file.status} "
            f"({n_validated_pages}/{split_file.n_pages} pages validated)."
        )
