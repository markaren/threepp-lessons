// One of the two programs in the lesson film "Coupling and cohesion" (films/coupling_cohesion.py):
// the level crossing of tangled.cpp, tidied up. It prints what tangled.cpp prints.
//
// A console program: it opens no window. Each class does one job and keeps its data private; the
// Controller is the only class that knows the others, and it knows only their public functions.
// Built with NEW_SENSOR, the radar is replaced by a contact on the rail, which keeps different
// data. Nothing outside Sensor changes, and the program prints the same lines.
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

#ifndef NEW_SENSOR
// [sensor]
class Sensor {
public:
    void read(int tick) { distance_ = std::abs(trainAt(tick)); }
    bool trainNear() const { return distance_ < SAFE_DISTANCE; }

private:
    int distance_ = FAR_AWAY;
};
// [end]
#else
// [new_sensor]
class Sensor {
public:
    void read(int tick) {
        occupied_ = std::abs(trainAt(tick)) < SAFE_DISTANCE;
    }
    bool trainNear() const { return occupied_; }

private:
    bool occupied_ = false;
};
// [end]
#endif

class Gate {
public:
    void lower() { angle_ = std::max(DOWN, angle_ - STEP); }
    void raise() { angle_ = std::min(UP, angle_ + STEP); }
    bool isUp() const { return angle_ == UP; }

private:
    int angle_ = UP;
};

class Lights {
public:
    void on() { lit_ = true; }
    void off() { lit_ = false; }
    bool isOn() const { return lit_; }

private:
    bool lit_ = false;
};

class Controller {
public:
    Controller(Sensor& sensor, Gate& gate, Lights& lights)
        : sensor_(sensor), gate_(gate), lights_(lights) {}

    // [update]
    void update() {
        if (sensor_.trainNear()) {
            lights_.on();
            gate_.lower();
        } else {
            gate_.raise();
            if (gate_.isUp()) {
                lights_.off();
            }
        }
    }
    // [end]

private:
    Sensor& sensor_;
    Gate& gate_;
    Lights& lights_;
};

int main() {
    Sensor sensor;
    Gate gate;
    Lights lights;
    Controller controller(sensor, gate, lights);
    for (int tick = 0; tick < TICKS; ++tick) {
        sensor.read(tick);
        controller.update();
        std::cout << (sensor.trainNear() ? "train near  " : "train far   ")
                  << (gate.isUp() ? "gate open    " : "gate closed  ")
                  << (lights.isOn() ? "lights on" : "lights off") << "\n";
    }
}
