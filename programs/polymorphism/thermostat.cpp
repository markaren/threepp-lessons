// The two Thermostats in the lesson film "Polymorphism" (films/polymorphism_rules.py): one that
// inherits from the sensor it reads, and one that holds it as a member. Both compile and both
// work; they differ in what a Thermostat offers the rest of the program.
// The film shows the lines between each "// [name]" and its "// [end]".

#include <iostream>

class TemperatureSensor {
public:
    double readCelsius() const { return 21.5; }    // a real one would read the hardware
};

namespace is_a {

    // [is_a]
    class Thermostat : public TemperatureSensor {
    public:
        bool shouldHeat(double target) const {
            return readCelsius() < target;
        }
    };
    // [end]

}// namespace is_a

namespace has_a {

    // [has_a]
    class Thermostat {
        TemperatureSensor sensor_;
    public:
        bool shouldHeat(double target) const {
            return sensor_.readCelsius() < target;
        }
    };
    // [end]

}// namespace has_a

int main() {
    const double target = 22;

    is_a::Thermostat inherited;
    has_a::Thermostat composed;
    std::cout << std::boolalpha << "inherited: " << inherited.shouldHeat(target) << ", composed: "
              << composed.shouldHeat(target) << "\n";

    // the sensor's function is the inheriting Thermostat's too
    std::cout << "inherited.readCelsius(): " << inherited.readCelsius() << "\n";

#ifdef LEAK
    composed.readCelsius();    // does not compile: has_a::Thermostat has no member named readCelsius
#endif
}
