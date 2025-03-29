"""
 Usage example
  logging_agent = LoggingAgent(agent_name="MyAgent")
  logger = logging_agent.logger
  logger.info("This is a log message.")
"""

import logging
from .config_utils import RootConfig, PathConfig


class LoggingAgent:
    """
    LoggingAgent is responsible for setting up and managing loggers for different agents.

    Attributes:
    - agent_name (str): The name of the agent (used in log file naming and logger identification).
    - log_dir (Path): The directory where the log files should be saved.
    - log_level (int): The logging level (default is logging.INFO).
    """

    d_log_level = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    def __init__(self, agent_name: str):
        """
        Initializes the LoggingAgent with the given agent name.

        Parameters:
        - agent_name (str): Name of the agent for which the logger is being created.
        """
        self.agent_name = agent_name
        self.log_level = self._get_log_level()
        self.log_dir = PathConfig().log_dir_path

        # Ensure the log directory exists
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Logger is initially None, will be lazily initialized
        self._logger = self._initialize_logger()
        if not self._logger.hasHandlers():
            self._add_file_handler()
            self._add_console_handler()

    @property
    def logger(self) -> logging.Logger:
        """
        Getter for the logger attribute.
        Returns:
        - logging.Logger: A configured logger for the agent.
        """
        return self._logger

    def _get_log_level(self) -> str:
        """
        Helper method to retrieve the log level from the configuration.
        Returns:
        - str: The log level as a string.
        """
        return self.d_log_level[RootConfig().config["log_level"]]

    def _initialize_logger(self) -> logging.Logger:
        """
        Initializes a logger with the agent name and log level.

        Returns:
        - logging.Logger: A logger with the agent name and log level.
        """
        logger = logging.getLogger(self.agent_name)
        logger.setLevel(self.log_level)
        return logger

    def _add_file_handler(self):
        """
        Adds a file handler to the logger to write logs to a file.

        Parameters:
        - log_file (Path): The path to the log file.
        """
        log_file = self.log_dir / f"{self.agent_name}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(self.log_level)
        file_handler.setFormatter(self.formatter)
        self._logger.addHandler(file_handler)

    def _add_console_handler(self):
        """
        Adds a console handler to the logger to output logs to the console.
        """
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)
        console_handler.setFormatter(self.formatter)
        self._logger.addHandler(console_handler)
