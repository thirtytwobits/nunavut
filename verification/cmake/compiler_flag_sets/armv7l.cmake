#
# Copyright 2020 Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# C, CXX, LD, and AS flags for a cortex-a7 (e.g. Raspberry Pi 3B)
#

#
# Flags for C and C++
#
include(${CMAKE_CURRENT_LIST_DIR}/common.cmake)

list(APPEND C_AND_CXX_FLAG_SET
                         "-mcpu=cortex-a7"
                         "-DGTEST_HAS_POSIX_RE=0"
                         "-DGTEST_HAS_PTHREAD=0"
                         "-DGTEST_HAS_DEATH_TEST=0"
                         "-DGTEST_HAS_STREAM_REDIRECTION=0"
                         "-DGTEST_HAS_RTTI=0"
                         "-DGTEST_HAS_EXCEPTIONS=0"
                         "-DGTEST_HAS_DOWNCAST_=0"
                         "-DGTEST_HAS_MUTEX_AND_THREAD_LOCAL_=0"
                         "-DGTEST_USES_POSIX_RE=0"
                         "-DGTEST_USES_PCRE=0"
)

list(APPEND C_FLAG_SET ${C_AND_CXX_FLAG_SET})
list(APPEND CXX_FLAG_SET ${C_AND_CXX_FLAG_SET})
list(APPEND ASM_FLAG_SET ${C_AND_CXX_FLAG_SET})

list(APPEND CXX_FLAG_SET "-fno-exceptions"
                         "-fno-rtti"
                         "-fno-threadsafe-statics"
)
