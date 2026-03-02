# 编译
bash build.sh

# 环境变量
export NUM_CHANNELS=4
export MIN_POWER=23
export MAX_POWER=35
export BUFFER_SIZE_MB=32
export STAGE_SRC_WINDOW_MB=32
export STAGE_CHUNK=$((8*1024*1024))
export STAGE_SLOTS=8
export HMC_RDMA_CQ_CAPACITY=1024
export HMC_RDMA_MAX_WR=1024
export HMC_RDMA_PATH_MTU=1024
export DEFAULT_SERVER_IP=192.168.2.248
export DEFAULT_CLIENT_IP=192.168.2.249
export DEFAULT_TCP_IP=192.168.2.248

# 测试
./build/apps/uhm_app/uhm_server --mode write_stage
./build/apps/uhm_app/uhm_client --mode write_stage