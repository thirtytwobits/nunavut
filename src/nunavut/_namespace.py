#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Namespace object and associated utilities. Nunavut namespaces provide an internal representation of dsdl namespaces
that are also data objects for target languages, like python, that model namespaces as objects.
"""

import collections
from pathlib import Path, Path
from typing import Any, Deque, Generator, ItemsView, Iterable, Iterator, KeysView, Optional, Tuple, Union, ValuesView

import pydsdl

from .lang import Language, LanguageContext
from .lang._common import IncludeGenerator


# +--------------------------------------------------------------------------------------------------------------------+
class Generatable(Path):
    """
    A file that can be generated from a pydsdl type.

    .. invisible-code-block: python

        from nunavut._namespace import Generatable
        from pathlib import Path
        from copy import copy
        import pydsdl
        from unittest.mock import MagicMock
        from pytest import raises

        path = Path("test")
        definition = MagicMock(spec=pydsdl.Any)
        input_types = [MagicMock(spec=pydsdl.Any)]

        gen = Generatable.wrap(path, definition, input_types)

        assert Path("path", "to", "test") == Path("path", "to") / gen
        copy_of_gen = copy(gen)
        assert gen == copy_of_gen
        # Ensure the copy is shallow
        gen._input_types[0].__hash__ = MagicMock(return_value=1)
        hash(gen) == hash(copy_of_gen)

        gen._input_types.clear()
        assert gen != copy_of_gen
        gen = copy(copy_of_gen)
        assert gen == copy_of_gen
        gen._definition = MagicMock(spec=pydsdl.Any)
        assert gen != copy_of_gen

        assert Generatable("foo", definition=MagicMock(spec=pydsdl.Any)) != copy_of_gen

        with raises(ValueError):
            Generatable("foo")

        print(f"{str(gen)}:{repr(gen)}")

        assert str(Path("foo")) == str(Generatable("foo", definition=MagicMock(spec=pydsdl.Any)))
        assert Path("foo") == Generatable("foo/bar", definition=MagicMock(spec=pydsdl.Any)).parent

    """

    @classmethod
    def wrap(cls, path: Path, definition: pydsdl.Any, input_types: list[pydsdl.Any]) -> "Generatable":
        """
        Wrap a Path object with the Generatable interface.

        :param Path path: The path to the generated file.
        :param pydsdl.Any definition: The pydsdl type that can be reified into a generated file.
        :param list[pydsdl.Any] input_types: The types that are required to generate the file.
        :return: A Generatable object.
        """
        return Generatable(path, definition=definition, input_types=input_types)

    def __init__(self, *args, **kwargs):
        try:
            self._definition = kwargs.pop("definition")
        except KeyError as ex:
            raise ValueError("Generatable requires a 'definition' argument.") from ex

        try:
            self._input_types = kwargs.pop("input_types")
        except KeyError:
            self._input_types = []

        super().__init__(*args, **kwargs)

    def with_segments(self, *pathsegments):
        """
        Path override: Construct a new path object from any number of path-like objects.
        We descard the Generatable type here and continue on with a default Path object.
        """
        return Path(*pathsegments)

    @property
    def definition(self) -> pydsdl.Any:
        """
        The pydsdl type that can be reified into a generated file.
        """
        return self._definition

    @property
    def input_types(self) -> list[pydsdl.Any]:
        """
        The types that are required to generate the file.
        """
        return self._input_types.copy()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Generatable):
            return (
                super().__eq__(other) and self.definition == other.definition and self.input_types == other.input_types
            )
        else:
            return False

    def __hash__(self) -> int:
        return hash((super().__hash__(), self.definition))

    def __repr__(self) -> str:
        return (
            f"{super().__repr__()}, " f"definition={repr(self._definition)}, " f"input_types={repr(self._input_types)}"
        )

    def __copy__(self) -> "Generatable":
        return Generatable(self, definition=self.definition, input_types=self.input_types)


# +--------------------------------------------------------------------------------------------------------------------+
class Namespace(pydsdl.Any):  # pylint: disable=too-many-public-methods
    """
    K-ary tree (where K is the largest set of data types in a single dsdl namespace) where
    the nodes represent dsdl namespaces and the children are the datatypes and other nested
    namespaces (with datatypes always being leaf nodes). This structure extends :code:`pydsdl.Any`
    and is a :code:`pydsdl.pydsdl.CompositeType` via duck typing.

    :param str full_namespace:  The full, dot-separated name of the namepace. This is expected to be
                                a unique identifier.
    :param Path root_namespace_dir: The directory representing the dsdl namespace and containing the
                                namespaces's datatypes and nested namespaces.
    :param Path base_output_path: The base path under which all namespaces and datatypes should
                                be generated.
    :param LanguageContext language_context: The generated software language context the namespace is within.
    """

    @classmethod
    def strop_namespace(cls, full_namespace: str, language_context: LanguageContext) -> Tuple[list[str], list[str]]:
        """
        Strop a namespace string for a given language context.

        :param str full_namespace: The dot-separated namespace string to strop.
        :param LanguageContext language_context: The language context to use when stroping the namespace.
        :return: A tuple containing the original namespace components and the stropped namespace components.

        .. invisible-code-block: python

            from nunavut.lang import LanguageContext, LanguageContextBuilder
            from nunavut._namespace import Namespace

            lctx = (
                LanguageContextBuilder()
                    .set_target_language("c")
                    .create()
            )

        .. code-block:: python

            full_namespace = "uavcan.node"
            namespace_components, namespace_components_stropped = Namespace.strop_namespace(full_namespace, lctx)

            assert namespace_components == ["uavcan", "node"]
            assert namespace_components_stropped == ["uavcan", "node"]

        """
        namespace_components = full_namespace.split(".")
        return (
            namespace_components,
            [language_context.filter_id_for_target(component, "path") for component in namespace_components],
        )

    @classmethod
    def add_types(
        cls,
        index: "Namespace",
        types: list[Tuple[pydsdl.CompositeType, list[pydsdl.CompositeType]]],
        extension: Optional[str] = None,
    ) -> "Namespace":
        """
        Add a set of types to a namespace tree building new nodes as needed.

        :param Namespace tree: A namespace tree to add types to. This can be any namespace in the tree as
            :meth:`Namespace.get_index_namespace` will be used to find the meta-namespace.
        :param list types: A list of pydsdl types to add.
        :param str extension: Override the file extension to use for the generated files. If None, the extension will be
            determined by the target language.

        .. invisible-code-block: python

            from nunavut._namespace import Namespace
            from nunavut.lang import LanguageContext, LanguageContextBuilder
            from pathlib import Path
            from unittest.mock import MagicMock
            from pytest import raises
            import pydsdl

            lctx = (
                LanguageContextBuilder()
                    .set_target_language("c")
                    .create()
            )
            base_path = gen_paths.out_dir
            root_namespace_dir = base_path / Path("animalia")
            root_namespace_dir.mkdir(exist_ok=True)

            chordata_folder = root_namespace_dir / Path("chordata")
            chordata_folder.mkdir(exist_ok=True)

            structures_folder = root_namespace_dir / Path("structures")
            structures_folder.mkdir(exist_ok=True)

            mock_aves = MagicMock(spec=pydsdl.CompositeType)
            mock_aves.full_namespace = "animalia.chordata"
            mock_aves.source_file_path_to_root = root_namespace_dir
            mock_aves.source_file_path = chordata_folder / Path("Aves.1.0.dsdl")

            mock_mammal = MagicMock(spec=pydsdl.CompositeType)
            mock_mammal.full_namespace = "animalia.chordata"
            mock_mammal.source_file_path_to_root = root_namespace_dir
            mock_mammal.source_file_path = chordata_folder / Path("Mammal.1.0.dsdl")

            mock_wing = MagicMock(spec=pydsdl.CompositeType)
            mock_wing.full_namespace = "animalia.structures"
            mock_wing.source_file_path_to_root = root_namespace_dir
            mock_wing.source_file_path = structures_folder / Path("Wing.1.0.dsdl")

        .. code-block:: python

            index = Namespace.Identity(base_path, lctx)

            # Add the types to the root namespace.
            Namespace.add_types(
                index,
                [
                    (mock_aves, []),
                    (mock_mammal, []),
                    (mock_wing, [])
                ]
            )

            assert index.get_root_namespace(root_namespace_dir) == index.get_root_namespace(root_namespace_dir)
            assert index.get_root_namespace(root_namespace_dir) != index.get_root_namespace(chordata_folder)

        """
        for dsdl_type, input_types in types:
            # For each type we form a path with the output_dir as the base; the intermediate
            # folders named for the type's namespaces; and a file name that includes the type's
            # short name, major version, minor version, and the extension argument as a suffix.
            # Python's pathlib adapts the provided folder and file names to the platform
            # this script is running on.
            # We also, lazily, generate Namespace nodes as we encounter new namespaces for the
            # first time.

            root_namespace = index.get_root_namespace(dsdl_type.source_file_path_to_root)
            root_namespace._add_data_type(dsdl_type, input_types, extension)  # pylint: disable=protected-access

    @classmethod
    def Identity(cls, output_path: Path, lctx: LanguageContext) -> "Namespace":
        """
        Create a namespace identity object. This is a namespace with no root directory and no parent. It can be used
        as a Namespace index object.

        :param Path output_path: The base path under which all namespaces and datatypes should be generated.
        :param LanguageContext lctx: The language context to use when building the namespace.
        :return: A namespace identity object.
        :rtype: Namespace
        """
        return cls("", Path(""), output_path, lctx)

    DefaultOutputStem = "_"

    def __init__(
        self,
        full_namespace: str,
        root_namespace_dir: Path,
        base_output_path: Path,
        language_context: LanguageContext,
        parent: Optional["Namespace"] = None,
    ):
        if full_namespace == "":
            if parent is not None:
                raise ValueError("Identity namespaces must not have a parent.")
        else:
            if parent is None:
                raise ValueError("Non-identity namespaces must have a parent.")
            if len(root_namespace_dir.name) == 0:
                raise ValueError("Root namespace directory must have a name.")

        target_language = language_context.get_target_language()
        self._parent = parent
        self._namespace_components, self._namespace_components_stropped = self.strop_namespace(
            full_namespace, language_context
        )
        if self._namespace_components[0] != root_namespace_dir.name:
            raise ValueError(f"Namespace {full_namespace} does not match root namespace directory {root_namespace_dir}")
        self._full_namespace = ".".join(self._namespace_components_stropped)
        self._output_folder = Path(base_output_path / Path(*self._namespace_components_stropped))
        output_stem = target_language.get_config_value(Language.WKCV_NAMESPACE_FILE_STEM, self.DefaultOutputStem)
        output_path = self._output_folder / Path(output_stem)
        self._base_output_path = base_output_path
        self._output_path = output_path.with_suffix(
            target_language.get_config_value(Language.WKCV_DEFINITION_FILE_EXTENSION)
        )
        self._source_folder = Path(root_namespace_dir / Path(*self._namespace_components[1:])).resolve(strict=False)
        self._short_name = self._namespace_components_stropped[-1]
        self._data_type_to_outputs: dict[pydsdl.CompositeType, Generatable] = {}
        self._nested_namespaces: dict[str, Namespace] = {}
        self._language_context = language_context

        if self._parent is not None:
            self._parent._nested_namespaces[self._namespace_components[0]] = self

    # +--[PROPERTIES]-----------------------------------------------------------------------------------------------+
    @property
    def output_folder(self) -> Path:
        """
        The folder where this namespace's output file and datatypes are generated.
        """
        return self._output_folder

    @property
    def output_path(self) -> Path:
        """
        Path to the namespaces output file.
        """
        return self._output_path

    @property
    def parent(self) -> Optional["Namespace"]:
        """
        The parent namespace of this namespace or None if this is a root namespace.
        """
        return self._parent

    @property
    def base_output_path(self) -> Path:
        """
        The folder under which artifacts are generated.
        """
        return self._base_output_path

    # +--[PUBLIC]--------------------------------------------------------------------------------------------------+
    def get_index_namespace(self) -> "Namespace":
        """
        The index namespace is a meta-namespace that is empty and has no data types. It contains
        the root output folder, a common language context, and all the namespaces in a tree of DSDL types. It is used to
        generate index files that reference all the generated files in the tree at once. Logically, it is the root of
        the tree and is always the parent of each root namespace. The taxonomy of namespaces is therefore ::

                                          ┌────────────────┐
                                          │  CompoundType  │
                                          │                │
                                          └────────────────┘
                                           ▲             ▲
                        ┌──────────────────┘             │
                        │                                │
                        │              ┌──────┐          │
                        │              │ Path │          │
                        │              │      │          │
                        │              └──────┘          │
                        │               ▲    ▲           │
                        │               │    │           │
                  ┌─────┴─────┐ ┌───────┴┐  ┌┴───────┐   │
                  │ Namespace │ │ Folder │  │  File  │   │
                  │           │ │        │  │        │   │
                  └───────────┘ └────────┘  └────────┘   │
                   ▲    ▲   ▲     ▲    ▲           ▲     │
                   │    │   │     │    └──────┐    │     │
                   │    │   │     │           │    │     │
                   │    │   └──── │ ─────┐    │    │     │
                   │    │         │      │    │    │     │
                   │    └─────┐   │      │    │    │     │
                   │          │   │      │    │    │     │
                ┌──┴──────┐ ┌─┴───┴──┐ ┌─┴────┴─┐ ┌┴─────┴────┐
                │  index  │ │  root  │ │ nested │ │ DSDL Type │
                │         │ │        │ │        │ │           │
                └─────────┘ └────────┘ └────────┘ └───────────┘

        :return: The index namespace.

        .. invisible-code-block: python

            from nunavut._namespace import Namespace
            from nunavut.lang import LanguageContext, LanguageContextBuilder
            from pathlib import Path

            lctx = (
                LanguageContextBuilder()
                    .set_target_language("c")
                    .create()
            )

            base_path = gen_paths.out_dir
            root_namespace_dir = base_path / Path("uavcan")
            root_namespace_dir.mkdir(exist_ok=True)
            nested_namespace_dir = root_namespace_dir / Path("node")
            nested_namespace_dir.mkdir(exist_ok=True)

        .. code-block:: python

            # This is the index namespace identity.
            index_ns = Namespace.Identity(base_path, lctx)
            ns = Namespace("uavcan", root_namespace_dir, base_path, lctx, index_ns)

            # This is a root namespace identity.
            assert ns.get_index_namespace() == index_ns

        """
        namespace = self
        while namespace.full_namespace != "":
            if namespace.parent is None:
                raise RuntimeError(f"Orphaned namespace {self.full_name}: Not in indexed namespace tree.")
            namespace = namespace.parent
        return namespace

    def get_language_context(self) -> LanguageContext:
        """
        The generated software language context the namespace is within.
        """
        return self._language_context

    def get_root_namespace(self, root_namespace_folder: Path) -> "Namespace":
        """
        Retrieves or creates a root namespace object from a root namespace folder. Only the folder name is used
        to determine the namespace name so the same object will be returned for different paths to a folder with
        the same name.

        .. invisible-code-block: python

            from nunavut._namespace import Namespace
            from nunavut.lang import LanguageContext, LanguageContextBuilder
            from pathlib import Path

            lctx = (

                LanguageContextBuilder()
                    .set_target_language("c")
                    .create()
            )
            base_path = gen_paths.out_dir

        .. code-block:: python

            index_ns = Namespace.Identity(base_path, lctx)
            uavcan_namespace_dir_0 = Path("path") / Path("to") / Path("uavcan")
            uavcan_namespace_dir_1 = Path("another") / Path("path") / Path("to") / Path("uavcan")

            assert (
                index_ns.get_root_namespace(uavcan_namespace_dir_0) ==
                index_ns.get_root_namespace(uavcan_namespace_dir_1)
            )

        :param Path root_namespace_folder: The folder that represents the root namespace.
        :return: The root namespace object.
        """
        index = self.get_index_namespace()
        try:
            return index._nested_namespaces[root_namespace_folder.name]  # pylint: disable=protected-access
        except KeyError:
            pass
        namespace = Namespace(
            root_namespace_folder.name, root_namespace_folder, self._base_output_path, self._language_context, index
        )
        return namespace

    def get_nested_namespaces(self) -> Iterator["Namespace"]:
        """
        Get an iterator over all the nested namespaces within this namespace.
        This is a shallow iterator that only provides directly nested namespaces.
        """
        return iter(self._nested_namespaces.values())

    def get_nested_types(self) -> ItemsView[pydsdl.CompositeType, Generatable]:
        """
        Get a view of a tuple relating datatypes in this namespace to the path for the
        type's generated output. This is a shallow view including only the types
        directly within this namespace.
        """
        return self._data_type_to_outputs.items()

    def get_all_datatypes(self) -> Generator[Tuple[pydsdl.CompositeType, Generatable], None, None]:
        """
        Generates tuples relating datatypes at and below this namespace to the path
        for each type's generated output.
        """
        yield from self._recursive_data_type_generator(self)

    def get_all_namespaces(self) -> Generator[Tuple["Namespace", Path], None, None]:
        """
        Generates tuples relating nested namespaces at and below this namespace to the path
        for each namespace's generated output.
        """
        yield from self._recursive_namespace_generator(self)

    def get_all_types(self) -> Generator[Tuple[pydsdl.Any, Generatable], None, None]:
        """
        Generates tuples relating datatypes and nested namespaces at and below this
        namespace to the path for each type's generated output.
        """
        yield from self._recursive_data_type_and_namespace_generator(self)

    def find_output_path_for_type(self, compound_type: Union["Namespace", pydsdl.CompositeType]) -> Generatable:
        """
        Searches the entire namespace tree to find a mapping of the type to an
        output file path.

        :param pydsdl.CompositeType compound_type: A Namespace or pydsdl.CompositeType to find the output pathfor.
        :return: The path where a file will be generated for a given type.
        :raises KeyError: If the type was not found in this namespace tree.
        """
        if isinstance(compound_type, Namespace):
            return compound_type.output_path
        else:
            # pylint: disable=protected-access
            root_namespace = self.get_index_namespace().get_root_namespace(compound_type.source_file_path_to_root)
            return root_namespace._bfs_search_for_output_path(compound_type, set())  # pylint: disable=protected-access

    # +--[DUCK TYPING: pydsdl.CompositeType]-----------------------------------------------------------------------+
    @property
    def short_name(self) -> str:
        """
        See :py:attr:`pydsdl.CompositeType.short_name`
        """
        return self._short_name

    @property
    def full_name(self) -> str:
        """
        See :py:attr:`pydsdl.CompositeType.full_name`
        """
        return self._full_namespace

    @property
    def full_namespace(self) -> str:
        """
        See :py:attr:`pydsdl.CompositeType.full_namespace`
        """
        return self._full_namespace

    @property
    def namespace_components(self) -> list[str]:
        """
        See :py:attr:`pydsdl.CompositeType.namespace_components`
        """
        return self._namespace_components

    @property
    def source_file_path(self) -> Path:
        """
        See :py:attr:`pydsdl.CompositeType.source_file_path`
        """
        return self._source_folder

    @property
    def data_types(self) -> KeysView[pydsdl.CompositeType]:
        """
        See :py:attr:`pydsdl.CompositeType.data_types`
        """
        return self._data_type_to_outputs.keys()

    @property
    def attributes(self) -> list[pydsdl.CompositeType]:
        """
        See :py:attr:`pydsdl.CompositeType.attributes`
        """
        return []

    # +--[PYTHON DATA MODEL]--------------------------------------------------------------------------------------+

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Namespace):
            return self._full_namespace == other._full_namespace
        else:
            return False

    def __str__(self) -> str:
        return self.full_name

    def __hash__(self) -> int:
        return hash(self._full_namespace)

    # +--[PRIVATE]------------------------------------------------------------------------------------------------+

    def _add_data_type(
        self, dsdl_type: pydsdl.CompositeType, input_types: list[pydsdl.CompositeType], extension: Optional[str]
    ) -> Generatable:
        """
        Add a datatype to this namespace.

        :param pydsdl.CompositeType dsdl_type: The datatype to add.
        :param str extension: The file extension to use for the generated file. If None, the
                                extension will be determined by the target language.
        :return: A path to the file this type will be generated in.
        """

        language = self._language_context.get_target_language()
        if extension is None:
            extension = language.get_config_value(Language.WKCV_DEFINITION_FILE_EXTENSION)
        output_file = Path(self._base_output_path) / IncludeGenerator.make_path(dsdl_type, language, extension)
        output_generatable = Generatable.wrap(output_file, dsdl_type, input_types)
        self._data_type_to_outputs[dsdl_type] = output_generatable
        return output_generatable

    def _bfs_search_for_output_path(self, data_type: pydsdl.CompositeType, skip_namespace: set["Namespace"]) -> Path:
        search_queue: Deque[Namespace] = collections.deque()
        search_queue.appendleft(self)
        while len(search_queue) > 0:
            namespace = search_queue.pop()
            if namespace not in skip_namespace:
                try:
                    return namespace._data_type_to_outputs[data_type]  # pylint: disable=protected-access
                except KeyError:
                    pass
            for nested_namespace in namespace._nested_namespaces.values():  # pylint: disable=protected-access
                search_queue.appendleft(nested_namespace)

        raise KeyError(data_type)

    @classmethod
    def _recursive_data_type_generator(
        cls, namespace: "Namespace"
    ) -> Generator[Tuple[pydsdl.CompositeType, Path], None, None]:
        for data_type, output_path in namespace.get_nested_types():
            yield (data_type, output_path)

        for nested_namespace in namespace.get_nested_namespaces():
            yield from cls._recursive_data_type_generator(nested_namespace)

    @classmethod
    def _recursive_namespace_generator(cls, namespace: "Namespace") -> Generator[Tuple["Namespace", Path], None, None]:
        yield (namespace, namespace.output_path)

        for nested_namespace in namespace.get_nested_namespaces():
            yield from cls._recursive_namespace_generator(nested_namespace)

    @classmethod
    def _recursive_data_type_and_namespace_generator(
        cls, namespace: "Namespace"
    ) -> Generator[Tuple[pydsdl.Any, Path], None, None]:
        yield (namespace, namespace.output_path)

        for data_type, output_path in namespace.get_nested_types():
            yield (data_type, output_path)

        for nested_namespace in namespace.get_nested_namespaces():
            yield from cls._recursive_data_type_and_namespace_generator(nested_namespace)


# +---------------------------------------------------------------------------+


def build_namespace_tree(
    types: list[pydsdl.CompositeType],
    root_namespace_dir: Union[str, Path],
    output_dir: Union[str, Path],
    language_context: LanguageContext,
) -> Namespace:
    """
    Generates a :class:`nunavut.Namespace` tree.

    .. note::

        Deprecated. Use :method:`Namespace.add_types` instead. build_namespace_tree creates a new a :class:`Namespace`
        index internally which may lead to unexpected behavior if calling this method multiple times. Furthermore, it
        cannot associate output files with their dependent types and is ambiguous about the root namespace directory.

    Given a list of pydsdl types, this method returns a root :class:`nunavut.Namespace`.
    The root :class:`nunavut.Namespace` is the top of a tree where each node contains
    references to nested :class:`nunavut.Namespace` and to any :code:`pydsdl.CompositeType`
    instances contained within the namespace.

    :param list types: A list of pydsdl types.
    :param str | Path root_namespace_dir: The root namespace directory. This is the directory that contains the
            namespaces's datatypes and nested namespaces.

        .. note::
            Root namespace directories are determined by the source file path of individual types so it is possible
            to pass in a list of types that are not available in the returned Namespace. Only types that are within
            this root namespace directory will be included in the returned Namespace.

    :param str | Path output_dir: The base directory under which all generated files will be created.
    :param nunavut.LanguageContext language_context: The language context to use when building
            :class:`nunavut.Namespace` objects.
    :return: The root :class:`nunavut.Namespace`.
    :rtype: nunavut.Namespace

    """

    index = Namespace.Identity(Path(output_dir), language_context)
    Namespace.add_types(index, [(dsdl_type, []) for dsdl_type in types])
    return index.get_root_namespace(Path(root_namespace_dir))


# +---------------------------------------------------------------------------+
