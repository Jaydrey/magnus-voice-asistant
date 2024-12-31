import logging

from .settings import (
    LOG_FILENAME,
    LOGGER_NAME
)

logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s', 
    filename=LOG_FILENAME.as_posix(),
    encoding='utf-8',
    filemode='a+',
)

logger = logging.getLogger(LOGGER_NAME)

