# The C++ programs in the sockets lesson film, as a project of their own (not part of threepp's build).
#
#   cmake -B build            # fetches SimpleSocket from GitHub
#   cmake --build build
#
# Or point it at a local checkout: -DSIMPLE_SOCKET_DIR=path/to/SimpleSocket
cmake_minimum_required(VERSION 3.19)
project(sockets_lesson CXX)
set(CMAKE_CXX_STANDARD 20)

set(SIMPLE_SOCKET_BUILD_TESTS OFF)
set(SIMPLE_SOCKET_WITH_TLS OFF)
set(SIMPLE_SOCKET_WITH_MQTT OFF)
set(SIMPLE_SOCKET_WITH_MODBUS OFF)
set(SIMPLE_SOCKET_WITH_MEMORY OFF)
set(SIMPLE_SOCKET_WITH_WEBSOCKETS OFF)
set(SIMPLE_SOCKET_DIR "" CACHE PATH "a local SimpleSocket checkout (empty: fetch it)")
if (SIMPLE_SOCKET_DIR)
    add_subdirectory(${SIMPLE_SOCKET_DIR} simple_socket)
else ()
    include(FetchContent)
    FetchContent_Declare(SimpleSocket
            GIT_REPOSITORY https://github.com/markaren/SimpleSocket.git
            GIT_TAG 5d35263)
    FetchContent_MakeAvailable(SimpleSocket)
endif ()

foreach (t echo_server echo_client pingpong_server pingpong_client)
    add_executable(${t} ${t}.cpp)
    target_link_libraries(${t} PRIVATE simple_socket)
endforeach ()

# the operating system's own API, as the e-book shows it: POSIX only (Linux, macOS, WSL)
if (NOT WIN32)
    add_executable(posix_echo_server posix_echo_server.cpp)
endif ()
