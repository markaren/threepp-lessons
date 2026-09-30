#include <simple_socket/TCPSocket.hpp>
#include <iostream>
#include <string>
#include <vector>

using namespace simple_socket;

int main() {
    TCPClientContext ctx;
    auto conn = ctx.connect("127.0.0.1", 8080);   // reach out to the server

    conn->write("hello");

    std::vector<uint8_t> buffer(1024);
    int n = conn->read(buffer);
    std::string reply(buffer.begin(), buffer.begin() + n);
    std::cout << "server replied: " << reply << "\n";
}   // conn closes itself here (RAII)
