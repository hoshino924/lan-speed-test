#!/usr/bin/env python3
"""English-output wrapper for the LAN network test client."""

import argparse
import json
import statistics

from client import (
    duration_download,
    duration_upload,
    fixed_download,
    fixed_upload,
    mbps,
    open_connection,
    percentile,
    send_message,
    tcp_latency,
    udp_loss_test,
)


def main():
    parser = argparse.ArgumentParser(description="LAN performance test client")
    parser.add_argument("server", help="Server IP address or hostname")
    parser.add_argument("--port", type=int, default=5201, help="TCP port")
    parser.add_argument("--duration", type=float, default=10, help="Test duration per direction")
    parser.add_argument("--size-mb", type=int, help="Fixed test size in MiB; overrides --duration")
    parser.add_argument("--pings", type=int, default=20, help="Number of TCP latency tests")
    parser.add_argument("--udp-count", type=int, default=100, help="Number of UDP packets")
    parser.add_argument("--udp-interval", type=float, default=0.01, help="UDP packet interval in seconds")
    parser.add_argument("--udp-timeout", type=float, default=0.5, help="Timeout per UDP packet in seconds")
    args = parser.parse_args()

    try:
        conn, hello = open_connection(args.server, args.port)
        with conn:
            token = bytes.fromhex(hello["token"])
            udp_port = int(hello["udp_port"])
            print(f"Connected to {args.server}:{args.port}")
            samples = tcp_latency(conn, args.pings)
            print(
                f"TCP latency: average {statistics.mean(samples):.2f} ms, "
                f"minimum {min(samples):.2f} ms, P95 {percentile(samples, 0.95):.2f} ms, "
                f"maximum {max(samples):.2f} ms"
            )
            if args.size_mb:
                byte_count = args.size_mb * 1024 * 1024
                received, download_seconds = fixed_download(conn, byte_count)
                sent, upload_seconds = fixed_upload(conn, byte_count)
            else:
                received, download_seconds = duration_download(args.server, args.port, args.duration)
                sent, upload_seconds = duration_upload(args.server, args.port, args.duration)
            print(
                f"Download speed: {mbps(received, download_seconds):.2f} Mbps "
                f"({received / 1024 / 1024:.1f} MiB, {download_seconds:.2f} seconds)"
            )
            print(
                f"Upload speed: {mbps(sent, upload_seconds):.2f} Mbps "
                f"({sent / 1024 / 1024:.1f} MiB, {upload_seconds:.2f} seconds)"
            )
            udp_received, udp_rtts = udp_loss_test(
                args.server, udp_port, token, args.udp_count, args.udp_interval, args.udp_timeout
            )
            lost = args.udp_count - udp_received
            detail = (
                f", average successful-packet RTT {statistics.mean(udp_rtts):.2f} ms"
                if udp_rtts else ""
            )
            print(
                f"UDP packet loss: {lost / args.udp_count * 100:.2f}% "
                f"(sent {args.udp_count}, received {udp_received}, lost {lost}{detail})"
            )
            send_message(conn, {"type": "close"})
    except (OSError, ConnectionError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Test failed: {exc}")


if __name__ == "__main__":
    main()
