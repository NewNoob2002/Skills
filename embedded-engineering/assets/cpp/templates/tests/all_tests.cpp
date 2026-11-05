/// @file all_tests.cpp
/// @brief CppUTest 入口。CI 中建议运行：host_tests -c -v -s（随机顺序）与 -r2（发现静态状态残留）。

#include "CppUTest/CommandLineTestRunner.h"

int
main (int argc, char ** argv)
{
    return CommandLineTestRunner::RunAllTests(argc, argv);
}
