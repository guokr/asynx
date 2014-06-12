from os import path
from .taskqueue import TaskQueueClient

__all__ = ['TaskQueueClient']

with open(path.join(path.dirname(__file__), 'version.txt')) as fp:
    __version__ = fp.read().strip()
