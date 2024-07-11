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

from .cli import make_nunavut_parser


# --[ MAIN ]-----------------------------------------------------------------------------------------------------------
def main() -> int:
    """
    Main entry point for command-line scripts.
    """

    #
    # Parse the command-line arguments.
    #
    parser = make_nunavut_parser()

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
    from .cli.runners import new_runner

    return new_runner(args).run()


sys.exit(main())
