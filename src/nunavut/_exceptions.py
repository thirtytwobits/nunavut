#
# Copyright (C) OpenCyphal Development Team  <opencyphal.org>
# Copyright Amazon.com Inc. or its affiliates.
# SPDX-License-Identifier: MIT
#
"""
Exception types thrown by the core library.

"""

import typing
from pathlib import Path
import urllib.parse


class BackendError(Exception):
    """
    This is the root exception type for all custom exceptions defined in the library.
    This type itself is not expected to be particularly useful to the library user;
    please refer to the direct descendants instead.

    (yes, this is patterned on pydsdl's FrontendError and shamelessly copied)
    """

    def __init__(self, text: str, path: typing.Optional[Path] = None, line: typing.Optional[int] = None):
        Exception.__init__(self, text)
        self._path = path
        self._line = line

    def set_error_location_if_unknown(
        self, path: typing.Optional[Path] = None, line: typing.Optional[int] = None
    ) -> None:
        """
        Entries that are already known will be left unchanged.
        This is useful when propagating exceptions through recursive instances,
        e.g., when processing nested definitions.
        """
        if not self._path and path:
            self._path = path

        if not self._line and line:
            self._line = line

    @property
    def path(self) -> typing.Optional[Path]:
        """Source file path where the error has occurred, if known."""
        return self._path

    @property
    def line(self) -> typing.Optional[int]:
        """
        Source file line number (first line numbered 1) where the error has occurred, if known.
        The path is always known if the line number is set.
        """
        return self._line

    @property
    def text(self) -> str:
        """
        The text of the exception
        """
        return Exception.__str__(self)

    def __str__(self) -> str:
        """
        Nicely formats an error string in the typical error format ``[file:[line:]]description``.
        Example::

            uavcan/internet/udp/500.HandleIncomingPacket.1.0.dsdl:33: Error such and such
        """
        if self.path and self.line:
            return f"{self.path.as_posix()}:{self.line}: {self.text}"

        if self.path:
            return f"{self.path.as_posix()}: {self.text}"

        return self.text

    def __repr__(self) -> str:
        return self.__class__.__name__ + ": " + repr(self.__str__())


class InternalError(BackendError):
    """
    This exception is used to report internal errors in the front end itself that prevented it from
    processing the definitions. Every occurrence should be reported to the developers.
    """

    def __init__(
        self,
        text: typing.Optional[str] = None,
        path: typing.Optional[Path] = None,
        line: typing.Optional[int] = None,
        culprit: typing.Optional[Exception] = None,
    ):
        if culprit is not None:
            report_text = (
                "PLEASE REPORT AT https://github.com/OpenCyphal/nunavut/issues/new?title="
                + urllib.parse.quote(repr(culprit))
            )
            if text:
                text = text + " " + report_text
            else:
                text = report_text

        if not text:
            text = ""

        super().__init__(text=text, path=path, line=line)
