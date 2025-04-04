################################################
Software Language Generation Guide
################################################

.. note ::
    This is a placeholder for documentation this project owes you, the user, for how to integrate nnvg with build
    systems and how to tune and optimize source code generation for each supported language.

*************************
C++ (experimental)
*************************

See :ref:`template-language-guide` until this section is more complete.

============================================================
Using a Different Variable-Length Array Type and Allocator
============================================================

For now this tip is important for people using the experimental C++ support.  To set which variable length array
implementation to use, create a properties override json file and pass it to nnvg.  Specifying the use of an
allocator is optional (If ctor_convention is set to "default" then the allocator_include and allocator_type
properties don't need to be set.)

Alternatively, you may specify the language standard argument as -std=c++20-pmr, -std=c++17-pmr or -std=cetl++14-17
as short-hand for the following configurations shown below.  Note that "cetl++14-17" means target C++14 but use
the CETL C++17 polyfill types.

c++20-pmr.json
"""""""""""""""""

.. code-block :: json

    {
      "nunavut.lang.cpp": {
        "options": {
          "variable_array_type_include": "<vector>",
          "variable_array_type_template": "std::vector<{TYPE}, {REBIND_ALLOCATOR}>",
          "variable_array_type_constructor_args": "",
          "allocator_include": "<memory>",
          "allocator_type": "std::pmr::polymorphic_allocator",
          "allocator_is_default_constructible": true,
          "ctor_convention": "uses-trailing-allocator"
        }
      }
    }

c++17-pmr.json
"""""""""""""""""

.. code-block :: json

    {
      "nunavut.lang.cpp": {
        "options": {
          "variable_array_type_include": "<vector>",
          "variable_array_type_template": "std::vector<{TYPE}, {REBIND_ALLOCATOR}>",
          "variable_array_type_constructor_args": "",
          "allocator_include": "<memory>",
          "allocator_type": "std::pmr::polymorphic_allocator",
          "allocator_is_default_constructible": true,
          "ctor_convention": "uses-trailing-allocator"
        }
      }
    }

cetl++14-17.json
"""""""""""""""""

.. code-block :: json

    {
      "nunavut.lang.cpp": {
        "options": {
          "variable_array_type_include": "\"cetl/variable_length_array.hpp\"",
          "variable_array_type_template": "cetl::VariableLengthArray<{TYPE}, {REBIND_ALLOCATOR}>",
          "variable_array_type_constructor_args": "{MAX_SIZE}",
          "allocator_include": "\"cetl/pf17/sys/memory_resource.hpp\"",
          "allocator_type": "cetl::pf17::pmr::polymorphic_allocator",
          "allocator_is_default_constructible": false,
          "ctor_convention": "uses-trailing-allocator",
          "variant_include": "\"cetl/pf17/variant.hpp\"",
        }
      }
    }

nnvg command
""""""""""""""""""

.. code-block :: bash

    nnvg --configuration=c++17-pmr.json \  # or --configuration=cetl++14-17.json
         -l cpp \
        --experimental-languages \
        -I path/to/public_regulated_data_types/uavcan \
        /path/to/my_types

*************************
Python
*************************

The Python language support generates Python packages that depend on the following packages:

* **PyDSDL** --- maintained by the OpenCyphal team at https://github.com/OpenCyphal/pydsdl.
* **NumPy** --- a third-party dependency needed for fast serialization of arrays, esp. bit arrays.
* :code:`nunavut_support.py` --- produced by Nunavut itself and stored next to the other generated packages.
  When redistributing generated code, this package should be included as well.

These are the only dependencies of the generated code. Nunavut itself is notably excluded from this list.
The generated code should be compatible with all current versions of Python.
To see the specific versions of Python and dependencies that generated code is tested against,
please refer to ``verification/python`` in the source tree.

At the moment there are no code generation options for Python;
that is, the generated code is always the same irrespective of the options given.

The ``nunavut_support.py`` module includes several members that are useful for working with generated code.
The documentation for each member is provided in the docstrings of the module itself;
please be sure to read it.
The most important members are:

* :code:`serialize`, :code:`deserialize` --- (de)serialize a DSDL object.
* :code:`get_model`, :code:`get_class` --- map a Python class to a PyDSDL AST model and vice versa.
* :code:`get_extent_bytes`, :code:`get_fixed_port_id`, etc. --- get information about a DSDL object.
* :code:`to_builtin`, :code:`update_from_builtin` --- convert a DSDL object to/from a Python dictionary.
  This is useful for conversion between DSDL and JSON et al.
* :code:`get_attribute`, :code:`set_attribute` --- get/set object fields.
  DSDL fields that are named like Python builtins or keywords are modified with a trailing underscore;
  .e.g., ``if`` becomes ``if_``.
  These helpers allow one to access fields by their DSDL name without having to worry about this.
