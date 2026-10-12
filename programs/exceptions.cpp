// The program behind the lesson film "Throw, and catch" (films/exceptions.py).
//
// A console program: it opens no window. A tank monitor reads its level sensor through a
// stack of calls, main -> runCycle -> readLevel -> parseLevel, once on a good day and once
// on the day the sensor sends text. The film shows the lines between each pair of
// [markers], and the lines this program prints. `exceptions old` runs the old way instead (a
// special return value, which one caller forgets to check); `exceptions nocatch` runs the bad
// day with no catch in main, so the exception reaches the top of the stack and the program
// is terminated.

#include <iostream>
#include <stdexcept>
#include <string>

// [log]
struct Log {                             // a local object: opened on the way in, closed on the way out
    explicit Log(std::string where) : where_(std::move(where)) {
        std::cout << "open  " << where_ << "\n";
    }
    // [dtor]
    ~Log() {
        std::cout << "close " << where_ << "\n";
    }
    // [dtor]
    std::string where_;
};
// [log]

std::string sensorText(int cycle) {      // what the sensor sent: a number, then one day some text
    return cycle == 0 ? "73" : "ERR";
}

bool isNumber(const std::string& text) {
    return !text.empty() && text.find_first_not_of("0123456789") == std::string::npos;
}

// [sentinel]
int parseLevelOrMinusOne(const std::string& text) {
    if (!isNumber(text)) {
        return -1;   // and every caller must check
    }
    return std::stoi(text);
}
// [sentinel]

void runCycleOldWay() {                  // the old way, with the check forgotten on this floor
    int level = parseLevelOrMinusOne(sensorText(1));
    std::cout << (level < 50 ? "pump on" : "pump off") << "\n";
}

// [parse]
int parseLevel(const std::string& text) {
    if (!isNumber(text)) {
        throw std::invalid_argument("not a number: " + text);
    }
    return std::stoi(text);
}
// [parse]

// [read]
int readLevel(int cycle) {
    Log log("readLevel");
    return parseLevel(sensorText(cycle));
}
// [read]

// [cycle]
void runCycle(int cycle) {
    Log log("runCycle");
    int level = readLevel(cycle);
    std::cout << (level < 50 ? "pump on" : "pump off") << "\n";
}
// [cycle]

int main(int argc, char** argv) {
    if (argc > 1 && std::string(argv[1]) == "old") {
        runCycleOldWay();                // the film's second beat: a special value, unchecked
        return 0;
    }
    if (argc > 1) {                      // the film's last beat: nobody catches
        runCycle(1);
    }
    for (int cycle = 0; cycle < 2; ++cycle) {
        // [main]
        try {
            runCycle(cycle);
        } catch (const std::invalid_argument& e) {
            std::cout << "caught: " << e.what() << "\n";
        }
        // [main]
    }
}
