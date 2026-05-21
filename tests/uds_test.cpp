#include <cstdio>
#include <cstdlib>
#include <thread>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/un.h>

// Test 1: raw UDS send/recv 8 bytes (no HMC)
void test_raw_uds() {
    int fd[2];
    socketpair(AF_UNIX, SOCK_STREAM, 0, fd);
    printf("[raw] socketpair created: %d <-> %d\n", fd[0], fd[1]);

    uint64_t val = 0xDEADBEEF12345678ULL;
    write(fd[0], &val, sizeof(val));
    uint64_t recv = 0;
    read(fd[1], &recv, sizeof(recv));
    printf("[raw] sent=0x%llX recv=0x%llX -> %s\n",
           (unsigned long long)val, (unsigned long long)recv,
           val == recv ? "OK" : "FAIL");
    close(fd[0]); close(fd[1]);
}

// Test 2: separate UDS server/client
void test_uds_server_client() {
    unlink("/tmp/test_uds.sock");
    int srv = socket(AF_UNIX, SOCK_STREAM, 0);
    sockaddr_un addr{};
    addr.sun_family = AF_UNIX;
    snprintf(addr.sun_path, sizeof(addr.sun_path), "/tmp/test_uds.sock");
    bind(srv, (sockaddr*)&addr, sizeof(addr));
    listen(srv, 1);

    std::thread cli([&]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        int c = socket(AF_UNIX, SOCK_STREAM, 0);
        connect(c, (sockaddr*)&addr, sizeof(addr));

        uint64_t v = 0xCAFEBABEDEADBEEFULL;
        write(c, &v, sizeof(v));
        printf("[cli] sent 0x%llX\n", (unsigned long long)v);
        close(c);
    });

    int a = accept(srv, nullptr, nullptr);
    uint64_t recv = 0;
    read(a, &recv, sizeof(recv));
    printf("[srv] recv 0x%llX -> %s\n", (unsigned long long)recv,
           recv == 0xCAFEBABEDEADBEEFULL ? "OK" : "FAIL");
    close(a); close(srv);
    cli.join();
    unlink("/tmp/test_uds.sock");
}

int main() {
    test_raw_uds();
    test_uds_server_client();
    return 0;
}
