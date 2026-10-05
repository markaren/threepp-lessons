# the programs whose code "Polymorphism" shows: the threepp scene, the Square that cannot stand
# in for a Rectangle, and the Thermostat written both ways (no threepp in the last two)
lesson_program(lesson_polymorphism_scene SOURCES scene.cpp)
add_executable(lesson_polymorphism_liskov liskov.cpp)
add_executable(lesson_polymorphism_thermostat thermostat.cpp)
