#!/usr/bin/env python
    
import argparse
from .common import get_server_url
from loomengine.utils.connection import Connection


def version():
    with open(os.path.join(os.path.dirname(__file__), '..', 'VERSION')) as versionfile:
        return versionfile.read().strip()

class Version:
    """Shows the Loom version."""

    def __init__(self, args=None):

        # Args may be given as an input argument for testing purposes.
        # Otherwise get them from the parser.
        if args is None:
            args = self._get_args()
        self.args = args
        self.connection = self._get_connection()

    def _get_connection(self):
        master_url = get_server_url()
        return  Connection(master_url)

    def _get_args(self):
        parser = self.get_parser()
        return parser.parse_args()

    @classmethod
    def get_parser(cls, parser=None):

        # If called from main, use the subparser provided.
        # Otherwise create a top-level parser here.
        if parser is None:
            parser = argparse.ArgumentParser(__file__)
        return parser

    def run(self):
        server_version = self.get_server_version()
        if not server_version:
            server_version = 'unavailable'
        print "client version: %s" % version()
        print "server version: %s" % server_version

    def get_server_version(self):
        return self.connection.get_version()

if __name__=='__main__':
    response = Version().run()
