#
# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Copyright (C) 2018-2019  OpenCyphal Development Team  <opencyphal.org>
# This software is distributed under the terms of the MIT License.
#
import itertools
import json
from pathlib import Path
from typing import Iterable, Tuple

from pydsdl import CompositeType, read_namespace

from nunavut import LanguageContextBuilder, NamespaceContext
from nunavut.jinja import DSDLCodeGenerator


def test_anygen(gen_paths):  # type: ignore
    """
    Verifies that any dsdl type will resolve to an ``Any`` template.
    """
    root_namespace_dir = gen_paths.dsdl_dir / Path("uavcan")
    type_map: Iterable[Tuple[CompositeType, list[CompositeType]]] = zip(
        read_namespace(str(root_namespace_dir), []), itertools.repeat([])
    )
    language_context = (
        LanguageContextBuilder().set_target_language_configuration_override("extension", ".json").create()
    )
    root_namespace = NamespaceContext(language_context, gen_paths.out_dir, root_namespace_dir).add_types(type_map)
    generator = DSDLCodeGenerator(
        root_namespace, templates_dir=gen_paths.templates_dir, index_file=["index", "xml/default_template.xml"]
    )
    generator.generate_all(False)

    outfile = gen_paths.find_outfile_in_namespace("uavcan.time.SynchronizedTimestamp", root_namespace)

    assert outfile is not None

    with open(str(outfile), "r", encoding="utf-8") as json_file:
        json_blob = json.load(json_file)

    assert json_blob is not None
    assert json_blob["full_name"] == "uavcan.time.SynchronizedTimestamp"
    assert (gen_paths.out_dir / Path("index.json")).exists()
    assert (gen_paths.out_dir / Path("xml", "default_template.xml")).exists()
