# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT

import enum
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Tuple, Set, Union

from pydsdl.visitors import DsdlFile, NamespaceVisitor


class DefaultFilterRule(enum.Enum):
    """
    Rule to apply for types that do not match any filter rule.
    """

    EXCLUDE = "exclude"
    INCLUDE = "include"


class FilterOrder(enum.Enum):
    """
    The order of the filter rules. For example, INCLUDE_FIRST means that the include rules are applied first and
    filter processing stops for that type as soon as an include rule is matched regardless of any other rules.
    EXCLUDE_FIRST means that the exclude rules are applied first and filter processing stops for that type as
    soon as an exclude rule is matched regardless of any other rules.
    """

    INCLUDE_FIRST = "include-first"
    EXCLUDE_FIRST = "exclude-first"


class FilterType(enum.Enum):
    """
    What part of a DSDL-file-defined type to apply the filter to.
    """

    FULL_NAME_AND_VERSION = "full-name-and-version"
    SHORT_NAME_AND_VERSION = "short-name-and-version"
    FULL_NAME = "full-name"
    SHORT_NAME = "short-name"
    FILE_PATH = "file-path"
    ROOT_NAMESPACE = "root-namespace"
    FULL_NAMESPACE = "full-namespace"
    VERSION = "version"


class FilterStatus(enum.Enum):
    """
    The status of a filter rule.
    """

    STRONGLY_INCLUDED = "strongly-included"
    WEAKLY_INCLUDED = "weakly-included"
    STRONGLY_EXCLUDED = "strongly-excluded"
    WEAKLY_EXCLUDED = "weakly-excluded"


TypeFilter = Union[str, re.Pattern[str], Tuple[FilterType, Union[str, re.Pattern[str]]]]
"""
The type of a filter rule. This can be an un-compiled regular expression (string), pre-compiled regular expression
pattern, or a tuple of a FilterType and an un-compiled regular expression or pre-compiled regular expression pattern.
Filters without types are given a default type when normalized.
"""

NormalizedTypeFilter = Tuple[FilterType, re.Pattern[str]]
"""
A TypeFilter that is normalized to a tuple of a FilterType and a pre-compiled regular expression pattern.
"""

TypeFilters = NamedTuple(
    "TypeFilters",
    [
        ("default_rule", DefaultFilterRule),
        ("whitelist", Optional[List[TypeFilter]]),
        ("blacklist", Optional[List[TypeFilter]]),
        ("filter_order", Optional[FilterOrder]),
    ],
)
"""
A set of filter rules to use when processing DSDL namespaces.
"""


class DefinitionFilterEngine:
    """
    Engine that processes filter rules given DsdlDefinitions.
    """

    DEFAULT_FILTER_TYPE = FilterType.FULL_NAME_AND_VERSION
    DEFAULT_FILTER_ORDER = FilterOrder.INCLUDE_FIRST
    DEFAULT_FILTER_RULE = DefaultFilterRule.INCLUDE

    @classmethod
    def _normalize_filter(
        cls, filter_rule: TypeFilter, default_type: Optional[FilterType] = None
    ) -> NormalizedTypeFilter:
        if not isinstance(filter_rule, tuple) and default_type is None:
            raise ValueError("Cannot normalize a pattern without a default filter type")

        if isinstance(filter_rule, tuple):
            if len(filter_rule) != 2 or not isinstance(filter_rule[0], FilterType) or isinstance(filter_rule[1], tuple):
                raise ValueError("Invalid filter type")
            filter_type, pattern = cls._normalize_filter(filter_rule[1], filter_rule[0])
        elif isinstance(filter_rule, str):
            filter_type = default_type  # type: ignore
            pattern = re.compile(filter_rule)
        elif isinstance(filter_rule, re.Pattern):
            filter_type = default_type  # type: ignore
            pattern = filter_rule
        else:
            raise ValueError("Invalid filter format")
        return filter_type, pattern

    @classmethod
    def create(
        cls,
        filters: Optional[TypeFilters] = None,
        **kwargs: Any,
    ) -> "DefinitionFilterEngine":
        """
        Create a new filter engine with the given rules. If no arguments are provided the resulting engine
        will simply apply the default rule on select.

        :param filters: The filters specification.
        :param kwargs: Additional arguments to pass to the filter engine.
        :return: A new filter engine.
        """
        if filters is not None:
            kwargs["whitelist"] = (
                [cls._normalize_filter(rule, cls.DEFAULT_FILTER_TYPE) for rule in filters.whitelist]
                if filters.whitelist is not None
                else []
            )
            kwargs["blacklist"] = (
                [cls._normalize_filter(rule, cls.DEFAULT_FILTER_TYPE) for rule in filters.blacklist]
                if filters.blacklist is not None
                else []
            )
            kwargs["filter_order"] = (
                filters.filter_order if filters.filter_order is not None else cls.DEFAULT_FILTER_ORDER
            )
            kwargs["default_rule"] = filters.default_rule
        else:
            kwargs["whitelist"] = []
            kwargs["blacklist"] = []

        return cls(**kwargs)

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        whitelist: List[NormalizedTypeFilter],
        blacklist: List[NormalizedTypeFilter],
        filter_order: FilterOrder = DEFAULT_FILTER_ORDER,
        default_rule: DefaultFilterRule = DEFAULT_FILTER_RULE,
    ):
        self._filter_order = filter_order
        self._default_rule = default_rule
        self._whitelist = whitelist
        self._blacklist = blacklist

    @property
    def filter_order(self) -> FilterOrder:
        """
        The order of the filter rules.
        """
        return self._filter_order

    @property
    def default_rule(self) -> DefaultFilterRule:
        """
        The default rule to apply for types that do not match any filter rule.
        """
        return self._default_rule

    def select_all(self, *dsdl_defs: DsdlFile) -> None:
        """
        Updates the filter status of the given DSDL definitions.
        :param dsdl_defs: The DSDL definitions to select.
        """
        for dsdl_def in dsdl_defs:
            dsdl_def.filter_status = self._select_internal(dsdl_def)

    def select(self, dsdl_def: DsdlFile) -> bool:
        """
        Filter the type based on the filter rules.
        :param dsdl_def: The dsdl defintion to filter.
        :return: True if the type should be included, False if it should be excluded.
        """
        status = self._select_internal(dsdl_def)
        return status in (FilterStatus.STRONGLY_INCLUDED, FilterStatus.WEAKLY_INCLUDED)

    # +---[PRIVATE]---------------------------------------------------------------------------------------------------+
    def _select_internal(self, dsdl_def: DsdlFile) -> FilterStatus:
        """
        Filter the type based on the filter rules.
        :param dsdl_def: The dsdl defintion to filter.
        :return: FilterStatus.STRONGLY_INCLUDED if the type should be included because of a whitelist rule,
        FilterStatus.STRONGLY_EXCLUDED if the type should be excluded because of a blacklist rule,
        FilterStatus.WEAKLY_INCLUDED if the type should be included because of the default rule, and
        FilterStatus.WEAKLY_EXCLUDED if the type should be excluded because of the default rule.
        """
        if self._filter_order == FilterOrder.INCLUDE_FIRST:
            if self._include(dsdl_def):
                return FilterStatus.STRONGLY_INCLUDED
            if self._exclude(dsdl_def):
                return FilterStatus.STRONGLY_EXCLUDED
        else:
            if self._exclude(dsdl_def):
                return FilterStatus.STRONGLY_EXCLUDED
            if self._include(dsdl_def):
                return FilterStatus.STRONGLY_INCLUDED
        return (
            FilterStatus.WEAKLY_INCLUDED
            if self._default_rule == DefaultFilterRule.INCLUDE
            else FilterStatus.WEAKLY_EXCLUDED
        )

    def _include(self, dsdl_type: DsdlFile) -> bool:
        for rule in self._whitelist:
            if self._match(rule, dsdl_type):
                return True
        return False

    def _exclude(self, dsdl_type: DsdlFile) -> bool:
        for rule in self._blacklist:
            if self._match(rule, dsdl_type):
                return True
        return False

    # pylint: disable=too-many-return-statements
    def _match(self, rule: NormalizedTypeFilter, dsdl_type: DsdlFile) -> bool:
        if rule[0] == FilterType.FULL_NAME_AND_VERSION:
            return self._match_1(rule[1], f"{dsdl_type.full_name}.{dsdl_type.version.major}.{dsdl_type.version.minor}")
        if rule[0] == FilterType.SHORT_NAME_AND_VERSION:
            return self._match_1(rule[1], f"{dsdl_type.short_name}.{dsdl_type.version.major}.{dsdl_type.version.minor}")
        if rule[0] == FilterType.FULL_NAME:
            return self._match_1(rule[1], dsdl_type.full_name)
        if rule[0] == FilterType.SHORT_NAME:
            return self._match_1(rule[1], dsdl_type.short_name)
        if rule[0] == FilterType.FILE_PATH:
            return self._match_1(rule[1], str(dsdl_type.file_path))
        if rule[0] == FilterType.ROOT_NAMESPACE:
            return self._match_1(rule[1], dsdl_type.root_namespace)
        if rule[0] == FilterType.FULL_NAMESPACE:
            return self._match_1(rule[1], dsdl_type.full_namespace)
        if rule[0] == FilterType.VERSION:
            return self._match_1(rule[1], f"{dsdl_type.version.major}.{dsdl_type.version.minor}")
        return False

    def _match_1(self, rule: re.Pattern[str], text: str) -> bool:
        return rule.search(text) is not None


class FilteredNamespaceVisitor(NamespaceVisitor):
    """
    A NamespaceVisitor that filters the types it visits based on a DefinitionFilterEngine.
    """

    def __init__(
        self,
        engine: DefinitionFilterEngine,
        found_types: Set[DsdlFile],
        target_file_found_callback: Callable[[DsdlFile], None],
        types_discovered_callback: Callable[[DsdlFile], None],
    ):
        super().__init__()
        self._engine = engine
        self._dependent_types: Dict[Path, Set[DsdlFile]] = {}
        self._found_types: Set[DsdlFile] = found_types
        self._target_file_found_callback = target_file_found_callback
        self._types_discovered_callback = types_discovered_callback

    def get_dependent_types(self) -> Dict[Path, Set[DsdlFile]]:
        """
        Get the dependent types that were discovered during the visit.
        :return: The dependent types.
        """
        return self._dependent_types

    def get_found_types(self) -> Set[DsdlFile]:
        """
        Get the types that were found during the visit.
        :return: The found types.
        """
        return self._found_types

    # +-----------------------------------------------------------------------+
    # | NamespaceVisitor :: TEMPLATE METHODS                                  |
    # +-----------------------------------------------------------------------+
    def on_discover_target_file(self, target_dsdl_file: DsdlFile) -> bool:
        if self._engine.select(target_dsdl_file):
            self._found_types.add(target_dsdl_file)
            self._target_file_found_callback(target_dsdl_file)
            return True
        return False

    def on_discover_lookup_dependent_file(self, target_dsdl_file: DsdlFile, lookup_file: DsdlFile) -> None:
        # TODO. raise DependentFileError if lookup_file is strongly excluded
        if lookup_file not in self._found_types:
            try:
                dependent_types = self._dependent_types[lookup_file.root_namespace_path]
            except KeyError:
                dependent_types = set()
                self._dependent_types[lookup_file.root_namespace_path] = dependent_types
            if lookup_file not in dependent_types:
                self._types_discovered_callback(lookup_file)
                dependent_types.add(lookup_file)


# +---[UNIT TESTS]---------------------------------------------------------------------------------------------------+


def _unittest_filter_engine_create() -> None:
    # pylint: disable=import-outside-toplevel
    from unittest.mock import MagicMock

    type_a = MagicMock(spec=DsdlFile)

    default_engine = DefinitionFilterEngine.create()
    assert default_engine.default_rule == DefinitionFilterEngine.DEFAULT_FILTER_RULE
    assert default_engine.filter_order == DefinitionFilterEngine.DEFAULT_FILTER_ORDER

    assert default_engine.select(type_a) == (DefinitionFilterEngine.DEFAULT_FILTER_RULE == DefaultFilterRule.INCLUDE)

    assert (
        DefinitionFilterEngine.create(TypeFilters(DefaultFilterRule.EXCLUDE, None, None, None)).select(type_a) is False
    )
    assert (
        DefinitionFilterEngine.create(TypeFilters(DefaultFilterRule.INCLUDE, None, None, None)).select(type_a) is True
    )
