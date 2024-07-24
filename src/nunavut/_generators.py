#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Module containing types and utilities for building generator objects.
Generators abstract the code generation technology used to transform
pydsdl AST into source code.
"""

import abc
import itertools
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Type, Union, cast

from pydsdl import CompositeType
from pydsdl import read_files as read_dsdl_files
from pydsdl import read_namespace as read_dsdl_namespace

from nunavut._namespace import Namespace, build_namespace_tree
from nunavut._utilities import ResourceType, YesNoDefault
from nunavut.lang import LanguageContext, LanguageContextBuilder
from nunavut.lang._language import Language


@dataclass(frozen=True)
class DSDLFilePath:
    """
    A simple data class to hold the path to a DSDL file and the root of the namespace it is in.
    """

    path_to_namespace: Path
    """The path to the root of the namespace containing the DSDL file."""

    source_file_path: Path
    """The path to the DSDL file."""


@dataclass(frozen=True)
class GenerationResult:
    """
    A simple data class to hold the results of a generation operation.
    """

    lctx: LanguageContext
    """The language context used to generate outputs."""

    target_files: list[DSDLFilePath]
    """The set of explicit files targeted for generation."""

    dependent_files: list[DSDLFilePath]
    """
    The set of files determined to be dependencies of one or more `target_files`. Note that no target file will be in
    this list even if it is depended on by another target file. It is assumed that any target file may depend on any
    other target file for a given use of the generation APIs.
    """

    generated_files: list[Path]
    """
    The set of files that were (or would be, for dry runs) generated including support files where these are required.
    """

    template_files: list[Path]
    """
    The set of template files used to generate the `generated_files`.
    """


class AbstractGenerator(metaclass=abc.ABCMeta):
    """
    Abstract base class for classes that generate source file output
    from a given pydsdl parser result.

    :param nunavut.Namespace namespace:  The top-level namespace to
        generates types at and from.
    :param YesNoDefault generate_namespace_types:  Set to YES
        to force generation files for namespaces and NO to suppress.
        DEFAULT will generate namespace files based on the language
        preference.
    :param Any kwargs: Additional arguments to pass into generators.
    """

    def __init__(
        self,
        namespace: Namespace,
        resource_types: int,
        generate_namespace_types: YesNoDefault = YesNoDefault.DEFAULT,
        **kwargs: Any,
    ):  # pylint: disable=unused-argument
        self._namespace = namespace
        self._resource_types = resource_types
        if generate_namespace_types == YesNoDefault.YES:
            self._generate_namespace_types = True
        elif generate_namespace_types == YesNoDefault.NO:
            self._generate_namespace_types = False
        else:
            target_language = self._namespace.get_language_context().get_target_language()
            if target_language.has_standard_namespace_files:
                self._generate_namespace_types = True
            else:
                self._generate_namespace_types = False

    @property
    def namespace(self) -> Namespace:
        """
        The root :class:`nunavut.Namespace` for this generator.
        """
        return self._namespace

    @property
    def resource_types(self) -> int:
        """
        The bitmask of resources to generate. This can be a combination of ResourceType values.
        """
        return self._resource_types

    @property
    def generate_namespace_types(self) -> bool:
        """
        If true then the generator is set to emit files for :class:`nunavut.Namespace`
        in addition to the pydsdl datatypes. If false then only files for pydsdl datatypes
        will be generated.
        """
        return self._generate_namespace_types

    @abc.abstractmethod
    def get_templates(self) -> Iterable[Path]:
        """
        Enumerate all templates found in the templates path.
        :return: A list of paths to all templates found by this Generator object.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def generate_all(
        self,
        is_dryrun: bool = False,
        allow_overwrite: bool = True,
        embed_auditing_info: bool = False,
    ) -> Iterable[Path]:
        """
        Generates all output for a given :class:`nunavut.Namespace` and using
        the templates found by this object.

        :param bool is_dryrun: If True then no output files will actually be
                               written but all other operations will be performed.
        :param bool allow_overwrite: If True then the generator will attempt to overwrite any existing files
                                it encounters. If False then the generator will raise an error if the
                                output file exists and the generation is not a dry-run.
        :param embed_auditing_info: If True then additional information about the inputs and environment used to
                                generate source will be embedded in the generated files at the cost of build
                                reproducibility.
        :return: Iterator over the files generated.
        :raises: PermissionError if :attr:`allow_overwrite` is False and the file exists.
        """
        raise NotImplementedError()


# +---------------------------------------------------------------------------+
# | GENERATION HELPERS
# +---------------------------------------------------------------------------+


def generate_types(
    language_key: str,
    root_namespace_dir: Path,
    out_dir: Path,
    omit_serialization_support: bool = True,
    is_dryrun: bool = False,
    allow_overwrite: bool = True,
    lookup_directories: Optional[Iterable[str]] = None,
    allow_unregulated_fixed_port_id: bool = False,
    language_options: Optional[Mapping[str, Any]] = None,
    include_experimental_languages: bool = False,
    embed_auditing_info: bool = False,
) -> GenerationResult:
    """
    Deprecated; use `generate_all` instead.

    This method is deprecated as it relies on globular file discovery which may cause different results on different
    platforms. Furthermore, this method will not generate dependant types, instead, only generating types found under
    the `root_namespace_dir` (i.e. types found in the lookup directories will not be generated).

    ```
    ██████  ███████ ██████  ██████  ███████  ██████  █████  ████████ ███████ ██████
    ██   ██ ██      ██   ██ ██   ██ ██      ██      ██   ██    ██    ██      ██   ██
    ██   ██ █████   ██████  ██████  █████   ██      ███████    ██    █████   ██   ██
    ██   ██ ██      ██      ██   ██ ██      ██      ██   ██    ██    ██      ██   ██
    ██████  ███████ ██      ██   ██ ███████  ██████ ██   ██    ██    ███████ ██████
    ```

    Use `generate_all` instead which takes a list of target types and will generate code for both the specified types
    and any dependant types. Also, generation of .d files is only supported when using `generate_all`.

    :param str language_key: The name of the language to generate source for.
                See the :doc:`../../docs/templates` for details on available language support.
    :param Path root_namespace_dir: The path to the root of the DSDL types to generate
                code for.
    :param Path out_dir: The path to generate code at and under.
    :param bool omit_serialization_support: If True then logic used to serialize and deserialize data is omitted.
    :param bool is_dryrun: If True then nothing is generated but all other activity is performed and any errors
                that would have occurred are reported.
    :param bool allow_overwrite: If True then generated files are allowed to overwrite existing files under the
                `out_dir` path.
    :param Optional[Iterable[str]] lookup_directories: Additional directories to search for dependent
                types referenced by the types provided under the `root_namespace_dir`. Types will not be generated
                for these unless they are used by a type in the root namespace.
    :param bool allow_unregulated_fixed_port_id: If True then errors will become warning when using fixed port
                identifiers for unregulated datatypes.
    :param Optional[Mapping[str, Any]] language_options: Opaque arguments passed through to the
                language objects. The supported arguments and valid values are different depending on the language
                specified by the `language_key` parameter.
    :param bool include_experimental_languages: If true then experimental languages will also be available.
    :param embed_auditing_info: If True then additional information about the inputs and environment used to
                                generate source will be embedded in the generated files at the cost of build
                                reproducibility.
    :return: A tuple containing lists of target files and generated files. The dependent files list will be empty
                as this method does not generate dependant types.
    """
    if language_options is None:
        language_options = {}

    language_context = (
        LanguageContextBuilder(include_experimental_languages=include_experimental_languages)
        .set_target_language(language_key)
        .set_target_language_configuration_override(Language.WKCV_LANGUAGE_OPTIONS, language_options)
        .create()
    )

    if lookup_directories is None:
        lookup_directories = []

    type_map = read_dsdl_namespace(
        str(root_namespace_dir), lookup_directories, allow_unregulated_fixed_port_id=allow_unregulated_fixed_port_id
    )

    namespace = build_namespace_tree(type_map, str(root_namespace_dir), str(out_dir), language_context)

    from nunavut.jinja import DSDLCodeGenerator, SupportGenerator  # pylint: disable=import-outside-toplevel

    resource_types = (
        ResourceType.ANY.value
        if not omit_serialization_support
        else (ResourceType.ANY.value & ~ResourceType.SERIALIZATION_SUPPORT.value)
    )
    generator = DSDLCodeGenerator(namespace, resource_types)
    support_generator = SupportGenerator(namespace, resource_types)

    template_files = list(support_generator.get_templates())
    generated_files = list(support_generator.generate_all(is_dryrun, allow_overwrite, embed_auditing_info))

    template_files += list(generator.get_templates())
    generated_files += list(generator.generate_all(is_dryrun, allow_overwrite, embed_auditing_info))
    return GenerationResult(
        language_context,
        [DSDLFilePath(ct.source_file_path_to_root, ct.source_file_path) for ct in type_map],
        [],
        generated_files,
        template_files,
    )


# pylint: disable=too-many-arguments, too-many-locals
def generate_all(
    target_language: str,
    target_files: Iterable[Union[str, Path]],
    root_namespace_directories_or_names: Iterable[Union[str, Path]],
    outdir: Path,
    resource_types: int = ResourceType.ANY.value,
    dry_run: bool = False,
    no_overwrite: bool = False,
    allow_unregulated_fixed_port_id: bool = False,
    language_options: Optional[Mapping[str, Any]] = None,
    include_experimental_languages: bool = False,
    embed_auditing_info: bool = False,
    code_generator_type: Optional[Type[AbstractGenerator]] = None,
    support_generator_type: Optional[Type[AbstractGenerator]] = None,
    generate_namespace_types: YesNoDefault = YesNoDefault.DEFAULT,
    **kwargs: Any,
) -> GenerationResult:
    """
    Helper method that uses default settings and built-in templates to generate types for a given
    language. This method is the most direct way to generate code using Nunavut.

    :param str target_language: The name of the language to generate source for.
                See the :doc:`../../docs/templates` for details on available language support.
    :param target_files: A list of paths to dsdl files. This method will generate code for these files and their
                dependant types.
    :param root_namespace_directories_or_names: This can be a set of names of root namespaces or relative paths to
        root namespaces. All ``dsdl_files`` provided must be under one of these roots. For example, given:

        .. code-block:: python

            target_dsdl_files = [
                            Path("workspace/project/types/animals/felines/Tabby.1.0.dsdl"),
                            Path("workspace/project/types/animals/canines/Boxer.1.0.dsdl"),
                            Path("workspace/project/types/plants/trees/DouglasFir.1.0.dsdl")
                        ]


        then this argument must be one of:

        .. code-block:: python

            root_namespace_directories_or_names = ["animals", "plants"]

            root_namespace_directories_or_names = [
                                                    Path("workspace/project/types/animals"),
                                                    Path("workspace/project/types/plants")
                        ]


    :param Path outdir:
        The path to generate code at and under.
    :param int resource_types:
        Bitmask of resources to generate. This can be a combination of ResourceType values. For example, to generate
        only serialization support code, set this to ResourceType.SERIALIZATION_SUPPORT.value. To generate all resources
        set this to ResourceType.ANY.value. To only generate resource files (i.e. to omit source code generation) set
        the ResourceType.ONLY.value bit and the resource type bytes you do want to generate.
    :param bool dry_run:
        If True then no files will be generated/written but all logic will be exercised with commensurate logging and
        errors.
    :param bool no_overwrite:
        If True then generated files will not be allowed to overwrite existing files under the `outdir` path causing
        errors.
    :param Optional[Iterable[Union[str, Path]]] lookup_dir:
        Directories to search for dependent types when included within DSDL files.
    :param bool allow_unregulated_fixed_port_id:
        If True then errors will become warning when using fixed port identifiers for unregulated datatypes.
    :param Optional[Mapping[str, Any]] language_options: Opaque arguments passed through to the language objects. The
        supported arguments and valid values are different depending on the language specified by the `language_key`
        parameter.
    :param bool include_experimental_languages:
        If true then experimental languages will also be available.
    :param embed_auditing_info:
        If True then additional information about the inputs and environment used to generate source will be embedded in
        the generated files at the cost of build reproducibility.
    :param Optional[Type[AbstractGenerator]] code_generator_type: The type of code generator to use. If None then a
        default code generator will be used.
    :param Optional[Type[AbstractGenerator]] support_generator_type: The type of support generator to use. If None then
        a default support generator will be used.
    :param kwargs: Additional arguments passed into the generator constructors.

    :returns GenerationResult: A dataclass containing lists of target files, dependent files, and generated files
        (i.e explicit inputs, discovered inputs, and determined outputs).
    """
    generated_files: set[Path] = set()
    template_files: set[Path] = set()
    # translate the support_templates_dir argument to templates_dir for creating the support generator
    support_kwargs = kwargs.copy()
    support_kwargs["templates_dir"] = kwargs.get("support_templates_dir", [])

    if resource_types & ResourceType.ANY.value:
        if support_generator_type is None:
            from nunavut.jinja import SupportGenerator  # pylint: disable=import-outside-toplevel

            support_generator_type_resolved = cast(type[AbstractGenerator], SupportGenerator)
        else:
            support_generator_type_resolved = support_generator_type
    else:
        support_generator_type_resolved = None

    if not resource_types & ResourceType.ONLY.value:
        if code_generator_type is None:
            from nunavut.jinja import DSDLCodeGenerator  # pylint: disable=import-outside-toplevel

            code_generator_type_resolved = cast(type[AbstractGenerator], DSDLCodeGenerator)
        else:
            code_generator_type_resolved = code_generator_type
    else:
        code_generator_type_resolved = None

    if code_generator_type_resolved is None and support_generator_type_resolved is None:
        logging.warning(
            "No resource types selected for generation and code generation was disabled. Nothing to do. This was a "
            "useless call to generate_all()."
        )
    else:
        language_context = (
            LanguageContextBuilder(include_experimental_languages=include_experimental_languages)
            .set_target_language(target_language)
            .set_target_language_configuration_override(Language.WKCV_LANGUAGE_OPTIONS, language_options)
            .create()
        )

        if len(target_files) > 0:
            target_dsdl_files, dependent_dsdl_files = read_dsdl_files(
                target_files,
                root_namespace_directories_or_names,
                allow_unregulated_fixed_port_id=allow_unregulated_fixed_port_id,
            )

            dsdl_files_by_namespace: dict[Path, list[CompositeType]] = {}

            if not kwargs.get("omit_dependencies", False):
                files_to_generate = itertools.chain(target_dsdl_files, dependent_dsdl_files)
            else:
                files_to_generate = target_dsdl_files

            for dsdl_file in files_to_generate:
                root_path = dsdl_file.source_file_path_to_root
                dsdl_files_by_namespace.setdefault(root_path, []).append(dsdl_file)

            for root_namespace_dir, dsdl_files in dsdl_files_by_namespace.items():
                namespace = build_namespace_tree(dsdl_files, str(root_namespace_dir), str(outdir), language_context)

                if support_generator_type_resolved is not None:
                    support_generator = support_generator_type_resolved(
                        namespace, resource_types, generate_namespace_types=generate_namespace_types, **support_kwargs
                    )
                    template_files.update(support_generator.get_templates())
                    generated_files.update(
                        support_generator.generate_all(dry_run, not no_overwrite, embed_auditing_info)
                    )

                if code_generator_type_resolved is not None:
                    generator = code_generator_type_resolved(
                        namespace, generate_namespace_types=generate_namespace_types, **kwargs
                    )
                    template_files.update(generator.get_templates())
                    generated_files.update(generator.generate_all(dry_run, not no_overwrite, embed_auditing_info))
        else:
            target_dsdl_files, dependent_dsdl_files = [], []

            if support_generator_type_resolved is not None:
                namespace = build_namespace_tree([], "", str(outdir), language_context)
                support_generator = support_generator_type_resolved(
                    namespace, resource_types, generate_namespace_types=generate_namespace_types, **support_kwargs
                )
                template_files.update(support_generator.get_templates())
                generated_files.update(support_generator.generate_all(dry_run, not no_overwrite, embed_auditing_info))
            else:
                logging.info("No target files provided and no support files would be generated. Nothing to do.")

    return GenerationResult(
        language_context,
        [DSDLFilePath(ct.source_file_path_to_root, ct.source_file_path) for ct in target_dsdl_files],
        [DSDLFilePath(ct.source_file_path_to_root, ct.source_file_path) for ct in dependent_dsdl_files],
        list(generated_files),
        list(template_files),
    )
