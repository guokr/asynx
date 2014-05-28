from os import path

with open(path.join(path.dirname(__file__), 'version.txt')) as fp:
    __version__ = fp.read().strip()
