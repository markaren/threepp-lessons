#include <simple_socket/TCPSocket.hpp>
#include <iostream>
#include <vector>

using namespace simple_socket;

int main() {
    TCPServer server(8080);                       // claim port 8080 and listen
    std::cout << "listening on port 8080...\n";

    auto conn = server.accept();                  // block until a client connects

    std::vector<uint8_t> buffer(1024);
    int n = conn->read(buffer);                   // read whatever arrived
    conn->write(buffer.data(), n);                // echo it back
    // conn and server close themselves via RAII
}
