# 内网延迟、网速和丢包率测试工具

[English](README_EN.md)

这是一个仅使用 Python 标准库的服务端/客户端工具，可测试 TCP 延迟、上下行速度和 UDP 丢包率。

## 环境要求

使用前需要安装 **Python 3.8 或更高版本**。可从 [Python 官网](https://www.python.org/downloads/) 下载；安装 Windows 版本时，请勾选 `Add Python to PATH`。

## 使用方法

### 中文版本

服务端运行：

```powershell
python server.py
```

客户端运行，其中 `192.168.1.10` 替换为服务端内网 IP：

```powershell
python client.py 192.168.1.10
```

### 英文版本

服务端运行：

```powershell
python server_EN.py
```

客户端运行，其中 `192.168.1.10` 替换为服务端内网 IP：

```powershell
python client_EN.py 192.168.1.10
```

默认下载和上传各持续测试 10 秒。延长至 30 秒可获得更稳定的结果：

```powershell
python client.py 192.168.1.10 --duration 30
```

也可以按固定数据量测试，例如每个方向传输约 2 GiB：

```powershell
python client.py 192.168.1.10 --size-mb 2048
```

测试数据直接在内存中生成，不创建临时文件，因此不会把磁盘读写速度误算成网络速度。

其他参数示例：

```powershell
python client.py 192.168.1.10 --duration 20 --pings 50 --udp-count 500
python server.py --port 6001 --udp-port 6002
python client.py 192.168.1.10 --port 6001
```

## 注意事项

- 服务端防火墙需要允许 TCP `5201` 和 UDP `5202`。
- Windows 首次运行服务端时，请允许 Python 访问专用网络。
- 回环地址测试的是本机 TCP/IP 协议栈和 Python 处理能力，不代表网卡速度。
- UDP 丢包测试使用请求/回显方式，请求包或回包任一方向丢失都会记为丢包。
- Mbps 表示每秒百万位，MiB 表示 `1024 * 1024` 字节。

## 许可证

本项目采用 [MIT License](LICENSE)。
