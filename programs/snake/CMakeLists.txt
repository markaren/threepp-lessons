# the Snake program built in "A threepp lesson, Part 0c: threepp is the view"

# the "before" pictures: everything in main(), then the inheritance trap
lesson_program(lesson_snake_tangle SOURCES tangle/main.cpp)
lesson_program(lesson_snake_trap SOURCES trap/main.cpp)

# The film's capture builds (not built by default): headless, a fixed 1/60 s clock and
# scripted keys. ../capture.hpp is force-included, so the sources stay as shown on screen.
set(LESSON_CAPTURE_HPP "${CMAKE_CURRENT_SOURCE_DIR}/../capture.hpp")
function(snake_capture name)
    target_compile_definitions("${name}" PRIVATE LESSON_CAPTURE ${ARGN})
    if (MSVC)
        target_compile_options("${name}" PRIVATE "/FI${LESSON_CAPTURE_HPP}")
    else ()
        target_compile_options("${name}" PRIVATE "SHELL:-include ${LESSON_CAPTURE_HPP}")
    endif ()
    set_target_properties("${name}" PROPERTIES EXCLUDE_FROM_ALL TRUE)
    add_dependencies(captures "${name}")
endfunction()
foreach (name tangle trap)
    lesson_program("lesson_snake_${name}_capture" SOURCES ${name}/main.cpp)
    snake_capture("lesson_snake_${name}_capture")
endforeach ()
# the trap with its Group moved by one line elsewhere (-DLESSON_MOVE_GROUP): drawn and rules part ways
lesson_program(lesson_snake_trap_moved_capture SOURCES trap/main.cpp)
snake_capture(lesson_snake_trap_moved_capture LESSON_MOVE_GROUP)

# The rules are a library of their own. It doesn't link threepp, so a threepp
# #include in the model fails to compile: the build keeps the design honest.
add_library(snake_model STATIC model/Snake.cpp model/Game.cpp)
target_include_directories(snake_model PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}")
target_compile_features(snake_model PUBLIC cxx_std_20)

# the finished app: rules in snake_model, looks in view/, players in control/
set(SNAKE_APP_SOURCES main.cpp
        view/SnakeView.cpp view/AsciiView.cpp view/MinimapView.cpp
        control/KeyboardController.cpp control/GreedyAI.cpp)
lesson_program(lesson_snake SOURCES ${SNAKE_APP_SOURCES})
target_link_libraries(lesson_snake PRIVATE snake_model)

# build lesson_snake as it stood after one step: cmake -DLESSON_SNAKE_STEP=3 (1..6; empty = the whole app)
set(LESSON_SNAKE_STEP "" CACHE STRING "lesson_snake as it stood after this step, 1..6 (empty: the whole app)")
if (NOT LESSON_SNAKE_STEP STREQUAL "")
    target_compile_definitions(lesson_snake PRIVATE STEP=${LESSON_SNAKE_STEP})
endif ()

foreach (step RANGE 1 6)
    lesson_program("lesson_snake_capture_${step}" SOURCES ${SNAKE_APP_SOURCES})
    target_link_libraries("lesson_snake_capture_${step}" PRIVATE snake_model)
    snake_capture("lesson_snake_capture_${step}" STEP=${step})
endforeach ()

# The tests don't link threepp either, and neither do the two classes they bring
# along: the text view and the AI build without it, so they can be tested without it.
if (LESSONS_BUILD_TESTS)
    add_executable(test_snake
            tests/test_game.cpp tests/test_ascii_view.cpp tests/test_greedy_ai.cpp
            view/AsciiView.cpp control/GreedyAI.cpp)
    target_link_libraries(test_snake PRIVATE snake_model Catch2::Catch2WithMain)
    add_test(NAME test_snake COMMAND test_snake)
endif ()
