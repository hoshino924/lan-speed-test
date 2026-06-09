# LAN Latency, Speed, and Packet Loss Test

[简体中文](README.md)

A dependency-free Python client/server tool for measuring TCP latency, upload and download throughput, and UDP packet loss between two computers on a LAN.

## Usage

Start the server:

```powershell
python server.py
```

Run the client, replacing the IP address with the server's LAN IP:

```powershell
python client.py 192.168.1.10
```

By default, download and upload tests each run for 10 seconds. Use a longer duration for more stable results:

```powershell
python client.py 192.168.1.10 --duration 30
```

You can also test using a fixed amount of data. This example transfers approximately 2 GiB in each direction:

```powershell
python client.py 192.168.1.10 --size-mb 2048
```

Test data is generated in memory. No temporary file is created, so disk performance does not affect the result.

Additional examples:

```powershell
python client.py 192.168.1.10 --duration 20 --pings 50 --udp-count 500
python server.py --port 6001 --udp-port 6002
python client.py 192.168.1.10 --port 6001
```

## Notes

- Allow TCP port `5201` and UDP port `5202` through the server firewall.
- On Windows, allow Python to access private networks when prompted.
- A loopback test measures the local TCP/IP stack and Python processing performance, not the physical network adapter.
- UDP loss is measured with request/echo packets. A lost request or response is counted as packet loss.
- Mbps means one million bits per second. MiB means `1024 * 1024` bytes.

## License

This project is licensed under the [MIT License](LICENSE).
