#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
    Command-line for using nunavut and jinja to generate code
    from dsdl definitions.
"""

import argparse
import pathlib
import sys
import textwrap
import typing


class _LazyVersionAction(argparse._VersionAction):
    """
    Changes argparse._VersionAction so we only load nunavut.version
    if the --version action is requested.
    """

    # pylint: disable=protected-access

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: typing.Any,
        option_string: typing.Optional[str] = None,
    ) -> None:
        # pylint: disable=import-outside-toplevel
        from nunavut._version import __version__

        parser._print_message(__version__, sys.stdout)
        parser.exit()


class _NunavutArgumentParser(argparse.ArgumentParser):
    """
    Specialization of argparse.ArgumentParser to encapsulate inter-argument rules.
    """

    def parse_known_args(self, args=None, namespace=None):  # type: ignore
        parsed_args, argv = super().parse_known_args(args, namespace)
        self._post_process_args(parsed_args)
        return (parsed_args, argv)

    def _post_process_args(self, args: argparse.Namespace) -> None:
        """
        Applies rules between different arguments and handles other special cases.
        """

        if args.omit_serialization_support and args.generate_support == "always":
            self.error(
                textwrap.dedent(
                    """
                Logic error: use of --omit-serialization-support and --generate-support=always

                You cannot both omit serialization support and require generation of support code.
            """
                ).lstrip()
            )


def _make_parser() -> argparse.ArgumentParser:
    """
    Defines the command-line interface. Provided as a separate factory method to
    support sphinx-argparse documentation.
    """

    epilog = textwrap.dedent(
        """

        **Example Usage**::

            # This would include j2 templates for a folder named 'c_jinja'
            # and generate .h files into a directory named 'include' for
            # the uavcan.node.Heartbeat.1.0 data type and its dependencies

            nnvg --outdir include --templates c_jinja -e .h dsdl/uavcan::node/7509.Heartbeat.1.0.dsdl

    """
    )

    parser = _NunavutArgumentParser(
        description="Generate code from Cyphal DSDL using pydsdl and jinja2",
        epilog=epilog,
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--path-to-root",
        "-r",
        action="append",
        help=textwrap.dedent(
            """
        When operating on a target set of dsdl files this argument is required to specify
        a set of valid paths to or folder names of root namespaces. For example:

            nnvg types/animals/felines/Tabby.1.0.dsdl types/animals/canines/Boxer.1.0.dsdl

        will fail unless the path describing the root is provided:

            nnvg --path-to-root types/animals types/animals/cats/Tabby.1.0.dsdl types/animals/dogs/Boxer.1.0.dsdl

        If multiple roots are targeted then each root path will need to be enabled:

            nnvg -r types/animals -r types/plants types/animals/cats/Tabby.1.0.dsdl types/plants/trees/Fir.1.0.dsdl

        An additional syntax is supported where the root can be specified as part of the target
        path using a colon to separate the two which obviates the need to provide this argument:

            nnvg types/animals:cats/Tabby.1.0.dsdl types/plants:trees/Fir.1.0.dsdl

        When in legacy mode (given a single path, not target files) this argument is ignored.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "target_files_or_root_namespace",
        default=".",
        nargs="*",
        help=textwrap.dedent(
            """

        One or more dsdl files to generate from.

        All dependent types found in the target dsdl files will be generated and must be
        available either as another target or as a dsdl file under one of the --lookup-dir
        directories.

        A --path-to-root argument for each unique root path among the list of files is
        required if not using the colon syntax.

        Colon Syntax:

            The standard syntax allows the path to the root to be specified at the same
            time as the type:

                path/to/root:name/space/Type.1.0.dsdl

            This also adds the path to a list of valid paths. You can continue to specify
            it (duplicates are ignored) or you can specify it once:

                path/to/root:name/space/Type.1.0.dsdl name/space/Type.1.0.dsdl

                ...is the same as...

                path/to/root:name/space/Type.1.0.dsdl path/to/root:name/space/Type.1.0.dsdl

            Two colons do everything described above but also adds the path-to-root to
            the list of lookup directories (--lookup-dir):

                path/to/uavcan::node/7509.Heartbeat.1.0.dsdl node/430.GetInfo.1.0.dsdl

                ...node.Health.1.0 will also be generated because the Heartbeat
                   depends on it and it can be found under path/to/uavcan


        Deprecated/Legacy Behaviour:

            If a single path is provided then this script runs in legacy mode where this path
            is treated as a root namespace to generate types from. In this mode no dependent
            types will be generated unless they are also found under this folder.
    """
        ).lstrip(),
    )

    parser.add_argument(
        "--lookup-dir",
        "-I",
        action="append",
        help=textwrap.dedent(
            """

        List of other namespace directories containing data type definitions that are
        referred to from the target root namespace. For example, if you are reading a
        vendor-specific namespace, the list of lookup directories should always include
        a path to the standard root namespace "uavcan", otherwise the types defined in
        the vendor-specific namespace won't be able to use data types from the standard
        namespace.

        Additional directories can also be specified through an environment variable
        DSDL_INCLUDE_PATH where the path entries are separated by colons ":" on
        posix systems and ";" on Windows.

        CYPHAL_PATH will also be used to create additional includes where each folder
        directly under this path will a lookup directory.

    """
        ).lstrip(),
    )

    parser.add_argument("--verbose", "-v", action="count", help="verbosity level (-v, -vv)")

    parser.add_argument("--version", action=_LazyVersionAction)

    parser.add_argument("--outdir", "-O", default="nunavut_out", help="output directory")

    parser.add_argument(
        "--templates",
        help=textwrap.dedent(
            """

        Paths to a directory containing templates to use when generating code.

        Templates found under these paths will override the built-in templates for a
        given language.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--support-templates",
        help=textwrap.dedent(
            """

        Paths to a directory containing templates to use when generating support code.

        Templates found under these paths will override the built-in support templates for a
        given language.

    """
        ).lstrip(),
    )

    def extension_type(raw_arg: str) -> str:
        if len(raw_arg) > 0 and not raw_arg.startswith("."):
            return "." + raw_arg
        else:
            return raw_arg

    parser.add_argument(
        "--target-language",
        "-l",
        help=textwrap.dedent(
            """

        Language support to install into the templates.

        If provided then the output extension (--e) can be inferred otherwise the output
        extension must be provided.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--experimental-languages",
        "-Xlang",
        action="store_true",
        help=textwrap.dedent(
            """

        Activate languages with unstable, experimental support.

        By default, target languages where support is not finalized are not
        enabled when running nunavut, to make it clear that the code output
        may change in a non-backwards-compatible way in future versions, or
        that it might not even work yet.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--output-extension",
        "-e",
        type=extension_type,
        help="The extension to use for generated files.",
    )

    parser.add_argument("--dry-run", "-d", action="store_true", help="If True then no files will be generated.")

    parser.add_argument(
        "--list-outputs",
        action="store_true",
        help=textwrap.dedent(
            """
        Emit a semicolon-separated list of files.
        (implies --dry-run)
        Emits files that would be generated if invoked without --dry-run.
        This command is useful for integrating with CMake and other build
        systems that need a list of targets to determine if a rebuild is
        necessary.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--generate-support",
        choices=["always", "never", "as-needed", "only"],
        default="as-needed",
        help=textwrap.dedent(
            """
        Change the criteria used to enable or disable support code generation.

        as-needed (default) - generate support code if serialization is enabled.
        always - always generate support code.
        never - never generate support code.
        only - only generate support code.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--list-inputs",
        action="store_true",
        help=textwrap.dedent(
            """

        Emit a semicolon-separated list of files.
        (implies --dry-run)
        A list of files that are resolved given input arguments like templates.
        This command is useful for integrating with CMake and other build systems
        that need a list of inputs to determine if a rebuild is necessary.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--generate-namespace-types",
        action="store_true",
        help=textwrap.dedent(
            """
        If enabled this script will generate source for namespaces.
        All namespaces including and under the root namespace will be treated as a
        pseudo-type and the appropriate template will be used. The generator will
        first look for a template with the stem "Namespace" and will then use the
        "Any" template if that is available. The name of the output file will be
        the default value for the --namespace-output-stem argument and can be
        changed using that argument.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--omit-serialization-support",
        "-pod",
        action="store_true",
        help=textwrap.dedent(
            """
        If provided then the types generated will be POD datatypes with no additional logic.
        By default types generated include serialization routines and additional support libraries,
        headers, or methods.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--namespace-output-stem",
        help="The name of the file generated when --generate-namespace-types is provided.",
    )

    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help=textwrap.dedent(
            """

        By default, generated files will be silently overwritten by
        subsequent invocations of the generator. If this argument is specified an
        error will be raised instead preventing overwrites.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--file-mode",
        default=0o444,
        type=lambda value: int(value, 0),
        help=textwrap.dedent(
            """

        The file-mode each generated file is set to after it is created.
        Note that this value is interpreted using python auto base detection.
        Because of this, to provide an octal value, you'll need to prefix your
        literal with '0o' (e.g. --file-mode 0o664).

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--trim-blocks",
        action="store_true",
        help=textwrap.dedent(
            """

        If this is set to True the first newline after a block in a template
        is removed (block, not variable tag!).

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--lstrip-blocks",
        action="store_true",
        help=textwrap.dedent(
            """

        If this is set to True leading spaces and tabs are stripped from the
        start of a line to a block in templates.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--allow-unregulated-fixed-port-id",
        action="store_true",
        help=textwrap.dedent(
            """

        Do not reject unregulated fixed port identifiers.
        This is a dangerous feature that must not be used unless you understand the
        risks. The background information is provided in the Cyphal specification.

    """
        ).lstrip(),
    )

    parser.add_argument(
        "--embed-auditing-info",
        action="store_true",
        help=textwrap.dedent(
            """

        If set, generators are instructed to add additional information in the form of
        language-specific comments or meta-data to use when auditing source code generated by
        Nunavut. This data may change based on the environment in use which may interfere with
        the reproducibility of your builds. For example, paths to input files used to generate
        a type may be included with this option where these paths will be different depending
        on the server used to run nnvg.

    """
        ).lstrip(),
    )

    # +-----------------------------------------------------------------------+
    # | Post-Processing Options
    # +-----------------------------------------------------------------------+

    ln_pp_group = parser.add_argument_group(
        "post-processing options",
        description=textwrap.dedent(
            """

        Options that enable various post-generation steps because Pavel Kirienko doesn't
        like writing jinja templates.

    """
        ).lstrip(),
    )

    ln_pp_group.add_argument(
        "--pp-max-emptylines",
        type=int,
        help=textwrap.dedent(
            """

        If provided this will suppress generation of additional consecutive
        empty lines beyond the limit set by this argument.

        Note that this will insert a line post-processor which may reduce
        performance. Consider using a code formatter on the generated output
        to enforce whitespace rules instead.

    """
        ).lstrip(),
    )

    ln_pp_group.add_argument(
        "--pp-trim-trailing-whitespace",
        action="store_true",
        help=textwrap.dedent(
            """

        Enables a line post-processor that will elide all whitespace at the
        end of each line.

        Note that this will insert a line post-processor which may reduce
        performance. Consider using a code formatter on the generated output
        to enforce whitespace rules instead.

    """
        ).lstrip(),
    )

    ln_pp_group.add_argument(
        "-pp-rp",
        "--pp-run-program",
        help=textwrap.dedent(
            """

        Runs a program after each file is generated but before the file is
        set to read-only.

        example ::

            # invokes clang-format with the "in-place" argument on each file after it is
            # generated.

            nnvg --outdir include --templates c_jinja -e .h -pp-rp clang-format -pp-rpa=-i dsdl

    """
        ).lstrip(),
    )

    ln_pp_group.add_argument(
        "-pp-rpa",
        "--pp-run-program-arg",
        action="append",
        help=textwrap.dedent(
            """

        Additional arguments to provide to the program specified by --pp-run-program.
        The last argument will always be the path to the generated file.

    """
        ).lstrip(),
    )

    # +-----------------------------------------------------------------------+
    # | Language Options
    # +-----------------------------------------------------------------------+
    ln_opt_group = parser.add_argument_group(
        "language options",
        description=textwrap.dedent(
            """

        Options passed through to templates as `options` on the target language.

        Note that these arguments are passed though without validation, have no effect on the Nunavut
        library, and may or may not be appropriate based on the target language and generator templates
        in use.
    """
        ).lstrip(),
    )

    ln_opt_group.add_argument(
        "--target-endianness",
        choices=["any", "big", "little"],
        help=textwrap.dedent(
            """

        Specify the endianness of the target hardware. This allows serialization
        logic to be optimized for different CPU architectures.

    """
        ).lstrip(),
    )

    ln_opt_group.add_argument(
        "--omit-float-serialization-support",
        action="store_true",
        help=textwrap.dedent(
            """

        Instruct support header generators to omit support for floating point operations
        in serialization routines. This will result in errors if floating point types are used,
        however; if you are working on a platform without IEEE754 support and do not use floating
        point types in your message definitions this option will avoid dead code or compiler
        errors in generated serialization logic.

    """
        ).lstrip(),
    )

    ln_opt_group.add_argument(
        "--enable-serialization-asserts",
        action="store_true",
        help=textwrap.dedent(
            """

        Instruct support header generators to generate language-specific assert statements as part
        of serialization routines. By default the serialization logic generated may make assumptions
        based on documented requirements for calling logic that could expose a system to undefined
        behavior. The alternative, for languages that do not support exception handling, is to
        use assertions designed to halt a program rather than execute undefined logic.

    """
        ).lstrip(),
    )

    ln_opt_group.add_argument(
        "--enable-override-variable-array-capacity",
        action="store_true",
        help=textwrap.dedent(
            """

        Instruct support header generators to add the possibility to override max capacity of a
        variable length array in serialization routines. This option will disable serialization
        buffer checks and add conditional compilation statements which violates MISRA.

    """
        ).lstrip(),
    )

    ln_opt_group.add_argument(
        "--language-standard",
        "-std",
        choices=["c11", "c++14", "cetl++14-17", "c++17", "c++17-pmr", "c++20"],
        help=textwrap.dedent(
            """

        For language generators that support different standards of their core language this option
        can be used to optimize the output. For example, C templates may generate slightly different
        code for the the c99 standard then for c11. For available support in Nunavut see the
        documentation for built-in templates
        (https://nunavut.readthedocs.io/en/latest/docs/templates.html#built-in-template-guide).

    """
        ).lstrip(),
    )

    ln_opt_group.add_argument(
        "--configuration",
        "-c",
        nargs="*",
        type=pathlib.Path,
        help=textwrap.dedent(
            """

        There is a set of built-in configuration for Nunavut that provides default values for known
        languages as documented `in the template guide
        <https://nunavut.readthedocs.io/en/latest/docs/templates.html#language-options>`_. This argument lets you
        specify override configuration yamls.
    """
        ).lstrip(),
    )

    ln_opt_group.add_argument(
        "--list-configuration",
        "-lc",
        action="store_true",
        help=textwrap.dedent(
            """

        Lists all configuration values resolved for the given arguments.

    """
        ).lstrip(),
    )

    return parser
