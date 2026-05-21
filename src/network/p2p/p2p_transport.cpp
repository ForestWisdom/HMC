#include "p2p_transport.h"
#include "p2p_transport_cambricon.h"

namespace hmc {

std::unique_ptr<P2pTransport> P2pTransport::create(MemoryType type) {
  switch (type) {
  case MemoryType::CAMBRICON_MLU:
    return std::make_unique<CambriconTransport>();
  default:
    return nullptr;
  }
}

} // namespace hmc
