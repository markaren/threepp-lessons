// One of the two programs in the lesson film "Coupling and cohesion" (films/coupling_cohesion.py):
// a level crossing, written the tangled way. It works, and prints what tidy.cpp prints.
//
// A console program: it opens no window. A train passes once; every tick the sensor is read, the
// gate moves and one line is printed. The three classes keep their data public, each function
// does a bit of several jobs, and they reach into each other's data.
// Built with NEW_SENSOR, the radar is replaced by a contact on the rail, which keeps different
// data: Gate::move and Lights::print then no longer compile. That is the film's second beat, and
// the reason the CMake target for it is not built by default.
// The film shows the lines between each "// [name]" and its "// [end]".

#include <algorithm>
#include <cstdlib>
#include <iostream>

const int TICKS = 16;         // one train passes in this many ticks
const int SPEED = 100;        // metres the train moves in one tick
const int SAFE_DISTANCE = 350;   // metres: with the train closer than this, the crossing is closed
const int FAR_AWAY = 1000;
const int UP = 90;            // the gate's angle, in degrees
const int DOWN = 0;
const int STEP = 30;          // how far the gate turns in one tick

int trainAt(int tick) {       // the world: where the train is, in metres past the crossing
    return (tick - 6) * SPEED;
}

struct Lights;

#ifndef NEW_SENSOR
struct Sensor {               // a radar: how far away is the train?
    int distance = FAR_AWAY;
    void read(int tick, Lights& lights);
};
#else
struct Sensor {               // a contact on the rail: is a train on this stretch of track?
    bool occupied = false;
    void read(int tick, Lights& lights);
};
#endif

struct Gate {
    int angle = UP;
    void move(const Sensor& sensor, Lights& lights);
};

struct Lights {
    bool lit = false;
    void print(const Sensor& sensor, const Gate& gate) const;
};

#ifndef NEW_SENSOR
void Sensor::read(int tick, Lights& lights) {
    distance = std::abs(trainAt(tick));
    if (distance < SAFE_DISTANCE) {
        lights.lit = true;
    }
}
#else
void Sensor::read(int tick, Lights& lights) {
    occupied = std::abs(trainAt(tick)) < SAFE_DISTANCE;
    if (occupied) {
        lights.lit = true;
    }
}
#endif

// [move]
void Gate::move(const Sensor& sensor, Lights& lights) {
    if (sensor.distance < SAFE_DISTANCE) {
        angle = std::max(DOWN, angle - STEP);
    } else {
        angle = std::min(UP, angle + STEP);
        if (angle == UP) {
            lights.lit = false;
        }
    }
}
// [end]

void Lights::print(const Sensor& sensor, const Gate& gate) const {
    std::cout << (sensor.distance < SAFE_DISTANCE ? "train near  " : "train far   ")
              << (gate.angle == UP ? "gate open    " : "gate closed  ")
              << (lit ? "lights on" : "lights off") << "\n";
}

int main() {
    Sensor sensor;
    Gate gate;
    Lights lights;
    for (int tick = 0; tick < TICKS; ++tick) {
        sensor.read(tick, lights);
        gate.move(sensor, lights);
        lights.print(sensor, gate);
    }
}
