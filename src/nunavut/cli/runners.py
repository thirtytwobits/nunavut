#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
    Objects that utilize command-line inputs to run a program using Nunavut.
"""

import abc
import argparse
import itertools
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Tuple

from pydsdl import read_namespace as read_dsdl_namespace

from nunavut._generators import AbstractGenerator as Generator
from nunavut._generators import generate_all
from nunavut._namespace import NamespaceFactory
from nunavut._utilities import ResourceType
from nunavut.lang import Language, LanguageContext, LanguageContextBuilder


# ---[ ABSTRACT RUNNER ]---------------------------------------------------------------------------------------------
class Runner(abc.ABC):
    """
    Abstract base class for runners.
    """

    @abc.abstractmethod
    def run(self) -> int:
        """
        Perform actions defined by the arguments this object was created with. This may generate outputs where
        the arguments have requested this action.
        """
        raise NotImplementedError()

    @property
    @abc.abstractmethod
    def args(self) -> argparse.Namespace:
        """
        Access to the arguments this object interprets.
        """
        raise NotImplementedError()

    def new_language_context_builder_from_args(self) -> LanguageContextBuilder:
        """
        Uses interpreted arguments to create a new LanguageContextBuilder object.
        :return: A new LanguageContextBuilder object based on the command line arguments.
        """

        if self.args.configuration is None:
            additional_config_files = []
        elif isinstance(self.args.configuration, Path):
            additional_config_files = [self.args.configuration]
        else:
            additional_config_files = self.args.configuration

        target_language_name = self.args.target_language

        builder: LanguageContextBuilder = LanguageContextBuilder(
            include_experimental_languages=self.args.include_experimental_languages
        )
        builder.set_target_language(target_language_name)
        builder.add_config_files(*additional_config_files)
        builder.set_target_language_extension(self.args.output_extension)
        builder.set_target_language_configuration_override(
            Language.WKCV_NAMESPACE_FILE_STEM, self.args.namespace_output_stem
        )
        builder.set_target_language_configuration_override(Language.WKCV_LANGUAGE_OPTIONS, self.args.language_options)
        return builder

    def list_configuration(self, lctx: LanguageContext) -> None:
        """
        List the configuration of the language context to a yaml file.
        """

        import yaml  # pylint: disable=import-outside-toplevel

        sys.stdout.write("target_language: '")
        sys.stdout.write(lctx.get_target_language().name)
        sys.stdout.write("'\n")

        yaml.dump(lctx.config.sections(), sys.stdout, allow_unicode=True)

    def stdout_lister(
        self,
        things_to_list: Iterable[Any],
        to_string: Callable[[Any], str],
        sep: str = ";",
        end: str = ";",
    ) -> None:
        """
        Write a list of things to stdout.

        :param Iterable[Any] things_to_list: The things to list.
        :param Callable[[Any], str] to_string: A function that converts a thing to a string.
        :param str sep: The separator to use between things.
        :param str end: The character to print at the end.
        """
        first = True
        for thing in things_to_list:
            if first:
                first = False
            else:
                sys.stdout.write(sep)
            sys.stdout.write(to_string(thing))
        if not first:
            sys.stdout.write(end)


class LegacyArgparseRunner(Runner):
    """
    Runner based on Python argparse. Uses pydsdl to find DSDL files using globular path resolution and contains all
    argument handling logic in this class. The modern version of this runner delegates as much logic as possible
    to the Nunavut library to ensure consistency between the CLI and any applications that invoke Nunavut directly.

    ```
    ██████  ███████ ██████  ██████  ███████  ██████  █████  ████████ ███████ ██████
    ██   ██ ██      ██   ██ ██   ██ ██      ██      ██   ██    ██    ██      ██   ██
    ██   ██ █████   ██████  ██████  █████   ██      ███████    ██    █████   ██   ██
    ██   ██ ██      ██      ██   ██ ██      ██      ██   ██    ██    ██      ██   ██
    ██████  ███████ ██      ██   ██ ███████  ██████ ██   ██    ██    ███████ ██████
    ```

    This object should be removed in a future major release of Nunavut to reduce the complexity of the codebase.

    :param argparse.Namespace args: The command line arguments.
    """

    def __init__(self, args: argparse.Namespace):
        self._args = args
        assert self._args.legacy_mode

    @property
    def args(self) -> argparse.Namespace:
        return self._args

    def run(self) -> int:
        lctx = self.new_language_context_builder_from_args().create()

        if self._args.list_configuration:
            self.list_configuration(lctx)

        root_path = self._args.target_files[0]
        code_generator, support_generator = self._create_generators_for_root(lctx, root_path)

        if self._args.list_outputs:
            self._list_outputs_only(code_generator, support_generator)

        elif self._args.list_inputs:
            self._list_inputs_only(code_generator, support_generator)

        else:
            self._generate(code_generator, support_generator)

        return 0

    # --[PRIVATE]--------------------------------------------------------------------------------------------

    def _create_generators_for_root(
        self, lctx: LanguageContext, root_namespace_path: Path
    ) -> Tuple[Optional[Generator], Optional[Generator]]:

        should_create_codegen = (self._args.resource_types & ResourceType.ONLY.value) == 0
        should_create_supportgen = (self._args.resource_types & ResourceType.ANY.value) != 0
        if should_create_codegen and not self._args.list_configuration:
            type_map = read_dsdl_namespace(
                root_namespace_path,
                self._args.root_namespace_directories_or_names,
                allow_unregulated_fixed_port_id=self._args.allow_unregulated_fixed_port_id,
            )
        else:
            type_map = []

        root_namespace = NamespaceFactory(lctx, self._args.outdir, root_namespace_path).add_types(type_map)

        #
        # nunavut : create generators
        #
        generator_args = {
            "resource_types": self._args.resource_types,
            "generate_namespace_types": self._args.generate_namespace_types,
            "trim_blocks": self._args.trim_blocks,
            "lstrip_blocks": self._args.lstrip_blocks,
            "post_processors": self._args.post_processors,
            "embed_auditing_info": self._args.embed_auditing_info,
        }

        from nunavut.jinja import DSDLCodeGenerator, SupportGenerator  # pylint: disable=import-outside-toplevel

        code_generator = (
            None
            if not should_create_codegen
            else DSDLCodeGenerator(root_namespace, templates_dir=self._args.templates_dir, **generator_args)
        )
        support_generator = (
            None
            if not should_create_supportgen
            else SupportGenerator(root_namespace, templates_dir=self._args.support_templates_dir, **generator_args)
        )
        return (code_generator, support_generator)

    def _list_outputs_only(self, code_generator: Optional[Generator], support_generator: Optional[Generator]) -> None:
        if code_generator is not None:
            self.stdout_lister(
                code_generator.generate_all(is_dryrun=True),
                str,
            )

        if support_generator is not None:
            self.stdout_lister(
                support_generator.generate_all(is_dryrun=True),
                str,
            )

    def _list_inputs_only(self, code_generator: Optional[Generator], support_generator: Optional[Generator]) -> None:

        if support_generator is not None:
            self.stdout_lister(
                support_generator.get_templates(),
                lambda p: str(p.resolve()),
            )

        if code_generator is not None:
            self.stdout_lister(
                code_generator.get_templates(),
                lambda p: str(p.resolve()),
            )

            if code_generator.generate_namespace_types:
                self.stdout_lister(
                    [x for x, _ in code_generator.namespace.get_all_types()],
                    lambda p: str(p.source_file_path.as_posix()),
                )
            else:
                self.stdout_lister(
                    [x for x, _ in code_generator.namespace.get_all_datatypes()],
                    lambda p: str(p.source_file_path.as_posix()),
                )

    def _generate(self, code_generator: Optional[Generator], support_generator: Optional[Generator]) -> None:
        if support_generator is not None:
            support_generator.generate_all(
                is_dryrun=self._args.dry_run,
                allow_overwrite=not self._args.no_overwrite,
            )

        if code_generator is not None:
            code_generator.generate_all(
                is_dryrun=self._args.dry_run,
                allow_overwrite=not self._args.no_overwrite,
            )


class StandardArgparseRunner(Runner):
    """
    Runner based on Python argparse. This class delegates most of the generation logic to the :func:`generate_all`
    method providing only additional console output on top of that method's functionality.

    :param argparse.Namespace args: The command line arguments.
    """

    def __init__(self, args: argparse.Namespace):
        self._args = args

    @property
    def args(self) -> argparse.Namespace:
        return self._args

    def run(self) -> int:

        if self._args.list_configuration:
            self.list_configuration(self.new_language_context_builder_from_args().create())

        result = generate_all(**vars(self.args))

        if self._args.list_outputs:
            self.stdout_lister(result.generated_files, lambda p: str(p.resolve()), end="")

        elif self._args.list_inputs:
            input_dsdl = set()
            for target, dependencies in result.target_files.items():
                input_dsdl.add(target)
                input_dsdl.update({d.source_file_path for d in dependencies[1]})
            self.stdout_lister(
                itertools.chain(
                    iter(result.template_files),
                    iter(input_dsdl)
                ),
                lambda p: str(p.resolve()),
                end="",
            )

        return 0


def new_runner(args: argparse.Namespace) -> Runner:
    """
    Create a new ArgparseRunner based on the arguments.
    """
    if not args.omit_deprecated and hasattr(args, "legacy_mode") and args.legacy_mode:
        return LegacyArgparseRunner(args)
    return StandardArgparseRunner(args)


# --[ MAIN ]-----------------------------------------------------------------------------------------------------------
def main(command_line_args: Optional[Any] = None) -> int:
    """
    Main entry point for command-line scripts.
    """

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

    return new_runner(args).run()
