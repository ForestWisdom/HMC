#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <thread>
#include <mpi.h>
#include <hmc.h>

int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);
    int rank, world;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &world);
    if (world != 2) { MPI_Finalize(); return 1; }

    auto buf = std::make_shared<hmc::ConnBuffer>(rank, 64*1024*1024,
                                                  hmc::MemoryType::CAMBRICON_MLU);
    auto comm = std::make_shared<hmc::Communicator>(buf);

    std::string uds = "/tmp/hmc_ctrl_rank_" + std::to_string(rank) + ".sock";
    comm->initCtrlServer("127.0.0.1", 0, uds);
    int peer = 1 - rank;
    std::string peer_uds = "/tmp/hmc_ctrl_rank_" + std::to_string(peer) + ".sock";
    hmc::Communicator::CtrlLink link;
    link.transport = hmc::Communicator::CtrlTransport::UDS;
    link.uds_path = peer_uds;
    if (rank < peer) std::this_thread::sleep_for(std::chrono::milliseconds(500));
    comm->connectCtrl(peer, rank, link);

    // Test connectP2p (UDS handle exchange)
    hmc::status_t st = comm->connectP2p(peer, rank, rank,
                                         hmc::MemoryType::CAMBRICON_MLU);
    printf("[%d] connectP2p (UDS exchange): %s\n", rank,
           st == hmc::status_t::SUCCESS ? "OK" : "FAIL");

    if (st == hmc::status_t::SUCCESS) {
        size_t sz = 64*1024*1024;
        if (rank == 0) {
            auto *h = new char[sz]; memset(h, 0xAA, sz);
            buf->writeFromCpu(h, sz, 0); delete[] h;
        }
        MPI_Barrier(MPI_COMM_WORLD);
        if (rank == 0) comm->putP2p(peer, 0, 0, sz);
        if (rank == 1) comm->getP2p(peer, 0, 0, sz);
        MPI_Barrier(MPI_COMM_WORLD);
        if (rank == 1) {
            auto *h = new char[sz];
            buf->readToCpu(h, sz, 0);
            bool ok = (h[0] == (char)0xAA && h[sz-1] == (char)0xAA);
            printf("[%d] verify: %s\n", rank, ok ? "OK" : "FAIL");
            delete[] h;
        }
    }
    comm->closeCtrl();
    MPI_Finalize();
    return 0;
}
