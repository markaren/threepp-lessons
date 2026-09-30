#include <simple_socket/TCPSocket.hpp>
#include <iostream>
#include <string>
#include <vector>

using namespace simple_socket;

int main() {
    TCPServer server(8080);
    auto conn = server.accept();

    std::vector<uint8_t> buffer(1024);
    int n = conn->read(buffer);                   // ONE read
    std::cout << "read " << n << " bytes: " << std::string(buffer.begin(), buffer.begin() + n) << "\n";
}
