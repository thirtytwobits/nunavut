#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
    Objects that utilize command-line inputs to run a program using Nunavut.
"""

import argparse
import itertools
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .._generators import basic_language_context_builder_from_args, generate_all
from .._utilities import DefaultValue
from .._utilities import ResourceType
from ..lang import LanguageContext


class ConfigJSONEncoder(json.JSONEncoder):
    """
    A JSON encoder that can handle Nunavut configuration and pydsdl objects.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, Path):
            return str(o)
        if isinstance(o, DefaultValue):
            return o.value
        return super().default(o)


class StandardArgparseRunner:
    """
    Runner based on Python argparse. This class delegates most of the generation logic to the :func:`generate_all`
    function providing only additional console output on top of that method's functionality.

    :param argparse.Namespace args: The command line arguments.
    """

    def __init__(self, args: argparse.Namespace):
        self._args = args

    @property
    def args(self) -> argparse.Namespace:
        """
        Access to the arguments this object interprets.
        """
        return self._args

    def run(self) -> int:
        """
        Perform actions defined by the arguments this object was created with. This may generate outputs where
        the arguments have requested this action.
        """
        lister_object: Dict[str, Any] = {}
        if self._args.list_configuration:
            lister_object["configuration"] = self.list_configuration(
                basic_language_context_builder_from_args(**vars(self.args)).create()
            )
            if len(sys.argv) > 0:
                lister_object["cmdline"] = sys.argv

        result = generate_all(**vars(self.args))

        if self._args.list_inputs:
            input_dsdl = {str(p) for p in set(result.template_files)}
            for _, target_data in result.generator_targets.items():
                input_dsdl.add(str(target_data.definition.source_file_path.resolve()))
                input_dsdl.update({str(d.source_file_path.resolve()) for d in target_data.input_types})
            lister_object["inputs"] = list(input_dsdl)

        if self._args.list_outputs:
            file_iterators = []
            if self._args.resource_types != ResourceType.NONE.value:
                file_iterators.append(result.support_files)
            if (self._args.resource_types & ResourceType.ONLY.value) == 0:
                file_iterators.append(result.generated_files)
            lister_object["outputs"] = [str(p.resolve()) for p in itertools.chain(*file_iterators)]

        if self._args.list_format == "json":
            json.dump(lister_object, sys.stdout, ensure_ascii=False, cls=ConfigJSONEncoder)
        elif self._args.list_format == "json-pretty":
            json.dump(lister_object, sys.stdout, ensure_ascii=False, indent=2, cls=ConfigJSONEncoder)
        else:
            if self._args.list_format == "scsv":
                sep = ";"
                end = ";"
            elif self._args.list_format == "csv":
                sep = ","
                end = ","
            else:  # pragma: no cover
                raise ValueError(f"Unsupported list format: {self._args.list_format}")
            had_inputs = False
            has_outputs = "outputs" in lister_object and len(lister_object["outputs"]) > 0
            if "inputs" in lister_object and len(lister_object["inputs"]) > 0:
                had_inputs = True
                self.stdout_lister(lister_object["inputs"], sep=sep, end=(end if has_outputs else ""))
            if has_outputs:
                if had_inputs:
                    sys.stdout.write(sep)
                self.stdout_lister(lister_object["outputs"], sep=sep, end="")

        return 0

    def list_configuration(self, lctx: LanguageContext) -> Dict[str, Any]:
        """
        List the configuration of the language context to an object.
        """

        config: Dict[str, Any] = {}
        config["target_language"] = lctx.get_target_language().name
        config["sections"] = lctx.config.sections()

        return config

    def stdout_lister(
        self,
        things_to_list: Iterable[str],
        sep: str,
        end: str,
    ) -> None:
        """
        Write a list of things to stdout.

        :param Iterable[Any] things_to_list: The things to list.
        :param str sep: The separator to use between things.
        :param str end: The character to print at the end.
        """
        first = True
        for thing in things_to_list:
            if first:
                first = False
            else:
                sys.stdout.write(sep)
            sys.stdout.write(thing)
        if not first:
            sys.stdout.write(end)


# --[ MAIN ]-----------------------------------------------------------------------------------------------------------
def main(command_line_args: Optional[Any] = None) -> int:
    """
    Main entry point for command-line scripts.
    """
    from multiprocessing import freeze_support  # pylint: disable=import-outside-toplevel

    freeze_support()

    from . import _make_parser  # pylint: disable=import-outside-toplevel
    from .parsers import NunavutArgumentParser  # pylint: disable=import-outside-toplevel

    #
    # Parse the command-line arguments.
    #
    parser = _make_parser(NunavutArgumentParser)

    try:
        import argcomplete  # pylint: disable=import-outside-toplevel

        argcomplete.autocomplete(parser)
    except ImportError:
        logging.debug("argcomplete not installed, skipping autocomplete")

    args = parser.parse_args(args=command_line_args)

    #
    # Setup Python logging.
    #
    fmt = "%(message)s"
    level = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}.get(args.verbose or 0, logging.DEBUG)
    logging.basicConfig(stream=sys.stderr, level=level, format=fmt)

    logging.info("Running %s using sys.prefix: %s", Path(__file__).name, sys.prefix)

    return StandardArgparseRunner(args).run()
