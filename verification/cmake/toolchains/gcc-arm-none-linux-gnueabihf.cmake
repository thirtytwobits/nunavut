#
# Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# arm-none-eabi-linux with hard-float gcc cross compiler.
#
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSTEM_PROCESSOR arm)

set(TOOLCHAIN_TRIPLE arm-none-linux-gnueabihf)

set(CMAKE_C_COMPILER        ${TOOLCHAIN_TRIPLE}-gcc      CACHE INTERNAL "C Compiler")
set(CMAKE_LINKER            ${TOOLCHAIN_TRIPLE}-ld       CACHE INTERNAL "Linker")
set(CMAKE_CXX_COMPILER      ${TOOLCHAIN_TRIPLE}-g++      CACHE INTERNAL "C++ Compiler")
set(CMAKE_AR                ${TOOLCHAIN_TRIPLE}-ar       CACHE INTERNAL "Archiver")
set(CMAKE_ASM_COMPILER      ${TOOLCHAIN_TRIPLE}-as       CACHE INTERNAL "Assembler")
set(CMAKE_OBJCOPY           ${TOOLCHAIN_TRIPLE}-objcopy  CACHE INTERNAL "Object Copy")
set(CMAKE_RANLIB            ${TOOLCHAIN_TRIPLE}-ranlib   CACHE INTERNAL "Library Indexer")
set(CMAKE_STRIP             ${TOOLCHAIN_TRIPLE}-strip    CACHE INTERNAL "Stripper")
set(CMAKE_OBJDUMP           ${TOOLCHAIN_TRIPLE}-objdump  CACHE INTERNAL "Object introspection")

execute_process(
        COMMAND which ${CMAKE_C_COMPILER}
        OUTPUT_VARIABLE LOCAL_BINUTILS_PATH
        OUTPUT_STRIP_TRAILING_WHITESPACE
)

get_filename_component(TOOLCHAIN_DIR ${LOCAL_BINUTILS_PATH} DIRECTORY)

set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)
set(CMAKE_SYSROOT ${TOOLCHAIN_DIR}/../${TOOLCHAIN_TRIPLE})
set(CMAKE_FIND_ROOT_PATH ${TOOLCHAIN_DIR}/../${TOOLCHAIN_TRIPLE})
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
