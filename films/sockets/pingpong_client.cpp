#include <simple_socket/TCPSocket.hpp>

using namespace simple_socket;

int main() {
    TCPClientContext ctx;
    auto conn = ctx.connect("127.0.0.1", 8080);

    conn->write("ping");                          // two writes, back to back
    conn->write("pong");
}
