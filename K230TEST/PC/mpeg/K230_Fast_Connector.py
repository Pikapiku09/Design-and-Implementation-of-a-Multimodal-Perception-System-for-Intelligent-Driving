# -*- coding: utf-8 -*-
# @Time    : 2026/2/11 12:08
# @Author  : zlh
# @File    : K230_Fast_Connector.py.py
import socket
import threading
import time
import pickle
import os
from queue import Queue
from PyQt5.QtCore import QObject, pyqtSignal


class FastK230Scanner(QObject):
    """极速K230扫描器，2-5秒完成扫描"""

    # 定义信号（用于PyQt5线程安全通信）
    progress_signal = pyqtSignal(str, str)  # (消息, 类型)
    found_signal = pyqtSignal(str)  # 找到设备
    finished_signal = pyqtSignal()  # 扫描完成

    def __init__(self, port=8888):
        super().__init__()
        self.port = port
        self.scanning = False
        self.cache_file = "k230_cache.pkl"
        self.last_ip = None

        # 加载历史缓存
        self.load_cache()

    def load_cache(self):
        """加载历史连接记录"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self.last_ip = data.get('last_ip')
                    if self.last_ip:
                        self.progress_signal.emit(
                            f"加载历史IP: {self.last_ip}", "info"
                        )
            except:
                self.last_ip = None

    def save_cache(self, ip):
        """保存成功连接的IP"""
        try:
            data = {'last_ip': ip, 'timestamp': time.time()}
            with open(self.cache_file, 'wb') as f:
                pickle.dump(data, f)
        except:
            pass

    def test_ip(self, ip, result_queue, timeout=1):
        """测试单个IP（线程函数）"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, self.port))
            sock.close()

            if result == 0:
                # 端口开放，进一步验证
                if self.verify_k230(ip, timeout=2):
                    result_queue.put(ip)
        except:
            pass

    def verify_k230(self, ip, timeout=2):
        """验证是否为K230服务器"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((ip, self.port))

            # 发送验证请求
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            sock.close()

            # 检查是否是MJPEG服务器
            return "multipart/x-mixed-replace" in response or "image/jpeg" in response
        except:
            return False

    def concurrent_scan(self, network_prefix, start_end_pairs):
        """
        并发扫描指定的地址范围
        :param network_prefix: 网络前缀，如 "192.168.137"
        :param start_end_pairs: [(start1, end1), (start2, end2), ...]
        """
        result_queue = Queue()
        all_threads = []
        found_ip = None

        # 创建所有扫描任务
        for start, end in start_end_pairs:
            if not self.scanning:
                break

            batch_threads = []
            for i in range(start, end + 1):
                if not self.scanning:
                    break

                ip = f"{network_prefix}.{i}"
                thread = threading.Thread(
                    target=self.test_ip,
                    args=(ip, result_queue, 1)
                )
                batch_threads.append(thread)
                thread.start()

                # 每批50个线程
                if len(batch_threads) >= 50:
                    for t in batch_threads:
                        t.join(timeout=0.01)
                    batch_threads = []

                # 检查是否已找到
                try:
                    found_ip = result_queue.get_nowait()
                    break
                except:
                    pass

            # 等待本批次完成
            for t in batch_threads:
                t.join(timeout=0.01)

            if found_ip:
                break

        # 最终检查
        try:
            found_ip = result_queue.get_nowait()
        except:
            pass

        return found_ip

    def start_scan(self):
        """开始极速扫描"""
        self.scanning = True
        found_ip = None

        # 第1步：尝试缓存IP（最快，<1秒）
        if self.last_ip and self.scanning:
            self.progress_signal.emit(
                f"尝试历史IP: {self.last_ip}", "info"
            )

            if self.verify_k230(self.last_ip, timeout=2):
                found_ip = self.last_ip
                self.progress_signal.emit(
                    f"历史IP连接成功！", "success"
                )

        # 第2步：确定优先扫描的网络
        priority_network = "192.168.137"  # 你的K230固定在这个网段

        if not found_ip and self.scanning:
            self.progress_signal.emit(
                f"极速扫描 {priority_network}.x", "info"
            )

            # 智能扫描策略：先扫常用地址，再逐步扩大
            scan_phases = [
                # (开始, 结束, 描述)
                (1, 30, "DHCP常用范围（1-30）"),
                (50, 80, "中间范围（50-80）"),
                (100, 130, "较高范围（100-130）"),
                (150, 180, "较高范围（150-180）"),
                (200, 230, "较高范围（200-230）"),
            ]

            for start, end, desc in scan_phases:
                if found_ip or not self.scanning:
                    break

                self.progress_signal.emit(
                    f"扫描{desc}...", "info"
                )

                found_ip = self.concurrent_scan(
                    priority_network,
                    [(start, end)]
                )

        # 第3步：如果还没找到，快速扫描整个范围
        if not found_ip and self.scanning:
            self.progress_signal.emit(
                "快速扫描整个网段...", "warning"
            )

            # 分成4个批次并发扫描
            batches = [
                (1, 63),  # 第一批
                (64, 127),  # 第二批
                (128, 191),  # 第三批
                (192, 254),  # 第四批
            ]

            found_ip = self.concurrent_scan(priority_network, batches)

        # 扫描完成
        self.scanning = False

        if found_ip:
            self.save_cache(found_ip)
            self.found_signal.emit(found_ip)
        else:
            self.progress_signal.emit("未发现K230设备", "error")

        self.finished_signal.emit()
        return found_ip

    def stop_scan(self):
        """停止扫描"""
        self.scanning = False