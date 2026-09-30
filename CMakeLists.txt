cmake_minimum_required(VERSION 3.19)
project(threepp_lessons CXX)

# The C++ programs the films show and run (programs/): Part 0b's app and Part 0c/0d's Snake,
# each with the capture builds a film streams headless (the `captures` target builds them all).

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin")    # where films/lesson.py looks for them
if (NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
    set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type (single-config generators)" FORCE)
endif ()

option(LESSONS_BUILD_TESTS "Build the Snake tests" ON)

include(FetchContent)

# threepp, the way Part 0 shows a project of your own getting it. A threepp checkout next to
# this repository is used instead when there is one (-DFETCHCONTENT_SOURCE_DIR_THREEPP=<dir>
# names another). The lessons follow threepp's dev branch.
if (NOT DEFINED FETCHCONTENT_SOURCE_DIR_THREEPP AND EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/../threepp/CMakeLists.txt")
    set(FETCHCONTENT_SOURCE_DIR_THREEPP "${CMAKE_CURRENT_SOURCE_DIR}/../threepp" CACHE PATH "threepp checkout")
endif ()
FetchContent_Declare(threepp GIT_REPOSITORY https://github.com/markaren/threepp.git GIT_TAG dev)
FetchContent_MakeAvailable(threepp)

# The assets Part 0b's app loads (the soldier, the sky), the same threepp_data commit threepp's
# own examples use (-DFETCHCONTENT_SOURCE_DIR_THREEPP_DATA=<dir> for a local copy).
FetchContent_Declare(
        threepp_data
        URL https://github.com/markaren/threepp_data/archive/9689df3c4fbecabf727855657b5ac610caa8776d.tar.gz
        DOWNLOAD_EXTRACT_TIMESTAMP TRUE
)
FetchContent_MakeAvailable(threepp_data)

# Dear ImGui for the app's sun panel: threepp's own copy, the one its ImguiContext.hpp is
# written against, built the way threepp's examples build it.
set(IMGUI_DIR "${threepp_SOURCE_DIR}/examples/external/imgui")
add_library(imgui STATIC
        "${IMGUI_DIR}/imgui.cpp" "${IMGUI_DIR}/imgui_draw.cpp" "${IMGUI_DIR}/imgui_tables.cpp"
        "${IMGUI_DIR}/imgui_widgets.cpp" "${IMGUI_DIR}/imgui_impl_glfw.cpp" "${IMGUI_DIR}/imgui_impl_opengl3.cpp")
target_include_directories(imgui PUBLIC "${IMGUI_DIR}")
target_link_libraries(imgui PRIVATE glfw)

# lesson_program(<name> SOURCES <files...> [IMGUI]): a program that links threepp and finds
# threepp_data through DATA_FOLDER.
function(lesson_program name)
    cmake_parse_arguments(arg "IMGUI" "" "SOURCES" ${ARGN})
    add_executable("${name}" ${arg_SOURCES})
    target_link_libraries("${name}" PRIVATE threepp::threepp)
    if (arg_IMGUI)
        target_link_libraries("${name}" PRIVATE imgui)
    endif ()
    target_compile_definitions("${name}" PRIVATE DATA_FOLDER="${threepp_data_SOURCE_DIR}")
endfunction()

# The films' capture builds are left out of `all`; this builds every one of them.
add_custom_target(captures)

if (LESSONS_BUILD_TESTS)
    FetchContent_Declare(Catch2 GIT_REPOSITORY https://github.com/catchorg/Catch2.git GIT_TAG v3.4.0)
    FetchContent_MakeAvailable(Catch2)
    enable_testing()
endif ()

add_subdirectory(programs)
