import logging
import os

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "manga_downloader.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",
)


def get_logger(name):
    return logging.getLogger(name)
