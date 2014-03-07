import argparse
from ConfigParser import ConfigParser
from os.path import (
    abspath,
    expanduser,
)
from textwrap import dedent
from leankit.leankit import Auth


def load_credentials(ini_path):
    """Given an ini path, load their credentials."""
    config_path = abspath(expanduser(ini_path))

    ini = ConfigParser()
    ini.readfp(open(config_path))
    creds = Auth(
        ini.get('auth', 'account'),
        ini.get('auth', 'username'),
        ini.get('auth', 'password')
    )

    return creds


def base_args(desc):

    parser = argparse.ArgumentParser(description=desc)

    parser.add_argument(
        '-i', '--ini', dest='ini',
        action='store',
        default='~/leankit.ini',
        help="Path to config file with credentials.")
    parser.add_argument(
        '--board_id', dest='board_id',
        action='store',
        default=None,
        help="The id of the board to query")
    parser.add_argument(
        '--board_title', dest='board_title',
        action='store',
        default=None,
        help="The title of the board to query")
    parser.add_argument(
        '--lane_id', dest='lane_id',
        action='store',
        default=None,
        help="The id of the lane to query")
    parser.add_argument(
        '--lane_path', dest='lane_path',
        action='store',
        default=None,
        help=dedent("""
            The path to the lane to query. Separate path
            segments with ::"""))

    return parser
