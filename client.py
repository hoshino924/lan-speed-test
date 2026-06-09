#!/usr/bin/env python3
"""LAN network test client using only the Python standard library."""

import argparse
import json
import math
import socket
import statistics
import struct
import time


HEADER = struct.Struct("!I")
UDP_HEADER = struct.Struct("!16sI")
BUFFER_SIZE = 1024 * 1024
MAX_CONTROL_SIZE = 64 * 1024


def recv_exact(conn, size):
    chunks = []
    while size:
        chunk = conn.recv(size)
        if not chunk:
            raise ConnectionError("connection closed unexpectedly")
        chunks.append(chunk)
        size -= len(chunk)
    return b"".join(chunks)


def recv_message(conn):
    size = HEADER.unpack(recv_exact(conn, HEADER.size))[0]
    if size > MAX_CONTROL_SIZE:
        raise ValueError("control message is too large")
    return json.loads(recv_exact(conn, size).decode("utf-8"))


def send_message(conn, message):
    payload = json.dumps(message, ensure_ascii=False).encode("utf-8")
    conn.sendall(HEADER.pack(len(payload)) + payload)


def open_connection(host, port, timeout=60):
    conn = socket.create_connection((host, port), timeout=10)
    conn.settimeout(timeout)
    hello = recv_message(conn)
    if hello.get("type") != "hello":
        conn.close()
        raise RuntimeError("invalid server greeting")
    return conn, hello


def percentile(values, fraction):
    ordered = sorted(values)
    index = min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def tcp_latency(conn, count):
    samples = []
    for sequence in range(count):
        started = time.perf_counter()
        send_message(conn, {"type": "ping", "sequence": sequence})
        if recv_message(conn).get("type") != "pong":
            raise RuntimeError("unexpected ping response")
        samples.append((time.perf_counter() - started) * 1000)
    return samples


def fixed_download(conn, byte_count):
    send_message(conn, {"type": "download", "bytes": byte_count})
    if recv_message(conn).get("type") != "download_ready":
        raise RuntimeError("server refused download test")
    started = time.perf_counter()
    received = 0
    while received < byte_count:
        chunk = conn.recv(min(BUFFER_SIZE, byte_count - received))
        if not chunk:
            raise ConnectionError("connection closed during download")
        received += len(chunk)
    return received, time.perf_counter() - started


def fixed_upload(conn, byte_count):
    send_message(conn, {"type": "upload", "bytes": byte_count})
    if recv_message(conn).get("type") != "upload_ready":
        raise RuntimeError("server refused upload test")
    block = b"\0" * BUFFER_SIZE
    started = time.perf_counter()
    remaining = byte_count
    while remaining:
        chunk = block if remaining >= BUFFER_SIZE else block[:remaining]
        conn.sendall(chunk)
        remaining -= len(chunk)
    response = recv_message(conn)
    elapsed = max(float(response["seconds"]), time.perf_counter() - started)
    return int(response["bytes"]), elapsed


def duration_download(host, port, duration):
    conn, _ = open_connection(host, port, duration + 30)
    with conn:
        send_message(conn, {"type": "download_duration", "seconds": duration})
        if recv_message(conn).get("type") != "download_ready":
            raise RuntimeError("server refused download test")
        started = time.perf_counter()
        received = 0
        while True:
            chunk = conn.recv(BUFFER_SIZE)
            if not chunk:
                break
            received += len(chunk)
        return received, time.perf_counter() - started


def duration_upload(host, port, duration):
    conn, _ = open_connection(host, port, duration + 30)
    with conn:
        send_message(conn, {"type": "upload_duration", "seconds": duration})
        if recv_message(conn).get("type") != "upload_ready":
            raise RuntimeError("server refused upload test")
        block = b"\0" * BUFFER_SIZE
        started = time.perf_counter()
        deadline = started + duration
        sent = 0
        while time.perf_counter() < deadline:
            conn.sendall(block)
            sent += len(block)
        conn.shutdown(socket.SHUT_WR)
        response = recv_message(conn)
        elapsed = max(float(response["seconds"]), time.perf_counter() - started)
        return int(response["bytes"]), elapsed


def udp_loss_test(host, port, token, count, interval, timeout):
    rtts = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        for sequence in range(count):
            packet = UDP_HEADER.pack(token, sequence)
            started = time.perf_counter()
            sock.sendto(packet, (host, port))
            sock.settimeout(timeout)
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                data = b""
            if len(data) >= UDP_HEADER.size:
                response_token, response_sequence = UDP_HEADER.unpack(data[:UDP_HEADER.size])
                if response_token == token and response_sequence == sequence:
                    rtts.append((time.perf_counter() - started) * 1000)
            if interval:
                time.sleep(interval)
    return len(rtts), rtts


def mbps(byte_count, seconds):
    return byte_count * 8 / seconds / 1_000_000


def main():
    parser = argparse.ArgumentParser(description="内网性能测试客户端")
    parser.add_argument("server", help="服务端 IP 或主机名")
    parser.add_argument("--port", type=int, default=5201, help="TCP 端口")
    parser.add_argument("--duration", type=float, default=10, help="每个方向测速秒数")
    parser.add_argument("--size-mb", type=int, help="固定测试 MiB，会覆盖 --duration")
    parser.add_argument("--pings", type=int, default=20, help="TCP 延迟测试次数")
    parser.add_argument("--udp-count", type=int, default=100, help="UDP 数据包数量")
    parser.add_argument("--udp-interval", type=float, default=0.01, help="UDP 发包间隔秒数")
    parser.add_argument("--udp-timeout", type=float, default=0.5, help="每个 UDP 包超时秒数")
    args = parser.parse_args()

    try:
        conn, hello = open_connection(args.server, args.port)
        with conn:
            token = bytes.fromhex(hello["token"])
            udp_port = int(hello["udp_port"])
            print(f"已连接到 {args.server}:{args.port}")

            samples = tcp_latency(conn, args.pings)
            print(
                f"TCP 延迟: 平均 {statistics.mean(samples):.2f} ms, "
                f"最小 {min(samples):.2f} ms, P95 {percentile(samples, 0.95):.2f} ms, "
                f"最大 {max(samples):.2f} ms"
            )

            if args.size_mb:
                byte_count = args.size_mb * 1024 * 1024
                received, download_seconds = fixed_download(conn, byte_count)
                sent, upload_seconds = fixed_upload(conn, byte_count)
            else:
                received, download_seconds = duration_download(
                    args.server, args.port, args.duration
                )
                sent, upload_seconds = duration_upload(
                    args.server, args.port, args.duration
                )

            print(
                f"下载速度: {mbps(received, download_seconds):.2f} Mbps "
                f"({received / 1024 / 1024:.1f} MiB, {download_seconds:.2f} 秒)"
            )
            print(
                f"上传速度: {mbps(sent, upload_seconds):.2f} Mbps "
                f"({sent / 1024 / 1024:.1f} MiB, {upload_seconds:.2f} 秒)"
            )

            udp_received, udp_rtts = udp_loss_test(
                args.server, udp_port, token, args.udp_count,
                args.udp_interval, args.udp_timeout
            )
            lost = args.udp_count - udp_received
            detail = (
                f", 成功包平均 RTT {statistics.mean(udp_rtts):.2f} ms"
                if udp_rtts else ""
            )
            print(
                f"UDP 丢包率: {lost / args.udp_count * 100:.2f}% "
                f"(发送 {args.udp_count}, 收到 {udp_received}, 丢失 {lost}{detail})"
            )
            send_message(conn, {"type": "close"})
    except (OSError, ConnectionError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"测试失败: {exc}")


if __name__ == "__main__":
    main()
