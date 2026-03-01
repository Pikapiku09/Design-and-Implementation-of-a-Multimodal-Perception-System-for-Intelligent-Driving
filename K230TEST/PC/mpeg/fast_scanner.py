#!/usr/bin/env python3
"""
极速连接测试脚本 - 直接运行，无需GUI
"""
import socket
import time
import threading
from queue import Queue


def quick_connect_k230():
    """极速连接K230（纯命令行版本）"""
    print("=" * 60)
    print("K230 极速连接测试")
    print("=" * 60)

    port = 8888
    found_ip = None

    # 你的K230固定网段
    network = "192.168.137"

    print(f"[*] 极速扫描 {network}.x ...")
    print("[*] 预计时间: 2-5秒")
    print()

    start_time = time.time()

    # 第一步：并发扫描常用地址 (1-30)
    print("[1] 扫描常用地址 (1-30)...")
    found_ip = scan_range(network, 1, 30, port)

    # 第二步：如果没找到，扫描中间范围
    if not found_ip:
        print("[2] 扫描中间地址 (50-80)...")
        found_ip = scan_range(network, 50, 80, port)

    # 第三步：如果还没找到，快速扫描剩余范围
    if not found_ip:
        print("[3] 快速扫描剩余地址...")

        # 分4批并发扫描
        ranges = [(100, 130), (150, 180), (200, 230), (1, 254)]
        for r_start, r_end in ranges:
            if found_ip:
                break
            found_ip = scan_range(network, r_start, r_end, port)

    elapsed = time.time() - start_time

    if found_ip:
        print("\n" + "=" * 60)
        print(f"[✓] 连接成功!")
        print(f"    设备IP: {found_ip}")
        print(f"    扫描时间: {elapsed:.1f}秒")
        print(f"    测试连接...")

        # 测试视频流连接
        if test_video_stream(found_ip, port):
            print(f"[✓] 视频流测试通过!")
            print(f"\n现在可以运行: python qt_client.py")
        else:
            print(f"[!] 视频流测试失败")

        print("=" * 60)
        return found_ip
    else:
        print(f"\n[✗] 未找到K230设备")
        print(f"    扫描时间: {elapsed:.1f}秒")
        print(f"\n请检查:")
        print(f"  1. K230是否开机并运行服务器")
        print(f"  2. PC和K230是否在同一WiFi")
        print(f"  3. K230的IP可能不在 {network}.x 网段")
        return None


def scan_range(network, start, end, port):
    """扫描指定范围"""
    result_queue = Queue()
    threads = []

    for i in range(start, end + 1):
        ip = f"{network}.{i}"
        thread = threading.Thread(
            target=check_single_ip,
            args=(ip, port, result_queue)
        )
        threads.append(thread)
        thread.start()

        # 控制并发数
        if len(threads) >= 50:
            for t in threads:
                t.join(timeout=0.01)
            threads = []

        # 检查是否已找到
        try:
            found = result_queue.get_nowait()
            return found
        except:
            pass

    # 等待所有线程完成
    for t in threads:
        t.join(timeout=0.01)

    # 最终检查
    try:
        return result_queue.get_nowait()
    except:
        return None


def check_single_ip(ip, port, result_queue):
    """检查单个IP"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((ip, port))
        sock.close()

        if result == 0:
            # 验证是K230服务器
            if verify_k230(ip, port):
                result_queue.put(ip)
    except:
        pass


def verify_k230(ip, port, timeout=2):
    """验证是否为K230"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))

        sock.send(b"GET / HTTP/1.0\r\n\r\n")
        response = sock.recv(1024).decode('utf-8', errors='ignore')
        sock.close()

        return "multipart/x-mixed-replace" in response
    except:
        return False


def test_video_stream(ip, port, timeout=5):
    """测试视频流"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))

        sock.send(b"GET / HTTP/1.0\r\n\r\n")

        # 读取响应头
        response = b""
        start_time = time.time()

        while time.time() - start_time < timeout:
            chunk = sock.recv(1024)
            if not chunk:
                break
            response += chunk

            if b"\r\n\r\n" in response:
                break

        sock.close()

        if response and b"multipart/x-mixed-replace" in response:
            return True
    except:
        pass

    return False


if __name__ == "__main__":
    quick_connect_k230()

    input("\n按Enter键退出...")