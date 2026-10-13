# the two programs "Coupling and cohesion" takes apart: one level crossing, written twice (no threepp)
add_executable(lesson_coupling_tangled tangled.cpp)
add_executable(lesson_coupling_tidy tidy.cpp)

# the same two with the sensor replaced (NEW_SENSOR). The tidy one prints what it printed before.
# The tangled one does not compile, which is the film's point, so it is left out of `all`.
add_executable(lesson_coupling_tidy_new_sensor tidy.cpp)
target_compile_definitions(lesson_coupling_tidy_new_sensor PRIVATE NEW_SENSOR)
add_executable(lesson_coupling_tangled_new_sensor EXCLUDE_FROM_ALL tangled.cpp)
target_compile_definitions(lesson_coupling_tangled_new_sensor PRIVATE NEW_SENSOR)
