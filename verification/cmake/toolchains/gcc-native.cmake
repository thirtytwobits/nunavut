#
# Copyright 2019 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Toolchain for using gcc on what-ever-platform-this-is (aka "native").
#
set(CMAKE_C_COMPILER gcc CACHE FILEPATH "C compiler")
set(CMAKE_CXX_COMPILER g++ CACHE FILEPATH "C++ compiler")
set(CMAKE_ASM_COMPILER gcc CACHE FILEPATH "assembler")

set(VERIFICATION_COVERAGE_USE_LLVM_COV OFF CACHE BOOL "Enable gcov compatibility with lcov coverage tools.")
