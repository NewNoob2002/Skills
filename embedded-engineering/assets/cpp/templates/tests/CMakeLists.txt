# 主机单元测试（CppUTest）。生产代码的目标机构建在固件工程中，这里只编译可移植的 C++ 逻辑。
# 用法：
#   cmake -S . -B build-host -DETL_INCLUDE_DIR=<etl>/include -DPROJ_ROOT=<固件仓库根>
#   cmake --build build-host && ctest --test-dir build-host --output-on-failure
cmake_minimum_required(VERSION 3.16)
project(proj_host_tests CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(ETL_INCLUDE_DIR "" CACHE PATH "ETL include directory (contains etl/)")
set(PROJ_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/.." CACHE PATH "Firmware repository root")
# 厂商 SDK / CMSIS 头文件目录（分号分隔），作为 SYSTEM 包含以免严格告警波及第三方头。
set(PROJ_SDK_INCLUDE_DIRS "${PROJ_ROOT}/sdk_stub" CACHE STRING "Vendor SDK include directories")
if(NOT EXISTS "${ETL_INCLUDE_DIR}/etl/platform.h")
  message(FATAL_ERROR "Set ETL_INCLUDE_DIR to the ETL include directory")
endif()

find_package(CppUTest 4 REQUIRED)
# CppUTest 4.0 发布版导出 CppUTest / CppUTestExt；master 分支另提供 CppUTest:: 命名空间别名。
if(TARGET CppUTest::CppUTest)
  set(PROJ_CPPUTEST_LIBS CppUTest::CppUTest CppUTest::CppUTestExt)
else()
  set(PROJ_CPPUTEST_LIBS CppUTest CppUTestExt)
endif()

add_executable(host_tests
  all_tests.cpp
  test_bme280.cpp
  support/vendor_i2c_mock.cpp)
target_include_directories(host_tests PRIVATE
  ${PROJ_ROOT}/interface ${PROJ_ROOT}/driver/device ${PROJ_ROOT}/bsp ${PROJ_ROOT}/lib)
target_include_directories(host_tests SYSTEM PRIVATE ${ETL_INCLUDE_DIR} ${PROJ_SDK_INCLUDE_DIRS})
# 与目标机相同的严格告警，捕获可移植性问题；主机测试不强制 -fno-exceptions（CppUTest 自身可能使用）。
target_compile_options(host_tests PRIVATE -Wall -Wextra -Wpedantic -Wshadow -Wconversion
  -Wold-style-cast -Wnon-virtual-dtor -Werror -fsanitize=address,undefined)
target_link_options(host_tests PRIVATE -fsanitize=address,undefined)
target_link_libraries(host_tests PRIVATE ${PROJ_CPPUTEST_LIBS})

enable_testing()
add_test(NAME host_tests COMMAND host_tests -c -v -s)
