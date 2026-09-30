
# the app built in the lesson film "Part 0b: your first real app"
lesson_program(lesson_app SOURCES app.cpp IMGUI)

# The film's capture builds (not built by default): the program as it stands after each
# step, run headless on a fixed time step with a scripted mouse (see capture.hpp).
foreach (step RANGE 0 8)
    lesson_program("lesson_app_capture_${step}" SOURCES app.cpp IMGUI)
    target_compile_definitions("lesson_app_capture_${step}" PRIVATE STEP=${step} LESSON_CAPTURE)
    set_target_properties("lesson_app_capture_${step}" PROPERTIES EXCLUDE_FROM_ALL TRUE)
    add_dependencies(captures "lesson_app_capture_${step}")
endforeach ()
lesson_program("lesson_app_capture_6_separate" SOURCES app.cpp IMGUI)
target_compile_definitions("lesson_app_capture_6_separate" PRIVATE STEP=6 LESSON_CAPTURE SEPARATE_MESHES)
set_target_properties("lesson_app_capture_6_separate" PROPERTIES EXCLUDE_FROM_ALL TRUE)
add_dependencies(captures "lesson_app_capture_6_separate")

# build lesson_app as it stood after one step: cmake -DLESSON_APP_STEP=3 (0..8; empty = the whole app)
set(LESSON_APP_STEP "" CACHE STRING "lesson_app as it stood after this step, 0..8 (empty: the whole app)")
if (NOT LESSON_APP_STEP STREQUAL "")
    target_compile_definitions(lesson_app PRIVATE STEP=${LESSON_APP_STEP})
endif ()

# the Snake program built in "Part 0c: threepp is the view"
add_subdirectory(snake)
