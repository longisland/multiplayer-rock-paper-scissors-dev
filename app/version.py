import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

VERSION = '1.0.0'
BUILD_TIME = None  # Will be set during container build

def get_version_info():
    info = {
        'version': VERSION,
        'build_time': BUILD_TIME,
        'git_commit': os.getenv('GIT_COMMIT', 'unknown')
    }
    logger.info(f"Version info: {info}")
    return info