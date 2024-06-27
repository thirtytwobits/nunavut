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
from pathlib import Path, PurePath
from typing import Deque, Generator, ItemsView, Iterable, Iterator, KeysView, Optional, Tuple, Union

import pydsdl

from .lang import Language, LanguageContext
from .lang._common import IncludeGenerator

# +---------------------------------------------------------------------------+


class Namespace(pydsdl.Any):
    """
    K-ary tree (where K is the largest set of data types in a single dsdl namespace) where
    the nodes represent dsdl namespaces and the children are the datatypes and other nested
    namespaces (with datatypes always being leaf nodes). This structure extends :code:`pydsdl.Any`
    and is a :code:`pydsdl.pydsdl.CompositeType` via duck typing.

    :param str full_namespace:  The full, dot-separated name of the namepace. This is expected to be
                                a unique identifier.
    :param Path root_namespace_dir: The directory representing the dsdl namespace and containing the
                                namespaces's datatypes and nested namespaces.
    :param PurePath base_output_path: The base path under which all namespaces and datatypes should
                                be generated.
    :param LanguageContext language_context: The generated software language context the namespace is within.
    """

    DefaultOutputStem = "_"

    def __init__(
        self,
        full_namespace: str,
        root_namespace_dir: Path,
        base_output_path: PurePath,
        language_context: LanguageContext,
    ):
        target_language = language_context.get_target_language()
        self._parent: Optional[Namespace] = None
        self._namespace_components: list[str] = []
        self._namespace_components_stropped: list[str] = []
        for component in full_namespace.split("."):
            self._namespace_components_stropped.append(language_context.filter_id_for_target(component, "path"))
            self._namespace_components.append(component)
        self._full_namespace = ".".join(self._namespace_components_stropped)
        self._output_folder = Path(base_output_path / PurePath(*self._namespace_components_stropped))
        output_stem = target_language.get_config_value(Language.WKCV_NAMESPACE_FILE_STEM, self.DefaultOutputStem)
        output_path = self._output_folder / PurePath(output_stem)
        self._base_output_path = base_output_path
        self._output_path = output_path.with_suffix(
            target_language.get_config_value(Language.WKCV_DEFINITION_FILE_EXTENSION)
        )
        self._source_folder = Path(root_namespace_dir / PurePath(*self._namespace_components[1:])).resolve()
        if not self._source_folder.exists():
            # to make Python > 3.5 behave the same as Python 3.5
            raise FileNotFoundError(self._source_folder)
        self._short_name = self._namespace_components_stropped[-1]
        self._data_type_to_outputs: dict[pydsdl.CompositeType, Path] = dict()
        self._nested_namespaces: set[Namespace] = set()
        self._language_context = language_context

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

    def get_support_output_folder(self) -> PurePath:
        """
        The folder under which support artifacts are generated.
        """
        return self._base_output_path

    def get_language_context(self) -> LanguageContext:
        """
        The generated software language context the namespace is within.
        """
        return self._language_context

    def get_root_namespace(self) -> "Namespace":
        """
        Traverses the namespace tree up to the root and returns the root node.

        :return: The root namespace object.
        """
        namespace = self
        while namespace.parent is not None:
            namespace = namespace.parent
        return namespace

    def get_nested_namespaces(self) -> Iterator["Namespace"]:
        """
        Get an iterator over all the nested namespaces within this namespace.
        This is a shallow iterator that only provides directly nested namespaces.
        """
        return iter(self._nested_namespaces)

    def get_nested_types(self) -> ItemsView[pydsdl.CompositeType, Path]:
        """
        Get a view of a tuple relating datatypes in this namespace to the path for the
        type's generated output. This is a shallow view including only the types
        directly within this namespace.
        """
        return self._data_type_to_outputs.items()

    def get_all_datatypes(self) -> Generator[Tuple[pydsdl.CompositeType, Path], None, None]:
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

    def get_all_types(self) -> Generator[Tuple[pydsdl.Any, Path], None, None]:
        """
        Generates tuples relating datatypes and nested namespaces at and below this
        namespace to the path for each type's generated output.
        """
        yield from self._recursive_data_type_and_namespace_generator(self)

    def find_output_path_for_type(self, any_type: pydsdl.Any) -> Path:
        """
        Searches the entire namespace tree to find a mapping of the type to an
        output file path.

        :param Any any_type: Either a Namespace or pydsdl.CompositeType to find the
                             output path for.
        :return: The path where a file will be generated for a given type.
        :raises KeyError: If the type was not found in this namespace tree.
        """
        if isinstance(any_type, Namespace):
            return any_type.output_path
        else:
            try:
                return self._data_type_to_outputs[any_type]
            except KeyError:
                pass

            # We could get fancier but this should do
            return self.get_root_namespace()._bfs_search_for_output_path(  # pylint: disable=protected-access
                any_type, set([self])
            )

    def add_nested_namespace(self, nested: "Namespace") -> bool:
        """
        Add a nested namespace to this namespace.

        :param Namespace nested: The namespace to add.
        :return: True if the namespace was added, False if it was already present.

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
            ns = Namespace("uavcan", root_namespace_dir, base_path, lctx)
            nested_ns = Namespace("uavcan.node", root_namespace_dir, base_path, lctx)

            # Add a nested namespace
            assert ns.add_nested_namespace(nested_ns)

            # Add the same nested namespace again, should return False.
            assert not ns.add_nested_namespace(nested_ns)

        """
        if nested in self._nested_namespaces:
            return False
        self._nested_namespaces.add(nested)
        nested._parent = self  # pylint: disable=protected-access
        return True

    def add_data_type(self, dsdl_type: pydsdl.CompositeType, extension: Optional[str] = None) -> Path:
        """
        Add a datatype to this namespace.

        :param pydsdl.CompositeType dsdl_type: The datatype to add.
        :param str extension: The file extension to use for the generated file. If None, the
                                extension will be determined by the target language.
        :return: A path to the file this type will be generated in.
        """

        language = self._language_context.get_target_language()
        if extension is None:
            extension = language.get_config_value(
                Language.WKCV_DEFINITION_FILE_EXTENSION
            )
        output_file = Path(self._base_output_path) / IncludeGenerator.make_path(
            dsdl_type, language, extension
        )
        self._data_type_to_outputs[dsdl_type] = output_file
        return output_file

    # +-----------------------------------------------------------------------+
    # | DUCK TYPING: pydsdl.CompositeType
    # +-----------------------------------------------------------------------+
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

    # +-----------------------------------------------------------------------+
    # | PYTHON DATA MODEL
    # +-----------------------------------------------------------------------+

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Namespace):
            return self._full_namespace == other._full_namespace
        else:
            return False

    def __str__(self) -> str:
        return self.full_name

    def __hash__(self) -> int:
        return hash(self._full_namespace)

    # +-----------------------------------------------------------------------+
    # | PRIVATE
    # +-----------------------------------------------------------------------+

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
            for nested_namespace in namespace._nested_namespaces:  # pylint: disable=protected-access
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


class NamespaceFactory:
    """
    Read-through cache and factory for :class:`Namespace` objects.

    :param LanguageContext lctx: The language context to use when building
            :class:`nunavut.Namespace` objects.
    :param PurePath base_path: The base directory under which all generated files will be created.
    :param Path root_namespace_dir: The path representing the dsdl namespace and containing the
            namespaces's datatypes and nested namespaces.

    .. invisible-code-block: python

        from nunavut._namespace import Namespace, NamespaceFactory
        from nunavut.lang import LanguageContext, LanguageContextBuilder
        from pathlib import Path

        lctx = (
            LanguageContextBuilder()
                .set_target_language("c")
                .create()
        )
        base_path = gen_paths.out_dir
        root_namespace_dir = gen_paths.out_dir / Path("uavcan")
        root_namespace_dir.mkdir(exist_ok=True)
        nsf = NamespaceFactory(lctx, base_path, root_namespace_dir)

        assert nsf.get_root_namespace() is not None
        uavcan_ns = nsf.get_or_make_namespace("uavcan")
        assert uavcan_ns is not None
        assert uavcan_ns.short_name == "uavcan"

    """

    def __init__(self, lctx: LanguageContext, base_path: PurePath, root_namespace_dir: Path):
        self._lctx = lctx
        self._base_path = base_path
        self._namespaces: dict[str, Namespace] = dict()
        self._root_namespace_dir = root_namespace_dir

    def get_root_namespace(self) -> Namespace:
        """
        Namespace object for the root namespace.
        """
        try:
            return next(iter(self._namespaces.values())).get_root_namespace()
        except StopIteration:
            pass
        return self.get_empty_namespace()

    def get_empty_namespace(self) -> Namespace:
        """
        Namespace object for the empty namespace.
        """
        return self.get_or_make_namespace("")

    def add_types(self, types: Iterable[pydsdl.CompositeType]) -> Namespace:
        """
        Adds dsdl types to a namespace tree building new nodes as needed.

        :param list types: A list of pydsdl types.
        :return: The root :class:`nunavut.Namespace` as returned from :meth:`NamespaceFactory.get_root_namespace`
            but after new nodes have been added.
        """
        for dsdl_type in types:
            # For each type we form a path with the output_dir as the base; the intermediate
            # folders named for the type's namespaces; and a file name that includes the type's
            # short name, major version, minor version, and the extension argument as a suffix.
            # Python's pathlib adapts the provided folder and file names to the platform
            # this script is running on.
            # We also, lazily, generate Namespace nodes as we encounter new namespaces for the
            # first time.

            namespace = self.get_or_make_namespace(dsdl_type.full_namespace)
            namespace.add_data_type(dsdl_type)

        return self.get_root_namespace()

    def get_or_make_namespace(self, full_namespace: str) -> Namespace:
        """
        Read-through cache and factory for :class:`Namespace` objects.

        :param str full_namespace: The full, dot-separated name of the namepace.
        :return: The :class:`Namespace` object.

        """
        try:
            return self._namespaces[full_namespace]
        except KeyError:
            pass

        namespace = ancestor = Namespace(full_namespace, self._root_namespace_dir, self._base_path, self._lctx)

        self._namespaces[full_namespace] = namespace

        while len(ancestor.namespace_components) > 1:
            parent_ns = ".".join(ancestor.namespace_components[:-1])
            try:
                self._namespaces[parent_ns].add_nested_namespace(ancestor)
                break
            except KeyError:
                pass

            parent = Namespace(parent_ns, self._root_namespace_dir, self._base_path, self._lctx)
            parent.add_nested_namespace(ancestor)
            self._namespaces[parent_ns] = parent
            ancestor = parent

        return namespace


def build_namespace_tree(
    types: list[pydsdl.CompositeType],
    root_namespace_dir: Union[str, Path],
    output_dir: Union[str, Path],
    language_context: LanguageContext,
) -> Namespace:
    """
    Generates a :class:`nunavut.Namespace` tree.

    .. note::

        Deprecated. Use the :method:`NamespaceFactory.add_types` method of a :class:`NamespaceFactory`
        object instead. This method creates and destroys a :class:`NamespaceFactory` internally which is inefficient.

    Given a list of pydsdl types, this method returns a root :class:`nunavut.Namespace`.
    The root :class:`nunavut.Namespace` is the top of a tree where each node contains
    references to nested :class:`nunavut.Namespace` and to any :code:`pydsdl.CompositeType`
    instances contained within the namespace.

    :param list types: A list of pydsdl types.
    :param str | Path root_namespace_dir: A path to the folder which is the root namespace.
    :param str | Path output_dir: The base directory under which all generated files will be created.
    :param nunavut.LanguageContext language_context: The language context to use when building
            :class:`nunavut.Namespace` objects.
    :return: The root :class:`nunavut.Namespace`.
    :rtype: nunavut.Namespace

    """

    nsf = NamespaceFactory(language_context, PurePath(output_dir), Path(root_namespace_dir))

    for dsdl_type in types:
        # For each type we form a path with the output_dir as the base; the intermediate
        # folders named for the type's namespaces; and a file name that includes the type's
        # short name, major version, minor version, and the extension argument as a suffix.
        # Python's pathlib adapts the provided folder and file names to the platform
        # this script is running on.
        # We also, lazily, generate Namespace nodes as we encounter new namespaces for the
        # first time.

        namespace = nsf.get_or_make_namespace(dsdl_type.full_namespace)
        namespace.add_data_type(  # pylint: disable=protected-access
            dsdl_type, language_context.get_target_language().get_config_value(Language.WKCV_DEFINITION_FILE_EXTENSION)
        )

    return nsf.get_root_namespace()


# +---------------------------------------------------------------------------+
