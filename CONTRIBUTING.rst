#####################
Contributor Notes
#####################

|:wave:| Thanks for contributing. This page contains all the details about getting
your dev environment setup.

.. note::

    This is documentation for contributors developing nunavut. If you are
    a user of this software you can ignore everything here.

    - To ask questions about nunavut or Cyphal in general please see the `OpenCyphal forum`_.
    - See `nunavut on read the docs`_ for the full set of nunavut documentation.
    - See the `OpenCyphal website`_ for documentation on the Cyphal protocol.

.. warning::

    When committing to main you **must** bump at least the patch number in ``src/nunavut/_version.py``
    or the build will fail on the upload step.


************************************************
Tools
************************************************

tox devenv -e local
================================================

I highly recommend using the local tox environment when doing python development. It'll save you hours
of lost productivity the first time it keeps you from pulling in an unexpected dependency from your
global python environment. You can install tox from brew on osx or apt-get on GNU/Linux. I'd
recommend the following environment for vscode::

    git submodule update --init --recursive
    tox devenv -e local
    source venv/bin/activate

On Windows that last line is instead::

    ./venv/Scripts/activate

cmake
================================================

Our language generation verification suite uses CMake to build and run unit tests. If you are working
with a native language see `Nunavut Verification Suite`_ for details on manually running these builds
and tests.

Visual Studio Code
================================================

To use vscode you'll need:

1. vscode
2. install vscode command line (`Shell Command: Install`)
3. tox
4. cmake (and an available GCC or Clang toolchain, or Docker to use our toolchain-as-container)

Do::

    cd path/to/nunavut
    git submodule update --init --recursive
    tox devenv -e local
    source venv/bin/activate
    code .

Then install recommended extensions.

************************************************
Running The Tests
************************************************

To run the full suite of `tox`_ tests locally you'll need docker. Once you have docker installed
and running do::

    git submodule update --init --recursive
    docker pull ghcr.io/opencyphal/toxic:tx22.4.3
    docker run --rm -v $PWD:/repo ghcr.io/opencyphal/toxic:tx22.4.3 tox

To run a limited suite using only locally available interpreters directly on your host machine,
skip the docker invocations and use ``tox run -s``.

To run the language verification build you'll need to use a different docker container::

    docker pull ghcr.io/opencyphal/toolshed:ts24.4.3
    docker run --rm -it -v $PWD:/workspace ghcr.io/opencyphal/toolshed:ts24.4.3
    cd /workspace/verification
    cmake --list-presets

Choose one of the presets. For example::

    cmake --preset config-clang-native-c-11

To build replace the prefix ``config`` with ``build`` and suffix with one of the configurations listed in the presets
file as ``CMAKE_CONFIGURATION_TYPES`` but in all lower-case. For example::

    cmake --build --preset build-clang-native-c-11-debug

The verification cmake uses Ninja Multi-Config so you can run any ``build-clang-native-c-11-`` build flavor without
re-configuring in this example.

If you get a "denied" response from ghcr your ip might be getting rate-limited. While these are public containers
you'll have to login to get around any rate-limiting for your local site. See [the github docs](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
for how to setup a docker client login.


If you get the following error::

    gcc: error: unrecognized command-line option ‘-m32’

...it may mean you are trying to run one of our 32-bit platform tests using an armv8 docker image. For these builds
you might need to override the target platform and pull the x86 version of the container explicitly. For example::

     docker run --rm -it --platform linux/amd64 -v $PWD:/workspace ghcr.io/opencyphal/toolshed:ts24.4.3


Files Generated by the Tests
================================================

Given that Nunavut is a file generator our tests do have to write files. Normally these files are
temporary and therefore automatically deleted after the test completes. If you want to keep the
files so you can debug an issue provide a "keep-generated" argument.

**example** ::

    pytest -k test_namespace_stropping --keep-generated

You will see each test's output under "build/(test name}".

.. warning::

    Don't use this option when running tests in parallel. You will get errors.


Sybil Doctest
================================================

This project makes extensive use of `Sybil <https://sybil.readthedocs.io/en/latest/>`_ doctests.
These take the form of docstrings with a structure like thus::

    .. invisible-code-block: python

        from nunavut.lang.c import filter_to_snake_case

    .. code-block:: python

        # an input like this:
        input = "scotec.mcu.Timer"

        # should yield:
        filter_to_snake_case(input)
        >>> scotec_mcu_timer

The invisible code block is executed but not displayed in the generated documentation and,
conversely, ``code-block`` is both rendered using proper syntax formatting in the documentation
and executed. REPL works the same as it does for :mod:`doctest` but ``assert`` is also a valid
way to ensure the example is correct especially if used in a trailing ``invisible-code-block``::

    .. invisible-code-block: python

        assert 'scotec_mcu_timer' == filter_to_snake_case(input)

These tests are run as part of the regular pytest build. You can see the Sybil setup in the
``conftest.py`` found under the project directory but otherwise shouldn't need to worry about
it. The simple rule is; if the docstring ends up in the rendered documentation then your
``code-block`` tests will be executed as unit tests.


import file mismatch
================================================

If you get an error like the following::

    _____ ERROR collecting test/gentest_dsdl/test_dsdl.py _______________________________________
    import file mismatch:
    imported module 'test_dsdl' has this __file__ attribute:
    /my/workspace/nunavut/test/gentest_dsdl/test_dsdl.py
    which is not the same as the test file we want to collect:
    /repo/test/gentest_dsdl/test_dsdl.py
    HINT: remove __pycache__ / .pyc files and/or use a unique basename for your test file modules


Then you are probably a wonderful developer that is running the unit-tests locally. Pytest's cache
is interfering with your docker test run. To work around this simply delete the pycache files. For
example::

    #! /usr/bin/env bash
    clean_dirs="src test"

    for clean_dir in $clean_dirs
    do
        find $clean_dir -name __pycache__ | xargs rm -rf
        find $clean_dir -name \.coverage\* | xargs rm -f
    done

Note that we also delete the .coverage intermediates since they may contain different paths between
the container and the host build.

Alternatively just nuke everything temporary using git clean::

    git clean -X -d -f

************************************************
Building The Docs
************************************************

We rely on `read the docs`_ to build our documentation from github but we also verify this build
as part of our tox build. This means you can view a local copy after completing a full, successful
test run (See `Running The Tests`_) or do
:code:`docker run --rm -t -v $PWD:/repo ghcr.io/opencyphal/toxic:tx22.4.3 /bin/sh -c "tox run -e docs"` to build
the docs target. You can open the index.html under ``.tox_{host platform}/docs/tmp/index.html`` or run a local
web-server::

    python3 -m http.server --directory .tox_{host platform}/docs/tmp &
    open http://localhost:8000/docs/index.html

Of course, you can just use `Visual Studio Code`_ to build and preview the docs using
:code:`> reStructuredText: Open Preview`.


************************************************
Coverage and Linting Reports
************************************************

We publish the results of our coverage data to `sonarcloud`_ and the tox build will fail for any mypy
or black errors but you can view additional reports locally under the :code:`.tox_{host platform}` dir.

Coverage
================================================

We generate a local html coverage report. You can open the index.html under .tox_{host platform}/report/tmp
or run a local web-server::

    python -m http.server --directory .tox_{host platform}/report/tmp &
    open http://localhost:8000/index.html

Mypy
================================================

At the end of the mypy run we generate the following summaries:

- .tox_{host platform}/mypy/tmp/mypy-report-lib/index.txt
- .tox_{host platform}/mypy/tmp/mypy-report-script/index.txt

************************************************
Nunavut Verification Suite
************************************************

Nunavut has built-in support for several languages. Included with this is a suite of tests using typical test
frameworks and language compilers, interpreters, and/or virtual machines. While each release of Nunavut is
gated on automatic and successful completion of these tests this guide is provided to give system integrators
information on how to customize these verifications to use other compilers, interpreters, and/or virtual
machines.

CMake scripts
================================================

Our language generation verification suite uses CMake to build and run unit tests.
Instructions for reproducing the CI automation execution steps are below. This section will tell you how
to manually build and run individual unit tests as you develop them.

TLDR::

    git submodule update --init --recursive
    docker run --rm -it -v $PWD:/repo ghcr.io/opencyphal/toolshed:ts24.4.3
    cd verification
    cmake --preset config-clang-native-c-11
    cmake --build --preset build-clang-native-c-11-debug


To see all presets available do::

    cmake --list-presets
    cmake --build --list-presets


After configuring you can also use Ninja directly::

    cd build
    ninja -t targets

To obtain coverage information for the verification suite (not the Python code),
build the `cov_all` target and inspect the output under the `coverage` directory::

    cmake --build --preset build-clang-native-c-11-debug --target cov_all

.. warning::

    When switching between gcc and clang you must do a full clean of your repo if you previously ran the coverage
    build. For example ``git clean -xdf`` or clone a new repo in a different folder. Each compiler suite leaves
    different byproducts that may interfere with the coverage tools in the other suite.

While we strongly encourage you to use the cmake presets, the CMakeLists.txt for the verification suite is driven by
three variables you can set in your environment or pass into cmake if using cmake directly:

 - ``NUNAVUT_VERIFICATION_LANG`` - By default this will be 'c'. Set to 'c' or 'cpp'
 - ``NUNAVUT_VERIFICATION_LANG_STANDARD`` - See the supported options for ``--language-standard`` (see ``nnvg -h``)
 - ``NUNAVUT_VERIFICATION_TARGET_PLATFORM`` - 'native' by default. 'native32' for cross-compiling for a 32-bit version of the native platform.

All other options set when generating code are provided by setting ``NUNAVUT_EXTRA_GENERATOR_ARGS`` in your environment.

.. _`read the docs`: https://readthedocs.org/
.. _`tox`: https://tox.readthedocs.io/en/latest/
.. _`sonarcloud`: https://sonarcloud.io/dashboard?id=OpenCyphal_nunavut
.. _`OpenCyphal website`: http://opencyphal.org
.. _`OpenCyphal forum`: https://forum.opencyphal.org
.. _`nunavut on read the docs`: https://nunavut.readthedocs.io/en/latest/index.html
.. _`VSCode Remote Containers`: https://code.visualstudio.com/docs/remote/containers
