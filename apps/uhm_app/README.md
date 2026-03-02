
export SERVER_IP=192.168.2.244
export CLIENT_IP=192.168.2.244
export TCP_SERVER_IP=192.168.2.244

# optional defaults (used only when SERVER_IP/CLIENT_IP/TCP_SERVER_IP are unset)
export DEFAULT_SERVER_IP=192.168.2.248
export DEFAULT_CLIENT_IP=192.168.2.249
export DEFAULT_TCP_IP=192.168.2.248

CUDA_VISIBLE_DEVICES=5 ./build/apps/uhm_app/uhm_server --mode uhm
CUDA_VISIBLE_DEVICES=6 ./build/apps/uhm_app/uhm_client --mode uhm > uhm.log 2>&1

CUDA_VISIBLE_DEVICES=5 ./build/apps/uhm_app/uhm_server --mode g2h2g
CUDA_VISIBLE_DEVICES=6 ./build/apps/uhm_app/uhm_client --mode g2h2g > g2h2g.log 2>&1

CUDA_VISIBLE_DEVICES=5 ./build/apps/uhm_app/uhm_server --mode rdma_cpu
CUDA_VISIBLE_DEVICES=6 ./build/apps/uhm_app/uhm_client --mode rdma_cpu > rdma_cpu.log 2>&1

CUDA_VISIBLE_DEVICES=5 ./build/apps/uhm_app/uhm_server --mode serial
CUDA_VISIBLE_DEVICES=6 ./build/apps/uhm_app/uhm_client --mode serial > serial.log 2>&1

export UCX_NET_DEVICES=mlx5_0:1,mlx5_3:1 # 如果遇到连接问题，换网卡，ucx_info -d
export UCX_TLS=rc,self,sm,tcp
CUDA_VISIBLE_DEVICES=5 ./build/apps/uhm_app/uhm_server --mode ucx
CUDA_VISIBLE_DEVICES=6 ./build/apps/uhm_app/uhm_client --mode ucx > ucx.log 2>&1

# one-sided write high-performance mode (C++ / RDMA pipeline)
export NUM_CHANNELS=4
export PIPELINE_CHUNK=$((4*1024*1024))
export PIPELINE_INFLIGHT=128

# RDMA core tuning
export HMC_RDMA_CQ_CAPACITY=1024
export HMC_RDMA_MAX_WR=1024
export HMC_RDMA_PIPELINE_SIGNAL_INTERVAL=16
export HMC_RDMA_PIPELINE_INFLIGHT=128
export HMC_RDMA_PATH_MTU=4096

CUDA_VISIBLE_DEVICES=5 ./build/apps/uhm_app/uhm_server --mode write
CUDA_VISIBLE_DEVICES=6 ./build/apps/uhm_app/uhm_client --mode write > write.log 2>&1

# CPU ConnBuffer write benchmark (isolates RDMA path from MLU memory path)
CUDA_VISIBLE_DEVICES=5 ./build/apps/uhm_app/uhm_server --mode write_cpu
CUDA_VISIBLE_DEVICES=6 ./build/apps/uhm_app/uhm_client --mode write_cpu > write_cpu.log 2>&1

# staged path: MLU -> CPU staging + RDMA write
export BUFFER_SIZE_MB=128
export STAGE_CHUNK=$((8*1024*1024))
export STAGE_SLOTS=0   # 0=auto (buffer_size / STAGE_CHUNK)
export STAGE_SRC_WINDOW_MB=32
CUDA_VISIBLE_DEVICES=5 ./build/apps/uhm_app/uhm_server --mode write_stage
CUDA_VISIBLE_DEVICES=6 ./build/apps/uhm_app/uhm_client --mode write_stage > write_stage.log 2>&1

# UHM mode tuning (optional)
export HMC_UHM_CHUNK=$((4*1024*1024))
export HMC_UHM_SIGNAL_INTERVAL=16
export HMC_UHM_PENDING_SIGNAL=8

# test size range: 2^MIN_POWER .. 2^MAX_POWER bytes
export MIN_POWER=5
export MAX_POWER=29
