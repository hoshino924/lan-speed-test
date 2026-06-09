#!/usr/bin/env python3
"""English-output wrapper for the LAN network test server."""

import argparse
import threading

from server import tcp_server, udp_server


def main():
    parser = argparse.ArgumentParser(description="LAN performance test server")
    parser.add_argument("--host", default="0.0.0.0", help="Listening address")
    parser.add_argument("--port", type=int, default=5201, help="TCP port")
    parser.add_argument("--udp-port", type=int, default=5202, help="UDP port")
    args = parser.parse_args()

    stop_event = threading.Event()
    udp_thread = threading.Thread(
        target=udp_server, args=(args.host, args.udp_port, stop_event), daemon=True
    )
    udp_thread.start()
    try:
        tcp_server(args.host, args.port, args.udp_port, stop_event)
    except KeyboardInterrupt:
        print("\nStopping server...")
    finally:
        stop_event.set()
        udp_thread.join(timeout=2)


if __name__ == "__main__":
    main()
