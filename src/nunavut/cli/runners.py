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
import logging
import os
import sys
import typing

from pathlib import Path

from pydsdl import read_namespace as read_dsdl_namespace
from pydsdl import read_files as read_dsdl_files
from pydsdl import CompositeType

from nunavut._generators import create_default_generators
from nunavut._generators import AbstractGenerator as Generator
from nunavut._namespace import build_namespace_tree
from nunavut._namespace import Namespace
from nunavut._postprocessors import (
    ExternalProgramEditInPlace,
    FilePostProcessor,
    LimitEmptyLines,
    PostProcessor,
    SetFileMode,
    TrimTrailingWhitespace,
)
from nunavut._utilities import DefaultValue, YesNoDefault
from nunavut.lang import Language, LanguageContext, LanguageContextBuilder


# --[ INTERPRETER ]----------------------------------------------------------------------------------------------------


class ArgumentInterpreter:
    """
    Given the parsed args this class provides further interpretation of the results.
    Extend _NunavutArgumentParser (in the CLI package) for things that can be determined using trivial rules. Use this
    class to provide complex interpretation and a stable API that can present options which are determined by the
    values of several other options or which require collaboration with other objects.

    :param argparse.Namespace   args: The command line arguments to interpret.
    """

    def __init__(self, args: argparse.Namespace):
        self._args = args
        self._post_processors: typing.Optional[list[PostProcessor]] = None
        self._language_options: typing.Optional[dict[str, typing.Any]] = None

    @property
    def args(self) -> argparse.Namespace:
        """
        Access to the arguments this object interprets.
        """
        return self._args

    @property
    def should_generate_support(self) -> bool:
        """
        True if support code should be generated. False if it should not be generated.
        """
        if self._args.generate_support == "as-needed":
            return self._args.omit_serialization_support is None or not self._args.omit_serialization_support
        return bool(self._args.generate_support in ("always", "only"))

    @property
    def post_processors(self) -> list[PostProcessor]:
        """
        A, possibly empty, list of post processors to run based on provided arguments.
        """

        if self._post_processors is None:

            def _build_ext_program_postprocessor_args(program: str) -> list[str]:
                """
                Build an array of arguments for the program.
                """
                subprocess_args = [program]
                if hasattr(self._args, "pp_run_program_arg") and self._args.pp_run_program_arg is not None:
                    for program_arg in self._args.pp_run_program_arg:
                        subprocess_args.append(program_arg)
                return subprocess_args

            self._post_processors = []
            if self._args.pp_trim_trailing_whitespace:
                self._post_processors.append(TrimTrailingWhitespace())
            if hasattr(self._args, "pp_max_emptylines") and self._args.pp_max_emptylines is not None:
                self._post_processors.append(LimitEmptyLines(self._args.pp_max_emptylines))
            if hasattr(self._args, "pp_run_program") and self._args.pp_run_program is not None:
                self._post_processors.append(
                    ExternalProgramEditInPlace(_build_ext_program_postprocessor_args(self._args.pp_run_program))
                )

            self._post_processors.append(SetFileMode(self._args.file_mode))

        return self._post_processors

    @property
    def language_options(self) -> dict[str, typing.Any]:
        """
        Get the language options from the commandline options as a map.
        """
        if self._language_options is None:
            self._language_options = {}
            if self._args.target_endianness is not None:
                self._language_options["target_endianness"] = self._args.target_endianness

            self._language_options["omit_float_serialization_support"] = (
                True if self._args.omit_float_serialization_support else DefaultValue(False)
            )

            self._language_options["enable_serialization_asserts"] = (
                True if self._args.enable_serialization_asserts else DefaultValue(False)
            )

            self._language_options["enable_override_variable_array_capacity"] = (
                True if self._args.enable_override_variable_array_capacity else DefaultValue(False)
            )
            if self._args.language_standard is not None:
                self._language_options["std"] = self._args.language_standard

        return self._language_options

    @property
    def lookup_paths(self) -> list[Path]:
        """
        Get all lookup paths based on arguments and environment variables.
        """
        return [] # TODO

    @property
    def root_paths(self) -> list[Path]:
        """
        Get all root paths based on arguments.
        """
        return [] # TODO

    # --[PRIVATE]----------------------------------------------------------------------------------------------
    def _lookup_paths_from_environment(self) -> list[Path]:
        """
        Parse supported environment variables
        """

        def _extra_includes_from_env(env_var_name: str) -> list[Path]:
            try:
                return [Path(extra) for extra in os.environ[env_var_name].split(os.pathsep)]
            except KeyError:
                return []

        extra_includes: list[str] = self._args.lookup_dir if self._args.lookup_dir is not None else []

        dsdl_include_path = _extra_includes_from_env("DSDL_INCLUDE_PATH")

        if len(dsdl_include_path) > 0:
            logging.info("Additional include directories from DSDL_INCLUDE_PATH: %s", str(dsdl_include_path))

        cyphal_root_paths = _extra_includes_from_env("CYPHAL_PATH")
        cyphal_paths = list(
            map(lambda cyphal_path: [c for c in cyphal_path.glob("*") if c.is_dir()], cyphal_root_paths)
        )

        if len(cyphal_paths) > 0:
            logging.info("Additional include directories from CYPHAL_PATH: %s", str(cyphal_paths))

        extra_includes += sorted(itertools.chain(dsdl_include_path, cyphal_paths))

        return extra_includes


class ArgparseRunner:
    """
    Given a parsed namespace

    :param argparse.Namespace args: The command line arguments.
    :param typing.Optional[typing.Union[Path, typing.List[Path]]] extra_includes: A list of paths to additional DSDL
        root folders.
    """

    def __init__(self, args: argparse.Namespace):
        self._args_interp = ArgumentInterpreter(args)
        self._language_context = self._create_language_context()

    @property
    def args(self) -> argparse.Namespace:
        """
        The arguments used by the runner.
        """
        return self._args_interp.args

    def run(self) -> int:
        """
        Perform actions defined by the arguments this object was created with. This may generate outputs where
        the arguments have requested this action.

        """

        if self.args.list_configuration:
            self._list_configuration_only()

        for root_path in self._args_interp.root_paths:

            generator, support_generator = self._create_generators_for_root(root_path)

            if self.args.list_outputs:
                self._list_outputs_only(generator, support_generator)

            elif self.args.list_inputs:
                self._list_inputs_only(generator, support_generator)

            else:
                self._generate(generator, support_generator)

        return 0

    # --[PRIVATE]--------------------------------------------------------------------------------------------

    def _create_language_context(self) -> LanguageContext:

        if self.args.configuration is None:
            additional_config_files = []
        elif isinstance(self.args.configuration, Path):
            additional_config_files = [self.args.configuration]
        else:
            additional_config_files = self.args.configuration

        target_language_name = self.args.target_language

        builder: LanguageContextBuilder = LanguageContextBuilder(
            include_experimental_languages=self.args.experimental_languages
        )
        builder.set_target_language(target_language_name)
        builder.add_config_files(*additional_config_files)
        builder.set_target_language_extension(self.args.output_extension)
        builder.set_target_language_configuration_override(
            Language.WKCV_NAMESPACE_FILE_STEM, self.args.namespace_output_stem
        )
        builder.set_target_language_configuration_override(
            Language.WKCV_LANGUAGE_OPTIONS, self._args_interp.language_options
        )
        return builder.create()

    def _create_generators_for_root(self, root_namespace_path: Path) -> typing.Tuple[Generator, Generator]:
        if self.args.generate_support != "only" and not self.args.list_configuration:
            type_map = read_dsdl_namespace(
                root_namespace_path,
                self._args_interp.lookup_paths,
                allow_unregulated_fixed_port_id=self.args.allow_unregulated_fixed_port_id,
            )
        else:
            type_map = []

        root_namespace = build_namespace_tree(
            type_map, str(root_namespace_path), self.args.outdir, self._language_context
        )

        #
        # nunavut : create generators
        #
        generator_args = {
            "generate_namespace_types": (
                YesNoDefault.YES if self.args.generate_namespace_types else YesNoDefault.DEFAULT
            ),
            "templates_dir": (Path(self.args.templates) if self.args.templates is not None else None),
            "support_templates_dir": (
                Path(self.args.support_templates) if self.args.support_templates is not None else None
            ),
            "trim_blocks": self.args.trim_blocks,
            "lstrip_blocks": self.args.lstrip_blocks,
            "post_processors": self._args_interp.post_processors,
        }

        return create_default_generators(root_namespace, **generator_args)

    def _stdout_lister(
        self, things_to_list: typing.Iterable[typing.Any], to_string: typing.Callable[[typing.Any], str]
    ) -> None:
        for thing in things_to_list:
            sys.stdout.write(to_string(thing))
            sys.stdout.write(";")

    def _list_outputs_only(self, generator: Generator, support_generator: Generator) -> None:
        if self.args.generate_support != "only":
            self._stdout_lister(generator.generate_all(is_dryrun=True), str)

        if self._args_interp.should_generate_support:
            self._stdout_lister(support_generator.generate_all(is_dryrun=True), str)

    def _list_inputs_only(self, generator: Generator, support_generator: Generator) -> None:
        if self.args.generate_support != "only":
            self._stdout_lister(
                generator.get_templates(omit_serialization_support=self.args.omit_serialization_support),
                lambda p: str(p.resolve()),
            )

        if self._args_interp.should_generate_support:
            self._stdout_lister(
                support_generator.get_templates(omit_serialization_support=self.args.omit_serialization_support),
                lambda p: str(p.resolve()),
            )

        if self.args.generate_support != "only":
            if generator.generate_namespace_types:
                self._stdout_lister(
                    [x for x, _ in generator.namespace.get_all_types()], lambda p: str(p.source_file_path.as_posix())
                )
            else:
                self._stdout_lister(
                    [x for x, _ in generator.namespace.get_all_datatypes()],
                    lambda p: str(p.source_file_path.as_posix()),
                )

    def _list_configuration_only(self) -> None:
        lctx = self._language_context

        import yaml  # pylint: disable=import-outside-toplevel

        sys.stdout.write("target_language: '")
        sys.stdout.write(lctx.get_target_language().name)
        sys.stdout.write("'\n")

        yaml.dump(lctx.config.sections(), sys.stdout, allow_unicode=True)

    def _generate(self, generator: Generator, support_generator: Generator) -> None:
        if self._args_interp.should_generate_support:
            support_generator.generate_all(
                is_dryrun=self.args.dry_run,
                allow_overwrite=not self.args.no_overwrite,
                omit_serialization_support=self.args.omit_serialization_support,
                embed_auditing_info=self.args.embed_auditing_info,
            )

        if self.args.generate_support != "only":
            generator.generate_all(
                is_dryrun=self.args.dry_run,
                allow_overwrite=not self.args.no_overwrite,
                omit_serialization_support=self.args.omit_serialization_support,
                embed_auditing_info=self.args.embed_auditing_info,
            )
