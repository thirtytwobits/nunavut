#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
    Command-line parsers for the Nunavut command-line interface.
"""

import argparse
import itertools
import os
import re
import sys
import textwrap
import typing

from pathlib import Path

from nunavut._utilities import DefaultValue


class NunavutArgumentParser(argparse.ArgumentParser):
    """
    Specialization of argparse.ArgumentParser to encapsulate inter-argument rules, aggregate path arguments, and
    combine language options.

    Adds the following fields to the parsed arguments:

    - root_paths:               A non-empty list of root paths (directories) to search for DSDL files combined from
                                target file colon syntax and path-to-root arguments.
    - target_files:             When not in legacy mode, a non-empty list of target files to process with colon syntax
                                resolved. When in legacy mode, this is not provided.
    - lookup_paths:             A list of additional directories to search for DSDL files. This is a combination of
                                the lookup_dir argument and paths from supported environment variables.
    - language_options:         A dictionary of options to pass to a language context builder.
    - should_generate_support:  Truth based on the generate_support (trinary) and omit_serialization_support arguments.
    - legacy_mode:              A boolean indicating if the provided arguments use the single root path mode which is
                                the legacy behavior of Nunavut.

    """

    # --[ OVERRIDE ]--------------------------------------------------------------------------------------------------
    def parse_known_args(self, args=None, namespace=None):  # type: ignore
        parsed_args, argv = super().parse_known_args(args, namespace)
        self._post_process_args(parsed_args)
        return (parsed_args, argv)

    # --[ PRIVATE ]---------------------------------------------------------------------------------------------------
    def _post_process_log(self, args: argparse.ArgumentParser, message: str) -> None:
        """
        Print a message to the log.
        """
        if args.verbose <= 0:
            return
        if file is None:
            file = sys.stdout
        self._print_message(message, file)

    def _post_process_args(self, args: argparse.Namespace) -> None:
        """
        Applies rules between different arguments and handles other special cases.
        """

        # TODO: make sure the standard generator arg names line up:
        # language_key: str,
        # target_dsdl_files: typing.Iterable[typing.Union[str, Path]],
        # root_namespace_directories_or_names: typing.Iterable[typing.Union[str, Path]],
        # out_dir: Path,
        # omit_serialization_support: bool = True,
        # is_dryrun: bool = False,
        # allow_overwrite: bool = True,
        # lookup_directories: typing.Iterable[typing.Union[str, Path]] = None,
        # allow_unregulated_fixed_port_id: bool = False,
        # language_options: typing.Optional[typing.Mapping[str, typing.Any]] = None,
        # include_experimental_languages: bool = False,
        # embed_auditing_info: bool = False,

        if args.verbose is None:
            args.verbose = 0

        # Check for logic errors in the arguments.
        if args.omit_serialization_support and args.generate_support == "always":
            self.error(
                textwrap.dedent(
                    """
                Logic error: use of --omit-serialization-support and --generate-support=always

                You cannot both omit serialization support and require generation of support code.
            """
                ).lstrip()
            )

        # Add "should_generate_support" determination to the args object.
        if args.generate_support == "as-needed":
            args.should_generate_support = (
                args.omit_serialization_support is None or not args.omit_serialization_support
            )
        else:
            args.should_generate_support = bool(args.generate_support in ("always", "only"))

        # Find all possible path specifications and combine into three collections: root_paths, target_files, and
        # lookup_paths.
        root_paths, target_files = self._parse_target_paths(args.target_files_or_root_namespace)

        args.root_paths = list(root_paths)
        args.legacy_mode = len(args.root_paths) == 1 and args.root_paths[0].is_dir()

        lookup_paths = set(args.lookup_dir) if args.lookup_dir is not None else set()
        args.lookup_paths = list(lookup_paths.union(self._lookup_paths_from_environment(args)))

        if args.path_to_root is not None and args.legacy_mode:
            self.error("Cannot use --path-to-root when using a single root path (legacy syntax).")

        args.root_paths += args.path_to_root if args.path_to_root is not None else []

        if not args.legacy_mode:
            if len(target_files) == 0:
                self.error("No target files provided.")
            else:
                args.target_files = list(target_files)

        if len(args.root_paths) == 0:
            self.error("No root paths provided.")

        # Create a dictionary of language options.
        args.language_options = self._create_language_options(args)


    def _parse_target_paths(self, target_files_or_root_namespace: list[str]) -> typing.Tuple[set[Path], set[Path]]:
        """
        Parse the target paths from the command line arguments.

        :return: A list of root paths (folders) and a list of target paths (files).
        """

        def _parse_lookup_dir(lookup_dir: str) -> typing.Tuple[typing.Optional[Path], typing.Optional[Path]]:
            split_path = re.split(r"(?<!\\):", lookup_dir)
            if len(split_path) > 2:
                self.error(f"Invalid lookup path: {lookup_dir}")
            if len(split_path) == 2:
                return Path(split_path[0]), Path(split_path[1])
            elif (first_path := Path(split_path[0])).is_dir():
                return first_path, None
            else:
                return None, first_path

        if target_files_or_root_namespace is None:
            self.error("No target paths provided.")

        root_paths = set()
        target_files = set()
        for target_path in target_files_or_root_namespace:
            root_dir, target_file_maybe = _parse_lookup_dir(target_path)
            if root_dir is not None:
                root_paths.add(root_dir)
            if target_file_maybe is not None:
                target_files.add(target_file_maybe)

        if len(root_paths) == 0 and len(target_files) == 0:
            self.error("No root paths provided.")
        return root_paths, target_files

    def _lookup_paths_from_environment(self, args: argparse.Namespace) -> set[Path]:
        """
        Parse supported environment variables
        """

        def _extra_includes_from_env(env_var_name: str) -> list[Path]:
            try:
                return [Path(extra) for extra in os.environ[env_var_name].split(os.pathsep)]
            except KeyError:
                return []

        extra_includes: list[str] = []

        dsdl_include_path = _extra_includes_from_env("DSDL_INCLUDE_PATH")

        if len(dsdl_include_path) > 0:
            self._post_process_log(args, f"Extra includes from DSDL_INCLUDE_PATH: {dsdl_include_path}")

        cyphal_root_paths = _extra_includes_from_env("CYPHAL_PATH")
        cyphal_paths = list(
            map(lambda cyphal_path: [c for c in cyphal_path.glob("*") if c.is_dir()], cyphal_root_paths)
        )

        if len(cyphal_paths) > 0:
            self._post_process_log(args, f"Extra includes from CYPHAL_PATH: {cyphal_paths}")

        extra_includes += sorted(itertools.chain(dsdl_include_path, cyphal_paths))

        return set(extra_includes)

    def _create_language_options(self, args: argparse.Namespace) -> dict[str, typing.Any]:
        """
        Group all language options into a dictionary.
        """
        language_options = {}
        if args.target_endianness is not None:
            language_options["target_endianness"] = args.target_endianness

        language_options["omit_float_serialization_support"] = (
            True if args.omit_float_serialization_support else DefaultValue(False)
        )

        language_options["enable_serialization_asserts"] = (
            True if args.enable_serialization_asserts else DefaultValue(False)
        )

        language_options["enable_override_variable_array_capacity"] = (
            True if args.enable_override_variable_array_capacity else DefaultValue(False)
        )
        if args.language_standard is not None:
            language_options["std"] = args.language_standard

        return language_options
