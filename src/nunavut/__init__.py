#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Code generator built on top of pydsdl.

Nunavut uses pydsdl to generate text files using templates. While these
text files are often source code this module could also be used to generate
documentation or data interchange formats like JSON or XML.

The input to the nunavut library is a list of templates and a list of
``pydsdl.pydsdl.CompositeType`` objects. Typical use of this library is simply
invoking the ``nunavut.generate_all`` method.

"""
import sys as _sys

from ._generators import AbstractGenerator
from ._generators import generate_types
from ._generators import generate_all
from ._namespace import Namespace
from ._namespace import NamespaceFactory
from ._utilities import TEMPLATE_SUFFIX
from ._utilities import DefaultValue
from ._utilities import ResourceType
from ._utilities import YesNoDefault
from ._version import __author__
from ._version import __copyright__
from ._version import __email__
from ._version import __license__
from ._version import __version__
from .jinja import CodeGenerator
from .jinja import DSDLCodeGenerator
from .jinja import SupportGenerator
from .lang import Language
from .lang import LanguageContext
from .lang import LanguageContextBuilder
from .lang import UnsupportedLanguageError
from .lang._config import LanguageConfig

if _sys.version_info[:2] < (3, 8):  # pragma: no cover
    print("A newer version of Python is required", file=_sys.stderr)
    _sys.exit(1)

__version_info__ = tuple(map(int, __version__.split(".")[:3]))

__all__ = [
    "AbstractGenerator",
    "CodeGenerator",
    "DefaultValue",
    "DSDLCodeGenerator",
    "generate_all",
    "generate_types",
    "Language",
    "LanguageConfig",
    "LanguageContext",
    "LanguageContextBuilder",
    "Namespace",
    "NamespaceFactory",
    "ResourceType",
    "SupportGenerator",
    "TEMPLATE_SUFFIX",
    "UnsupportedLanguageError",
    "YesNoDefault",
    "__author__",
    "__copyright__",
    "__email__",
    "__license__",
    "__version__",
    "__version_info__",
]
