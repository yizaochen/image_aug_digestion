import os
from pathlib import Path
import yaml


class TiktokenCacheDirNotExistsError(Exception):
    pass


class ConfigYMLPathNotSetError(Exception):
    pass


class RootConfig:
    def __init__(self, config_path: str = None) -> None:
        if os.getenv("CONFIG_PATH") is None:
            raise ConfigYMLPathNotSetError(
                "CONFIG_PATH environment variable is not set. Please set the path to the configuration file."
            )
        config_path = os.getenv("CONFIG_PATH")

        if not config_path:
            raise ValueError(
                "CONFIG_PATH environment variable is not set or no config path was provided."
            )

        try:
            # Load the YAML configuration file
            with open(config_path, "r") as config_file:
                self._config = yaml.safe_load(config_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found at {config_path}")
        except PermissionError:
            raise PermissionError(
                f"Permission denied while trying to read the config file at {config_path}"
            )
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML configuration: {e}")

    @property
    def config(self):
        """Provides access to the loaded configuration."""
        return self._config


class SQLTypeConfig:
    def __init__(self):
        self.config = RootConfig().config

    @property
    def sql_type(self) -> str:
        return self.config["sql_type"]


class PathConfig:
    def __init__(self):
        """
        Initializes the PathConfigAgent with the provided configuration.
        Args:
            config (dict): The configuration loaded from the YAML file.
        """
        self.config = RootConfig().config
        self._base_dir = Path(self._get_path_from_config("paths", "base"))
        self._indices_dir = Path(self._get_path_from_config("indices_dir", "base"))

    def _get_path_from_config(self, *keys: str) -> str:
        """
        Helper method to retrieve a nested path from the configuration using provided keys.
        Args:
            keys: The hierarchical keys to reach the desired path.
        Returns:
            str: The retrieved path as a string.
        """
        path = self.config
        for key in keys:
            path = path.get(key)
            if path is None:
                raise KeyError(f"Key {'/'.join(keys)} not found in configuration.")
        return path

    @property
    def base_dir(self) -> Path:
        """Returns the base directory path."""
        return self._base_dir

    @property
    def indices_dir_path(self) -> Path:
        return self._indices_dir

    @property
    def log_dir_path(self) -> Path:
        """Returns the log directory path."""
        return self.base_dir / self._get_path_from_config("paths", "log_dir")

    @property
    def meta_data_dir_path(self) -> Path:
        """Returns the metadata directory path."""
        return self.base_dir / self._get_path_from_config(
            "paths", "meta_data_dir", "base"
        )

    @property
    def sql_db_path(self) -> Path:
        """Returns the SQL database directory path."""
        return self.base_dir / self._get_path_from_config("paths", "sql_db")

    @property
    def index_dirs(self) -> list[Path]:
        return [self.get_index_dir(index) for index in self.index_list]

    @property
    def index_list(self) -> list[str]:
        return self.config["index_list"]

    def get_index_dir(self, index_name: str) -> Path:
        return self.indices_dir_path / index_name

    def get_source_dir(self, index_name: str, process_type: str) -> Path:
        """
        process_type: text, text_image
        """
        return self.get_index_dir(index_name) / self._get_path_from_config(
            "indices_dir", "index_dir", f"{process_type}_dir", "base"
        )

    def get_wait_dir(self, index_name: str, process_type: str) -> Path:
        """
        process_type: text, text_image
        """
        return self.get_source_dir(
            index_name, process_type
        ) / self._get_path_from_config(
            "indices_dir", "index_dir", f"{process_type}_dir", "wait_dir"
        )

    def get_done_dir(self, index_name: str, process_type: str) -> Path:
        """
        process_type: text, text_image
        """
        return self.get_source_dir(
            index_name, process_type
        ) / self._get_path_from_config(
            "indices_dir", "index_dir", f"{process_type}_dir", "done_dir"
        )

    def get_fail_dir(self, index_name: str, process_type: str) -> Path:
        """
        process_type: text, text_image
        """
        return self.get_source_dir(
            index_name, process_type
        ) / self._get_path_from_config(
            "indices_dir", "index_dir", f"{process_type}_dir", "fail_dir"
        )

    def get_split_dir_path(self, file_dir_name: str) -> Path:
        """Returns split directory path."""
        return (
            self.base_dir
            / self.meta_data_dir_path
            / file_dir_name
            / self._get_path_from_config("paths", "meta_data_dir", "split_dir")
        )

    def get_pkl_dir_path(self, file_dir_name: str) -> Path:
        """Returns pkl directory path."""
        return (
            self.base_dir
            / self.meta_data_dir_path
            / file_dir_name
            / self._get_path_from_config("paths", "meta_data_dir", "pkl_dir")
        )

    def get_table_dir_path(self, file_dir_name: str) -> Path:
        """Returns table directory path."""
        return (
            self.base_dir
            / self.meta_data_dir_path
            / file_dir_name
            / self._get_path_from_config("paths", "meta_data_dir", "table_dir")
        )

    def get_figure_dir_path(self, file_dir_name: str) -> Path:
        """Returns figure directory path."""
        return (
            self.base_dir
            / self.meta_data_dir_path
            / file_dir_name
            / self._get_path_from_config("paths", "meta_data_dir", "figure_dir")
        )

    def get_raw_md_dir_path(self, file_dir_name: str) -> Path:
        """Returns raw_md directory path."""
        return (
            self.base_dir
            / self.meta_data_dir_path
            / file_dir_name
            / self._get_path_from_config("paths", "meta_data_dir", "raw_md_dir")
        )

    def get_bundle_md_dir_path(self, file_dir_name: str) -> Path:
        """Returns refined_md directory path."""
        return (
            self.base_dir
            / self.meta_data_dir_path
            / file_dir_name
            / self._get_path_from_config("paths", "meta_data_dir", "bundle_md_dir")
        )

    def get_general_path(self, *path_keys: str) -> Path:
        """
        General method to retrieve a path based on any number of path keys.
        Args:
            path_keys: The hierarchical keys to reach the desired path.
        Returns:
            Path: The constructed Path object.
        """
        return self.base_dir / self._get_path_from_config(*path_keys)

    def get_file_in_dir(self, dir_key: str, filename: str) -> Path:
        """
        Returns the full path to a file located in the specified directory.
        Args:
            dir_key (str): The directory key in the configuration.
            filename (str): The file name.
        Returns:
            Path: Full path to the file.
        """
        return self.get_general_path("paths", "data_dir", dir_key) / filename


class BackupConfig:
    def __init__(self):
        self._config = RootConfig().config
        self._path_config = PathConfig()

        self._source_root = self._path_config.meta_data_dir_path
        self._source_doc_dir = self._path_config.indices_dir_path
        self._backup_root = Path(self._config["backup_root"])

        self._retention_data = self._get_retention_data()

    @property
    def source_root(self) -> Path:
        return self._source_root

    @property
    def source_doc_dir(self) -> Path:
        return self._source_doc_dir

    @property
    def backup_root(self) -> Path:
        return self._backup_root

    @property
    def retention_days(self) -> int:
        return self._retention_data["days"]

    @property
    def retention_hours(self) -> int:
        return self._retention_data["hours"]

    @property
    def retention_minutes(self) -> int:
        return self._retention_data["minutes"]

    @property
    def retention_seconds(self) -> int:
        return self._retention_data["seconds"]

    def _get_retention_data(self) -> dict:
        retention = self._config["backup_retention"]
        return {
            "days": retention["days"],
            "hours": retention["hours"],
            "minutes": retention["minutes"],
            "seconds": retention["seconds"],
        }


class FileSplitterConfig:
    def __init__(self):
        self.config = RootConfig().config

    @property
    def n_pages_per_split(self) -> int:
        """
        Number of pages per split.
        """
        return self.config["file_splitter"]["n_pages_per_split"]


class DocumentIntelligenceConfig:
    def __init__(self) -> None:
        self.config = RootConfig().config

    @property
    def endpoint(self) -> str:
        return self.config["document_intelligence"]["endpoint"]

    @property
    def api_key(self) -> str:
        return self.config["document_intelligence"]["api_key"]

    @property
    def api_version(self) -> str:
        return self.config["document_intelligence"]["api_version"]

    @property
    def submit_interval(self) -> int:
        """Interval (in seconds) between job submissions."""
        return self.config["document_intelligence"]["submit_interval"]

    @property
    def check_period(self) -> int:
        """Time (in seconds) to wait between job status checks."""
        return self.config["document_intelligence"]["check_period"]

    @property
    def max_wait_time(self) -> int:
        """Maximum time (in seconds) to wait for job completion."""
        return self.config["document_intelligence"]["max_wait_time"]

    @property
    def batch_size(self) -> int:
        """The maximum number of files to process in each batch."""
        return self.config["document_intelligence"]["batch_size"]

    @property
    def main_loop_wait(self) -> int:
        """Time (in seconds) to wait between main loop iterations."""
        return self.config["document_intelligence"]["main_loop_wait"]


class AzureOpenAIConfig:

    def __init__(self) -> None:
        self.config = RootConfig().config

    @property
    def endpoint(self) -> str:
        return self.config["azure_openai"]["endpoint"]

    @property
    def api_key(self) -> str:
        return self.config["azure_openai"]["api_key"]

    @property
    def deployment(self) -> str:
        return self.config["azure_openai"]["deployment"]

    @property
    def api_version(self) -> str:
        return self.config["azure_openai"]["api_version"]


class ImageAOAIConfig:

    def __init__(self) -> None:
        self.config = RootConfig().config

    @property
    def api_key(self) -> str:
        return self.config["image_aoai"]["api_key"]

    @property
    def endpoint(self) -> str:
        return self.config["image_aoai"]["endpoint"]

    @property
    def deployment(self) -> str:
        return self.config["image_aoai"]["deployment"]

    @property
    def api_version(self) -> str:
        return self.config["image_aoai"]["api_version"]


class EmbeddingConfig:
    d_embedding_dimension = {
        "text-embedding-ada-002": 1536,
        "text-embedding-3-small": 1536,
        "text-embedding-3-large": 3072,
    }

    def __init__(self) -> None:
        self.config = RootConfig().config

    @property
    def model(self) -> str:
        return self.config["embedding"]["model"]

    @property
    def deployment(self) -> str:
        return self.config["embedding"]["model"]

    @property
    def api_version(self) -> str:
        return self.config["embedding"]["api_version"]

    @property
    def api_key(self) -> str:
        return self.config["embedding"]["api_key"]

    @property
    def endpoint(self) -> str:
        return self.config["embedding"]["endpoint"]

    @property
    def dimension(self) -> int:
        return self.d_embedding_dimension[self.model]


class AzureAISearchConfig:

    def __init__(self) -> None:
        self.config = RootConfig().config

    @property
    def index_name(self) -> str:
        return self.config["azure_ai_search"]["index_name"]

    @property
    def endpoint(self) -> str:
        return self.config["azure_ai_search"]["endpoint"]

    @property
    def api_version(self) -> str:
        return self.config["azure_ai_search"]["api_version"]

    @property
    def api_key(self) -> str:
        return self.config["azure_ai_search"]["api_key"]


class ChunkingConfig:
    def __init__(self) -> None:
        self.config = RootConfig().config

    @property
    def model_name(self) -> str:
        return self.config["chunking"]["model_name"]

    @property
    def chunk_size(self) -> int:
        return self.config["chunking"]["chunk_size"]

    @property
    def chunk_overlap(self) -> int:
        return self.config["chunking"]["chunk_overlap"]


class TiktokenConfig:
    def __init__(self) -> None:
        self.config = RootConfig().config

    def set_tiktoken_cache_dir_in_env(self, encoding_name: str) -> None:
        """
        encoding_name: cl100k_base, o200k_base
        """
        tiktoken_cache_dir = Path(self.config["tiktoken_cache_dir"][encoding_name])
        tiktoken_cache_dir.resolve()
        if not tiktoken_cache_dir.exists():
            raise TiktokenCacheDirNotExistsError(
                f"TIKTOKEN_CACHE_DIR path {tiktoken_cache_dir} does not exist. Please check..."
            )
        os.environ["TIKTOKEN_CACHE_DIR"] = str(tiktoken_cache_dir)
        print(f"Set TIKTOKEN_CACHE_DIR to {tiktoken_cache_dir}")


class MSSQLConfig:
    def __init__(self) -> None:
        self.config = RootConfig().config

    @property
    def connection_str(self) -> str:
        driver = self.config["mssql"]["driver"]
        server = self.config["mssql"]["server"]
        database = self.config["mssql"]["database"]
        username = self.config["mssql"]["username"]
        password = self.config["mssql"]["password"]
        return f"DRIVER={driver};SERVER={server};DATABASE={database};UID={username};PWD={password};TrustServerCertificate=yes"
