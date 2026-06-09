#!/usr/bin/env python3
"""LAN network test server using only the Python standard library."""

import argparse
import json
import secrets
import socket
import struct
import threading
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


def send_fixed_download(conn, byte_count):
    block = b"\0" * BUFFER_SIZE
    remaining = byte_count
    while remaining:
        chunk = block if remaining >= BUFFER_SIZE else block[:remaining]
        conn.sendall(chunk)
        remaining -= len(chunk)


def receive_fixed_upload(conn, byte_count):
    received = 0
    while received < byte_count:
        chunk = conn.recv(min(BUFFER_SIZE, byte_count - received))
        if not chunk:
            raise ConnectionError("connection closed during upload")
        received += len(chunk)
    return received


def tcp_client(conn, address, udp_port):
    conn.settimeout(60)
    token = secrets.token_bytes(16)
    try:
        send_message(conn, {"type": "hello", "udp_port": udp_port, "token": token.hex()})
        while True:
            request = recv_message(conn)
            action = request.get("type")

            if action == "ping":
                send_message(conn, {"type": "pong", "sequence": request.get("sequence")})

            elif action == "download":
                byte_count = max(0, int(request.get("bytes", 0)))
                send_message(conn, {"type": "download_ready", "bytes": byte_count})
                send_fixed_download(conn, byte_count)

            elif action == "upload":
                byte_count = max(0, int(request.get("bytes", 0)))
                send_message(conn, {"type": "upload_ready", "bytes": byte_count})
                started = time.perf_counter()
                received = receive_fixed_upload(conn, byte_count)
                send_message(
                    conn,
                    {
                        "type": "upload_result",
                        "bytes": received,
                        "seconds": time.perf_counter() - started,
                    },
                )

            elif action == "download_duration":
                duration = max(0.1, float(request.get("seconds", 10)))
                send_message(conn, {"type": "download_ready", "seconds": duration})
                block = b"\0" * BUFFER_SIZE
                deadline = time.perf_counter() + duration
                while time.perf_counter() < deadline:
                    conn.sendall(block)
                break

            elif action == "upload_duration":
                duration = max(0.1, float(request.get("seconds", 10)))
                send_message(conn, {"type": "upload_ready", "seconds": duration})
                started = time.perf_counter()
                received = 0
                while True:
                    chunk = conn.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    received += len(chunk)
                send_message(
                    conn,
                    {
                        "type": "upload_result",
                        "bytes": received,
                        "seconds": time.perf_counter() - started,
                    },
                )
                break

            elif action == "close":
                break
            else:
                send_message(conn, {"type": "error", "message": "unknown request"})
    except (ConnectionError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[TCP] {address[0]}:{address[1]} disconnected: {exc}")
    finally:
        conn.close()


def tcp_server(host, port, udp_port, stop_event):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen()
        server.settimeout(1)
        print(f"[TCP] Listening on {host}:{port}")
        while not stop_event.is_set():
            try:
                conn, address = server.accept()
            except socket.timeout:
                continue
            threading.Thread(
                target=tcp_client, args=(conn, address, udp_port), daemon=True
            ).start()


def udp_server(host, port, stop_event):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
        server.bind((host, port))
        server.settimeout(1)
        print(f"[UDP] Listening on {host}:{port}")
        while not stop_event.is_set():
            try:
                data, address = server.recvfrom(65535)
            except socket.timeout:
                continue
            if len(data) >= UDP_HEADER.size:
                server.sendto(data[:UDP_HEADER.size], address)


def main():
    parser = argparse.ArgumentParser(description="内网性能测试服务端")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=5201, help="TCP 端口")
    parser.add_argument("--udp-port", type=int, default=5202, help="UDP 端口")
    args = parser.parse_args()

    stop_event = threading.Event()
    udp_thread = threading.Thread(
        target=udp_server, args=(args.host, args.udp_port, stop_event), daemon=True
    )
    udp_thread.start()
    try:
        tcp_server(args.host, args.port, args.udp_port, stop_event)
    except KeyboardInterrupt:
        print("\n正在停止服务端...")
    finally:
        stop_event.set()
        udp_thread.join(timeout=2)


if __name__ == "__main__":
    main()
