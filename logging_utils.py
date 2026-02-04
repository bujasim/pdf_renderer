import logging
import logging.handlers

# Format string for the logger
FORMAT_STRING: str = "[%(asctime)s] [%(levelname)s] [%(name)s (%(lineno)d)] %(funcName)s: %(message)s"
DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
FORMATTER = logging.Formatter(fmt=FORMAT_STRING, datefmt=DATE_FORMAT)
CONSOLE_HANDLER = logging.StreamHandler()
CONSOLE_HANDLER.setFormatter(FORMATTER)