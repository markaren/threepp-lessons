#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <iostream>

int main() {
    int server = socket(AF_INET, SOCK_STREAM, 0);   // SOCK_STREAM = TCP

    int yes = 1;
    setsockopt(server, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));  // reuse the port right away

    sockaddr_in addr{};
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = INADDR_ANY;               // accept on any interface
    addr.sin_port = htons(8080);                     // port 8080, network byte order

    bind(server, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
    listen(server, 1);                               // queue up to 1 pending connection
    std::cout << "listening on port 8080...\n";

    int client = accept(server, nullptr, nullptr);   // blocks until someone connects

    char buffer[1024];
    ssize_t n = recv(client, buffer, sizeof(buffer), 0);
    send(client, buffer, n, 0);                      // echo the bytes straight back

    close(client);
    close(server);
}
