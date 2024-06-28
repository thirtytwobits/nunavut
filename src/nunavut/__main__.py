#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
    Command-line entrypoint and supporting functions.
"""

import logging
import sys

from pathlib import Path

from .cli import _make_parser


# --[ MAIN ]-----------------------------------------------------------------------------------------------------------
def main() -> int:
    """
    Main entry point for command-line scripts.
    """

    #
    # Parse the command-line arguments.
    #
    parser = _make_parser()

    try:
        import argcomplete  # pylint: disable=import-outside-toplevel

        argcomplete.autocomplete(parser)
    except ImportError:
        logging.debug("argcomplete not installed, skipping autocomplete")

    args = parser.parse_args()

    #
    # Setup Python logging.
    #
    fmt = "%(message)s"
    level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}.get(args.verbose or 0, logging.DEBUG)
    logging.basicConfig(stream=sys.stderr, level=level, format=fmt)

    logging.info("Running %s using sys.prefix: %s", Path(__file__).name, sys.prefix)

    # pylint: disable=import-outside-toplevel
    from .cli.runners import ArgparseRunner

    # this is an object to allow different runner implementations in the future if needed. For now
    # we only know about the one.
    return ArgparseRunner(args).run()


sys.exit(main())
