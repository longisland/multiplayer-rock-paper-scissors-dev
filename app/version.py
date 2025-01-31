import os
from datetime import datetime

VERSION = '1.0.0'
BUILD_TIME = None  # Will be set during container build

def get_version_info():
    return {
        'version': VERSION,
        'build_time': BUILD_TIME,
        'git_commit': os.getenv('GIT_COMMIT', 'unknown')
    }