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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Type, Union, cast

from pydsdl import CompositeType
from pydsdl import read_files as read_dsdl_files
from pydsdl import read_namespace as read_dsdl_namespace

from nunavut._namespace import Namespace, NamespaceFactory, build_namespace_tree
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
class GeneratorTarget:
    """
    Holds information about a dsdl file that is a target for code generation.
    """

    target_file: DSDLFilePath
    """The target file to generate code for."""

    generated_file_path: Path
    """The path to a file that will be, or has been generated for the target file."""

    dsdl_dependencies: list[DSDLFilePath]
    """The set DSDL files the target file depends on."""


@dataclass(frozen=True)
class GenerationResult:
    """
    A simple data class to hold the results of a generation operation.
    """

    lctx: LanguageContext
    """The language context used to generate outputs."""

    generator_targets: dict[Path, GeneratorTarget]
    """The set of explicit files targeted for generation and their dependant files."""

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
    ) -> Iterable[Path]:
        """
        Generates all output for a given :class:`nunavut.Namespace` and using
        the templates found by this object.

        :param bool is_dryrun: If True then no output files will actually be
                               written but all other operations will be performed.
        :param bool allow_overwrite: If True then the generator will attempt to overwrite any existing files
                                it encounters. If False then the generator will raise an error if the
                                output file exists and the generation is not a dry-run.
        :return: Iterator over the files generated.
        :raises: PermissionError if :attr:`allow_overwrite` is False and the file exists.
        """
        raise NotImplementedError()


class MultiGenerator(AbstractGenerator):
    """
    A generator that combines multiple generators into a single generator.
    """

    def __init__(self, namespace: Namespace, resource_types: int, generators: Iterable[AbstractGenerator]):
        super().__init__(namespace, resource_types)
        self._generators = generators

    def get_templates(self) -> Iterable[Path]:
        return itertools.chain.from_iterable(gen.get_templates() for gen in self._generators)

    def generate_all(self, is_dryrun: bool = False, allow_overwrite: bool = True) -> Iterable[Path]:
        return itertools.chain.from_iterable(gen.generate_all(is_dryrun, allow_overwrite) for gen in self._generators)


class MultiGeneratorBuilder:
    """
    A container for building MultiGenerators for different namespaces.
    """

    def __init__(self, language_context: LanguageContext, output_dir: Path, root_namespace_dir: Path) -> None:
        self._language_context = language_context
        self._generators: list[Type[AbstractGenerator], Any] = []
        self._output_dir = output_dir
        self._resource_types: int = ResourceType.ANY.value
        self._dsdl_types: set[CompositeType] = set()
        self._nsf: NamespaceFactory = NamespaceFactory(language_context, output_dir, root_namespace_dir)

    def __len__(self) -> int:
        return len(self._generators)

    def add_generator_type(self, generator_class: Type[AbstractGenerator], **overrides: Any) -> "MultiGeneratorBuilder":
        """
        Add a generator to the list of generators to combine.
        """
        self._generators.append((generator_class, overrides))
        return self

    def set_resource_types(self, resource_types: int) -> "MultiGeneratorBuilder":
        """
        Set the resource types for the generators.
        """
        self._resource_types = resource_types
        return self

    def update_dsdl_types(self, dsdl_types: list[CompositeType]) -> "MultiGeneratorBuilder":
        """
        Set the DSDL types for the generators.
        """
        self._nsf.add_types(dsdl_types)
        return self

    def get_root_namespace(self) -> Optional[Namespace]:
        """
        Get the root namespace determined so far. This will be none if no
        """
        return self._nsf.get_root_namespace()

    def create(
        self,
        **kwargs: Any,
    ) -> MultiGenerator:
        """
        Create a new generator that combines all the generators added to this builder.
        """
        root_namespace = self.get_root_namespace()
        generators: list[AbstractGenerator] = []
        for gen, overrides in self._generators:
            args_copy = kwargs.copy()
            args_copy.update(overrides)
            generators.append(gen(root_namespace, self._resource_types, **args_copy))
        return MultiGenerator(root_namespace, self._resource_types, generators)


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

    .. code-block:: text

        ██████  ███████ ██████  ██████  ███████  ██████  █████  ████████ ███████ ██████
        ██   ██ ██      ██   ██ ██   ██ ██      ██      ██   ██    ██    ██      ██   ██
        ██   ██ █████   ██████  ██████  █████   ██      ███████    ██    █████   ██   ██
        ██   ██ ██      ██      ██   ██ ██      ██      ██   ██    ██    ██      ██   ██
        ██████  ███████ ██      ██   ██ ███████  ██████ ██   ██    ██    ███████ ██████


    Use `generate_all` instead which takes a list of target types and will generate code for both the specified types
    and any dependant types. Also, generation of .d files is only supported when using `generate_all`.

    :param str language_key: The name of the language to generate source for.
                See the :doc:`../../docs/templates` for details on available language support.
    :param Path root_namespace_dir: The path to the root of the DSDL types to generate
                code for.
    :param Path out_dir: The path to generate code at and under.
    :param bool omit_serialization_support: If True then logic used to serialize and deserialize data is omitted from
                generated code.
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
    :return: A dataclass containing the language context used to generate outputs, the set of target files discovered,
             the template files used to generate the outputs, and the generated file paths. This legacy method does not
             return the set of dependent files generated nor does it return the set of root namespace directories.
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
    generator = DSDLCodeGenerator(namespace, resource_types, embed_auditing_info=embed_auditing_info)
    support_generator = SupportGenerator(namespace, resource_types, embed_auditing_info=embed_auditing_info)

    template_files = list(support_generator.get_templates())
    generated_files = list(support_generator.generate_all(is_dryrun, allow_overwrite))

    template_files += list(generator.get_templates())
    generated_files += list(generator.generate_all(is_dryrun, allow_overwrite))
    return GenerationResult(
        language_context,
        {},
        generated_files,
        template_files,
    )


# pylint: disable=too-many-arguments, too-many-locals, too-many-statements
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
    depfile: bool = False,
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

            # or

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

    :returns GenerationResult: A dataclass containing explicit inputs, discovered inputs, and determined outputs.
    """
    generated_files: set[Path] = set()
    template_files: set[Path] = set()
    # translate the support_templates_dir argument to templates_dir for creating the support generator
    support_kwargs = kwargs.copy()
    support_kwargs["templates_dir"] = kwargs.get("support_templates_dir", [])

    language_context = (
        LanguageContextBuilder(include_experimental_languages=include_experimental_languages)
        .set_target_language(target_language)
        .set_target_language_configuration_override(Language.WKCV_LANGUAGE_OPTIONS, language_options)
        .create()
    )

    def _write_dep_file_maybe(generation_result: GenerationResult) -> GenerationResult:
        """
        Write a .dep file to the output directory containing the paths of all generated files and the template files
        used to generate them.

        :param GenerationResult generation_result: The result of a generation operation to record in the dep file.
        """

        if depfile:
            depfile_path = outdir / "nunavut.make"
            with depfile_path.open("w", encoding="utf-8") as f:
                # Full manifest in comments
                f.write("# Generated Files:\n")
                for file in generation_result.generated_files:
                    f.write(f"#  - {file}\n")
                f.write("\n# Template Files:\n")
                for file in generation_result.template_files:
                    f.write(f"#  - {file}\n")
                f.write("\n# Rules:\n")
                for target in generation_result.generator_targets.values():
                    f.write(
                        f"\n# Target: {target.target_file.path_to_namespace.stem}/…/{target.generated_file_path.name}\n"
                    )
                    f.write(f"{target.generated_file_path}: {target.target_file.source_file_path}")
                    for dep in target.dsdl_dependencies:
                        f.write(f" {dep.source_file_path}")
                    for file in generation_result.template_files:
                        f.write(f" {file}")
                    f.write("\n")
                # TODO: support file rules and as dependencies

        return generation_result

    def _create_multigen_builder(root_namespace_dir: Path) -> MultiGeneratorBuilder:
        """
        Create a MultiGeneratorBuilder with the selected generator types.
        """
        multigen_builder = MultiGeneratorBuilder(language_context, outdir, root_namespace_dir)
        if resource_types & ResourceType.ANY.value:
            if support_generator_type is None:
                from nunavut.jinja import SupportGenerator  # pylint: disable=import-outside-toplevel

                support_generator_type_resolved = cast(type[AbstractGenerator], SupportGenerator)
            else:
                support_generator_type_resolved = support_generator_type

            multigen_builder.add_generator_type(
                cast(type[AbstractGenerator], support_generator_type_resolved),
                templates_dir=kwargs.get("support_templates_dir", []),
            )

        if not resource_types & ResourceType.ONLY.value:
            if code_generator_type is None:
                from nunavut.jinja import DSDLCodeGenerator  # pylint: disable=import-outside-toplevel

                code_generator_type_resolved = cast(type[AbstractGenerator], DSDLCodeGenerator)
            else:
                code_generator_type_resolved = code_generator_type

            multigen_builder.add_generator_type(cast(type[AbstractGenerator], code_generator_type_resolved))

        return multigen_builder.set_resource_types(resource_types)

    # A queue that starts with all the target files and is expanded with dependent files as they are discovered.
    # It's essential that any circular dependencies between target files are handled correctly or this will
    # result in an infinite loop.
    target_file_queue = [Path(target_file) for target_file in target_files]

    # A dictionary that maps target files to their dependant files. This is used to build the dependency graph.
    generator_targets: dict[Path, GeneratorTarget] = {}

    # we need to build generators for each root namespace directory. This caches each generator builder by the
    # root namespace directory allowing us to assemble the generator arguments based on each target file before
    # we commit to creating all the generators and generating the code
    multi_generator_builder_index: dict[Path, MultiGeneratorBuilder] = {}

    while len(target_file_queue) > 0:

        target_file = target_file_queue.pop(0)

        if target_file in generator_targets:
            # TODO handle path resolution (i.e. is same file but different path)
            continue

        target_dsdl_types, dependent_dsdl_types_for_target = read_dsdl_files(
            target_file,
            root_namespace_directories_or_names,
            allow_unregulated_fixed_port_id=allow_unregulated_fixed_port_id,
        )

        assert len(target_dsdl_types) == 1

        target_dsdl_type = target_dsdl_types[0]

        if not kwargs.get("omit_dependencies", False):
            target_file_queue.extend([dep.source_file_path for dep in dependent_dsdl_types_for_target])
        # elif we are omit(ting)_dependencies then we only generate the target files.

        try:
            multigen_builder = multi_generator_builder_index[
                target_dsdl_type.source_file_path_to_root
            ].update_dsdl_types(target_dsdl_types)
        except KeyError:
            multigen_builder = _create_multigen_builder(target_dsdl_type.source_file_path_to_root).update_dsdl_types(
                target_dsdl_types
            )
            multi_generator_builder_index[target_dsdl_type.source_file_path_to_root] = multigen_builder

        target_outfile = multigen_builder.get_root_namespace().find_output_path_for_type(target_dsdl_type)

        generator_targets[target_dsdl_type.source_file_path] = GeneratorTarget(
            DSDLFilePath(target_dsdl_type.source_file_path_to_root, target_dsdl_type.source_file_path),
            target_outfile,
            [
                DSDLFilePath(dep.source_file_path_to_root, dep.source_file_path)
                for dep in dependent_dsdl_types_for_target
            ],
        )

    if len(multi_generator_builder_index) == 0:
        multi_generator = _create_multigen_builder(Path("")).create(
            generate_namespace_types=generate_namespace_types,
            embed_auditing_info=embed_auditing_info,
            **kwargs,
        )
        template_files.update(multi_generator.get_templates())
        generated_files.update(multi_generator.generate_all(dry_run, not no_overwrite))
    else:
        for multigen_builder in multi_generator_builder_index.values():
            multi_generator = multigen_builder.create(
                generate_namespace_types=generate_namespace_types,
                embed_auditing_info=embed_auditing_info,
                **kwargs,
            )
            template_files.update(multi_generator.get_templates())
            generated_files.update(multi_generator.generate_all(dry_run, not no_overwrite))

    return _write_dep_file_maybe(
        GenerationResult(
            language_context,
            generator_targets,
            list(generated_files),
            list(template_files),
        )
    )
