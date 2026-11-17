cmake_minimum_required(VERSION 3.20)
project(g474_backlight LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(backlight_includes INTERFACE)
target_include_directories(backlight_includes INTERFACE c cpp)
target_compile_options(backlight_includes INTERFACE -Wall -Wextra -Werror)

add_executable(app c/main.c cpp/app/app_main.cpp)
target_link_libraries(app PRIVATE backlight_includes)

enable_testing()
add_executable(test_backlight tests/test_backlight.cpp)
target_link_libraries(test_backlight PRIVATE backlight_includes)
add_test(NAME backlight_behavior COMMAND test_backlight)
