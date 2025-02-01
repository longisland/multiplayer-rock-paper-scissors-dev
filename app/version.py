import os
import logging
import subprocess
from datetime import datetime

logger = logging.getLogger(__name__)

def get_git_version():
    try:
        # Get the latest tag
        tag = subprocess.check_output(['git', 'describe', '--tags', '--abbrev=0'], 
                                   stderr=subprocess.DEVNULL).decode().strip()
        # Get number of commits since tag
        commits_since = subprocess.check_output(
            ['git', 'rev-list', f'{tag}..HEAD', '--count']).decode().strip()
        # Get the current commit hash
        commit_hash = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
        
        if commits_since == "0":
            return tag
        return f"{tag}.post{commits_since}+{commit_hash}"
    except:
        return '0.0.0'

VERSION = get_git_version()
BUILD_TIME = datetime.utcnow().isoformat()

def get_version_info():
    info = {
        'version': VERSION,
        'build_time': BUILD_TIME,
        'git_commit': os.getenv('GIT_COMMIT', 'unknown')
    }
    logger.info(f"Version info: {info}")
    return info