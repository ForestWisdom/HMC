#!/usr/bin/env python3
from __future__ import annotations

import argparse
import socket
import struct
import time
from dataclasses import dataclass
from typing import Any, Optional

import hmc


def _try_import_torch():
    try:
        import torch  # type: ignore

        return torch
    except Exception:
        return None


def _sendall(sock: socket.socket, data: bytes) -> None:
    mv = memoryview(data)
    while mv:
        n = sock.send(mv)
        if n <= 0:
            raise ConnectionError("control socket send failed")
        mv = mv[n:]


def _recvall(sock: socket.socket, n: int) -> bytes:
    out = bytearray(n)
    mv = memoryview(out)
    got = 0
    while got < n:
        r = sock.recv(n - got)
        if not r:
            raise ConnectionError("control socket recv failed")
        mv[got : got + len(r)] = r
        got += len(r)
    return bytes(out)


def ctrl_send(sock: socket.socket, payload: bytes) -> None:
    _sendall(sock, struct.pack("!I", len(payload)))
    _sendall(sock, payload)


def ctrl_recv(sock: socket.socket) -> bytes:
    (n,) = struct.unpack("!I", _recvall(sock, 4))
    return _recvall(sock, n)


def parse_sizes(s: str) -> list[int]:
    out: list[int] = []
    for part in s.split(","):
        p = part.strip().lower()
        if not p:
            continue
        mul = 1
        if p.endswith("k"):
            mul = 1024
            p = p[:-1]
        elif p.endswith("m"):
            mul = 1024 * 1024
            p = p[:-1]
        elif p.endswith("g"):
            mul = 1024 * 1024 * 1024
            p = p[:-1]
        out.append(int(float(p) * mul))
    return out


@dataclass
class Result:
    conn: str
    size: int
    iters: int
    seconds: float
    gbps: float


def to_gbps(total_bytes: float, seconds: float) -> float:
    return (total_bytes * 8.0) / seconds / 1e9


def run_server(args: argparse.Namespace) -> None:
    torch = _try_import_torch()
    if args.gpu and torch is None:
        raise SystemExit("GPU mode requires torch with CUDA")

    mem_type = hmc.MemoryType.NVIDIA_GPU if args.gpu else hmc.MemoryType.CPU
    sess = hmc.create_session(
        device_id=args.device,
        buffer_size=args.buffer_size,
        mem_type=mem_type,
        num_chs=args.num_chs,
        local_ip=args.bind_ip,
    )
    sess.init_server(
        bind_ip=args.bind_ip,
        ucx_port=args.ucx_port,
        rdma_port=args.rdma_port,
        ctrl_tcp_port=args.ctrl_tcp_port,
        self_id=args.self_rank,
        ctrl_uds_dir=args.ctrl_uds_dir,
    )

    listen = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listen.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listen.bind((args.ctrl_bind_ip, args.ctrl_port))
    listen.listen(1)
    conn, addr = listen.accept()
    conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    print(f"[server] ctrl accepted: {addr[0]}:{addr[1]}")

    tmp = bytearray(64)
    try:
        while True:
            msg = ctrl_recv(conn)
            if msg == b"BYE":
                ctrl_send(conn, b"OK")
                break

            if msg.startswith(b"BEGIN "):
                ctrl_send(conn, b"OK")
                continue

            if msg.startswith(b"DONE "):
                if args.verify:
                    parts = msg.decode().split()
                    size = int(parts[1])
                    n = min(size, 64)
                    sess.buf.get_into(tmp, nbytes=n, offset=0)
                    ok = all(x == 0x41 for x in tmp[:n])
                    print(f"[server] verify size={size}: {'PASS' if ok else 'FAIL'}")
                ctrl_send(conn, b"OK")
                continue

            ctrl_send(conn, b"ERR")
    finally:
        conn.close()
        listen.close()


def run_client(args: argparse.Namespace) -> None:
    torch = _try_import_torch()
    if args.gpu and torch is None:
        raise SystemExit("GPU mode requires torch with CUDA")

    mem_type = hmc.MemoryType.NVIDIA_GPU if args.gpu else hmc.MemoryType.CPU
    sess = hmc.create_session(
        device_id=args.device,
        buffer_size=args.buffer_size,
        mem_type=mem_type,
        num_chs=args.num_chs,
        local_ip=args.local_ip,
    )
    ctrl = socket.create_connection((args.ctrl_ip, args.ctrl_port))
    ctrl.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    sizes = parse_sizes(args.sizes)
    cases: list[tuple[str, hmc.ConnType, int]] = []
    if args.conn in ("rdma", "both"):
        cases.append(("rdma", hmc.ConnType.RDMA, args.rdma_port))
    if args.conn in ("ucx", "both"):
        cases.append(("ucx", hmc.ConnType.UCX, args.ucx_port))

    payload = b""
    payload_size = 0
    gpu_buf: Optional[Any] = None
    gpu_ptr = 0
    results: list[Result] = []

    try:
        for conn_name, conn_type, port in cases:
            sess.connect(
                peer_id=args.peer_rank,
                self_id=args.self_rank,
                peer_ip=args.server_ip,
                data_port=port,
                ctrl_tcp_port=args.ctrl_tcp_port,
                uds_dir=args.ctrl_uds_dir,
                conn=conn_type,
            )

            for sz in sizes:
                if sz > args.buffer_size:
                    raise ValueError(f"size {sz} > buffer_size {args.buffer_size}")

                if args.gpu:
                    if gpu_buf is None or int(gpu_buf.numel()) < sz:
                        gpu_buf = torch.empty((sz,), device=f"cuda:{args.device}", dtype=torch.uint8)
                        gpu_ptr = int(gpu_buf.data_ptr())
                    gpu_buf[:sz].fill_(0x41)
                    sess.buf.buffer_put_gpu_ptr(gpu_ptr, nbytes=sz, offset=0)
                else:
                    if payload_size != sz:
                        payload = bytes([0x41]) * sz
                        payload_size = sz
                    sess.buf.put(payload, nbytes=sz, offset=0, device=None)

                ctrl_send(ctrl, f"BEGIN {sz} {conn_name}".encode())
                _ = ctrl_recv(ctrl)

                for _ in range(args.warmup):
                    sess.put_pipeline(
                        args.server_ip,
                        port,
                        0,
                        0,
                        sz,
                        chunk_size=args.chunk_size,
                        max_inflight=args.max_inflight,
                        conn=conn_type,
                    )

                t0 = time.perf_counter()
                for _ in range(args.iters):
                    sess.put_pipeline(
                        args.server_ip,
                        port,
                        0,
                        0,
                        sz,
                        chunk_size=args.chunk_size,
                        max_inflight=args.max_inflight,
                        conn=conn_type,
                    )
                elapsed = time.perf_counter() - t0

                ctrl_send(ctrl, f"DONE {sz} {conn_name}".encode())
                _ = ctrl_recv(ctrl)

                total_bytes = float(sz * args.iters)
                g = to_gbps(total_bytes, elapsed)
                results.append(Result(conn_name, sz, args.iters, elapsed, g))
                print(
                    f"[client] {conn_name} size={sz} iters={args.iters} "
                    f"time={elapsed:.4f}s bw={g:.2f} Gbps"
                )

            sess.disconnect(args.server_ip, port, conn=conn_type)

        ctrl_send(ctrl, b"BYE")
        _ = ctrl_recv(ctrl)
    finally:
        ctrl.close()

    print("\nSummary")
    print("conn   size(bytes)   iters   gbps")
    for r in results:
        print(f"{r.conn:<5}  {r.size:<11}  {r.iters:<5}  {r.gbps:>7.2f}")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="HMC one-sided write bandwidth benchmark")
    ap.add_argument("--role", choices=["server", "client"], required=True)
    ap.add_argument("--bind-ip", default="0.0.0.0")
    ap.add_argument("--local-ip", default="127.0.0.1")
    ap.add_argument("--server-ip", default="127.0.0.1")
    ap.add_argument("--ctrl-bind-ip", default="0.0.0.0")
    ap.add_argument("--ctrl-ip", default="127.0.0.1")
    ap.add_argument("--ctrl-port", type=int, default=20300)
    ap.add_argument("--ctrl-tcp-port", type=int, default=2027)
    ap.add_argument("--ctrl-uds-dir", default="/tmp")
    ap.add_argument("--rdma-port", type=int, default=2025)
    ap.add_argument("--ucx-port", type=int, default=2026)
    ap.add_argument("--conn", choices=["rdma", "ucx", "both"], default="rdma")
    ap.add_argument("--sizes", default="1m,4m,16m,64m")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--warmup", type=int, default=20)
    ap.add_argument("--buffer-size", type=int, default=128 * 1024 * 1024)
    ap.add_argument("--chunk-size", type=int, default=4 * 1024 * 1024)
    ap.add_argument("--max-inflight", type=int, default=64)
    ap.add_argument("--num-chs", type=int, default=1)
    ap.add_argument("--gpu", action="store_true")
    ap.add_argument("--device", type=int, default=0)
    ap.add_argument("--self-rank", type=int, default=1)
    ap.add_argument("--peer-rank", type=int, default=0)
    ap.add_argument("--verify", action="store_true")
    return ap


if __name__ == "__main__":
    args = build_parser().parse_args()
    if args.role == "server":
        run_server(args)
    else:
        run_client(args)
