#
# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Copyright (C) 2018-2019  OpenCyphal Development Team  <opencyphal.org>
# This software is distributed under the terms of the MIT License.
#
import json
from pathlib import Path

from pydsdl import read_namespace

from nunavut import LanguageContextBuilder, NamespaceFactory
from nunavut.jinja import DSDLCodeGenerator


def test_anygen(gen_paths):  # type: ignore
    """
    Verifies that any dsdl type will resolve to an ``Any`` template.
    """
    root_namespace_dir = gen_paths.dsdl_dir / Path("uavcan")
    type_map = read_namespace(str(root_namespace_dir), [])
    language_context = (
        LanguageContextBuilder().set_target_language_configuration_override("extension", ".json").create()
    )
    root_namespace = NamespaceFactory(language_context, gen_paths.out_dir, root_namespace_dir).add_types(type_map)
    generator = DSDLCodeGenerator(root_namespace, templates_dir=gen_paths.templates_dir)
    generator.generate_all(False)

    outfile = gen_paths.find_outfile_in_namespace("uavcan.time.SynchronizedTimestamp", root_namespace)

    assert outfile is not None

    with open(str(outfile), "r", encoding="utf-8") as json_file:
        json_blob = json.load(json_file)

    assert json_blob is not None
    assert json_blob["full_name"] == "uavcan.time.SynchronizedTimestamp"
