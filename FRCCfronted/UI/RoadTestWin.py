# -*- coding: utf-8 -*-
# @Time    : 2024/11/18 23:42
# @Modified: 2025/02/27 适配H265协议 - 优化版本
# @Author  : zlh
# @File    : RoadTestWin.py
# @Description: K230 H265视频流显示窗口，使用OpenCV直接解码，无FFmpeg依赖

import sys
import cv2
import numpy as np
import time
import socket
import threading
import pickle
import os
import struct
import subprocess
import io
from queue import Queue, Empty, Full
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *

# ==================== 配置常量 ====================
VIDEO_PORT = 8888
DISCOVERY_PORT = 8889
BUFFER_SIZE = 65535
NETWORK_SEGMENT = "192.168.137"


# ==================== UDP发现服务 ====================
class DiscoveryService(QObject):
    """UDP服务器发现服务 - 响应K230的广播请求"""
    device_discovered = pyqtSignal(str)
    status_signal = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.socket = None
        self.thread = None
        self.discovered_ips = set()

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

    def _run(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.socket.bind(('0.0.0.0', DISCOVERY_PORT))
            self.status_signal.emit("发现服务已启动", "success")

            while self.running:
                try:
                    self.socket.settimeout(1.0)
                    data, addr = self.socket.recvfrom(1024)

                    if data == b"K230_DISCOVER_REQUEST":
                        client_ip = addr[0]
                        self.socket.sendto(b"K230_DISCOVER_RESPONSE", addr)

                        if client_ip not in self.discovered_ips:
                            self.discovered_ips.add(client_ip)
                            self.device_discovered.emit(client_ip)

                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.status_signal.emit(f"发现服务错误: {e}", "error")
        except Exception as e:
            self.status_signal.emit(f"无法启动发现服务: {e}", "error")
        finally:
            try:
                self.socket.close()
            except:
                pass


# ==================== H265解码器 ====================
class H265Decoder:
    """
    H265视频解码器 - 使用OpenCV或FFmpeg进行软解码
    注: PyAudio是音频库，不能用于视频解码
    """

    def __init__(self):
        self.temp_file = None
        self.cap = None
        self.frame_width = 640
        self.frame_height = 480

    def decode_frame(self, nal_data):
        """
        解码H265 NAL数据
        返回: (success, frame) 或 (False, None)
        """
        try:
            # 方案1: 使用OpenCV的VideoCapture (需要完整文件)
            # 将NAL数据写入临时文件，然后用OpenCV读取

            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.265', delete=False) as f:
                f.write(nal_data)
                temp_path = f.name

            # 使用OpenCV打开并解码
            cap = cv2.VideoCapture(temp_path)

            frames = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                frames.append(frame)

            cap.release()

            # 删除临时文件
            try:
                os.unlink(temp_path)
            except:
                pass

            if frames:
                # 返回最后一帧（最新的）
                return True, frames[-1]

            return False, None

        except Exception as e:
            return False, None

    def decode_stream(self, stream_data):
        """
        解码连续H265流
        适用于累积了多个NAL单元的情况
        """
        return self.decode_frame(stream_data)


# ==================== H265视频流线程 ====================
class H265StreamThread(QThread):
    """H265视频流接收线程"""
    frame_ready = pyqtSignal(np.ndarray)
    status_signal = pyqtSignal(str, str)
    stats_signal = pyqtSignal(dict)

    def __init__(self, ip, port=VIDEO_PORT):
        super().__init__()
        self.ip = ip
        self.port = port
        self.running = False
        self.socket = None
        self.frame_count = 0
        self.start_time = None
        self.received_bytes = 0

        # H265相关
        self.decoder = H265Decoder()
        self.nal_buffer = bytearray()
        self.decode_queue = Queue(maxsize=5)

    def run(self):
        self.running = True
        self.start_time = time.time()

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.ip, self.port))
            self.socket.settimeout(30.0)

            self.status_signal.emit("success", "视频流连接成功")

            # 启动解码线程
            decode_thread = threading.Thread(target=self._decode_worker, daemon=True)
            decode_thread.start()

            # 接收数据
            self._receive_stream()

        except socket.timeout:
            self.status_signal.emit("error", "连接超时")
        except Exception as e:
            if self.running:
                self.status_signal.emit("error", f"连接错误: {str(e)}")
        finally:
            self.stop()

    def _receive_stream(self):
        """接收H265视频流"""
        last_stats_time = time.time()

        while self.running:
            try:
                # 接收头部
                header = self._recv_exactly(8)
                if not header:
                    break

                total_size, nalu_count = struct.unpack("<LL", header)
                self.received_bytes += 8

                # 接收数据
                data_buffer = self._recv_exactly(total_size)
                if not data_buffer:
                    break

                self.received_bytes += len(data_buffer)

                # 解析NALU
                offset = 0
                for i in range(nalu_count):
                    if offset + 4 > len(data_buffer):
                        break

                    nalu_size = struct.unpack("<L", data_buffer[offset:offset + 4])[0]
                    offset += 4

                    if offset + nalu_size > len(data_buffer):
                        break

                    nalu_data = data_buffer[offset:offset + nalu_size]
                    offset += nalu_size

                    # 添加起始码
                    self.nal_buffer.extend(b'\x00\x00\x00\x01')
                    self.nal_buffer.extend(nalu_data)

                # 尝试解码（当缓冲区足够大或检测到关键帧）
                if len(self.nal_buffer) > 8192 or self._is_keyframe(self.nal_buffer):
                    # 将数据放入解码队列
                    if not self.decode_queue.full():
                        self.decode_queue.put(bytes(self.nal_buffer))
                    # 清空缓冲区，准备下一帧
                    self.nal_buffer = bytearray()

                # 统计
                current_time = time.time()
                if current_time - last_stats_time >= 1.0:
                    elapsed = current_time - self.start_time
                    fps = self.frame_count / elapsed if elapsed > 0 else 0
                    bitrate = (self.received_bytes * 8) / elapsed / 1000

                    self.stats_signal.emit({
                        'fps': fps,
                        'bitrate': bitrate,
                        'frame_count': self.frame_count,
                        'queue_size': self.decode_queue.qsize()
                    })
                    last_stats_time = current_time

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.status_signal.emit("warning", f"接收错误: {e}")
                break

    def _recv_exactly(self, n):
        """精确接收n字节"""
        data = bytearray()
        while len(data) < n and self.running:
            try:
                chunk = self.socket.recv(min(n - len(data), BUFFER_SIZE))
                if not chunk:
                    return None
                data.extend(chunk)
            except socket.timeout:
                continue
            except:
                return None
        return bytes(data)

    def _is_keyframe(self, data):
        """检测关键帧"""
        for i in range(len(data) - 5):
            if data[i:i + 4] == b'\x00\x00\x00\x01':
                if i + 4 < len(data):
                    nal_header = data[i + 4]
                    nal_type = (nal_header >> 1) & 0x3F
                    if nal_type in [19, 20]:  # IDR帧
                        return True
        return False

    def _decode_worker(self):
        """解码工作线程"""
        while self.running:
            try:
                data = self.decode_queue.get(timeout=0.1)

                # 解码
                success, frame = self.decoder.decode_stream(data)

                if success and frame is not None:
                    # BGR -> RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    self.frame_ready.emit(frame_rgb)
                    self.frame_count += 1

            except Empty:
                continue
            except Exception as e:
                pass

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        while not self.decode_queue.empty():
            try:
                self.decode_queue.get_nowait()
            except:
                break


# ==================== H265扫描器 ====================
class H265Scanner:
    """H265设备扫描器"""

    def __init__(self, port=VIDEO_PORT):
        self.port = port
        self.scanning = False
        self.cache_file = "k230_h265_cache.pkl"
        self.last_ip = None
        self.callback = None
        self.discovery = DiscoveryService()

        self.load_cache()

    def load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'rb') as f:
                    data = pickle.load(f)
                    self.last_ip = data.get('last_ip')
            except:
                self.last_ip = None

    def save_cache(self, ip):
        try:
            data = {'last_ip': ip, 'timestamp': time.time()}
            with open(self.cache_file, 'wb') as f:
                pickle.dump(data, f)
        except:
            pass

    def verify_k230(self, ip, timeout=3):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, self.port))
            sock.close()
            return result == 0
        except:
            return False

    def start_scan(self, callback=None):
        self.callback = callback
        self.scanning = True
        found_ip = None

        # 尝试历史IP
        if self.last_ip and self.scanning:
            if self.callback:
                self.callback("info", f"尝试历史IP: {self.last_ip}")

            if self.verify_k230(self.last_ip):
                found_ip = self.last_ip
                if self.callback:
                    self.callback("success", f"历史IP连接成功！")
                self.scanning = False
                return found_ip

        # UDP发现
        if self.scanning:
            if self.callback:
                self.callback("info", "启动UDP发现服务...")

            discovered = Queue()

            def on_discovered(ip):
                discovered.put(ip)

            self.discovery.device_discovered.connect(on_discovered)
            self.discovery.start()

            start_time = time.time()
            while self.scanning and time.time() - start_time < 15:
                try:
                    found_ip = discovered.get(timeout=0.5)
                    if self.callback:
                        self.callback("success", f"发现设备: {found_ip}")
                    break
                except Empty:
                    if self.callback:
                        self.callback("info", "等待K230连接...")

            self.discovery.stop()

        # 主动扫描
        if not found_ip and self.scanning:
            if self.callback:
                self.callback("info", "主动扫描网段...")
            found_ip = self._active_scan()

        self.scanning = False

        if found_ip:
            self.save_cache(found_ip)

        return found_ip

    def _active_scan(self):
        result_queue = Queue()

        def test_ip(ip):
            if not self.scanning:
                return
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((ip, self.port))
                sock.close()
                if result == 0:
                    result_queue.put(ip)
            except:
                pass

        threads = []
        for i in range(1, 255):
            if not self.scanning:
                break
            ip = f"{NETWORK_SEGMENT}.{i}"
            t = threading.Thread(target=test_ip, args=(ip,))
            threads.append(t)
            t.start()

            if len(threads) >= 50:
                for t in threads:
                    t.join(timeout=0.01)
                threads = []
                try:
                    return result_queue.get_nowait()
                except:
                    pass

        for t in threads:
            t.join(timeout=0.01)

        try:
            return result_queue.get_nowait()
        except:
            return None

    def stop_scan(self):
        self.scanning = False
        self.discovery.stop()


# ==================== 连接对话框 ====================
class ConnectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.scanner = H265Scanner()
        QTimer.singleShot(100, self.start_scanning)

    def setup_ui(self):
        self.setWindowTitle("连接K230 (H265)")
        self.setModal(True)
        self.setFixedSize(500, 300)

        layout = QVBoxLayout(self)

        title = QLabel("正在连接K230，请稍候...")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("正在初始化...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10px;")
        layout.addWidget(self.log_text)

        button_layout = QHBoxLayout()
        self.manual_btn = QPushButton("手动输入IP")
        self.manual_btn.clicked.connect(self.manual_input)
        button_layout.addWidget(self.manual_btn)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_scanning)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def start_scanning(self):
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] 开始H265设备扫描...")
        self.scan_thread = threading.Thread(target=self._scan_thread_func, daemon=True)
        self.scan_thread.start()

    def _scan_thread_func(self):
        ip = self.scanner.start_scan(self.update_progress)

        if ip:
            self.found_ip = ip
            QMetaObject.invokeMethod(self, "_on_scan_success",
                                     Qt.QueuedConnection, Q_ARG(str, ip))
        else:
            QMetaObject.invokeMethod(self, "_on_scan_failed", Qt.QueuedConnection)

    def update_progress(self, msg_type, message):
        QMetaObject.invokeMethod(self, "_update_ui",
                                 Qt.QueuedConnection,
                                 Q_ARG(str, msg_type),
                                 Q_ARG(str, message))

    @pyqtSlot(str, str)
    def _update_ui(self, msg_type, message):
        timestamp = time.strftime("%H:%M:%S")
        self.status_label.setText(message)

        prefix = {
            "info": "[INFO]",
            "success": "[SUCCESS]",
            "warning": "[WARNING]",
            "error": "[ERROR]"
        }.get(msg_type, "[INFO]")

        self.log_text.append(f"[{timestamp}] {prefix} {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        colors = {
            "info": "#2196F3",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336"
        }

        if msg_type in colors:
            self.progress_bar.setStyleSheet(f"""
                QProgressBar::chunk {{ background-color: {colors[msg_type]}; }}
            """)

    @pyqtSlot(str)
    def _on_scan_success(self, ip):
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] [SUCCESS] 找到设备: {ip}")
        QTimer.singleShot(500, self.accept)

    @pyqtSlot()
    def _on_scan_failed(self):
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] [ERROR] 未发现设备")
        self.cancel_button.setEnabled(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

    def manual_input(self):
        ip, ok = QInputDialog.getText(self, "手动输入", "请输入K230的IP地址:")
        if ok and ip:
            self.found_ip = ip
            self.scanner.stop_scan()
            self.accept()

    def cancel_scanning(self):
        self.scanner.stop_scan()
        self.reject()

    def get_found_ip(self):
        return getattr(self, 'found_ip', None)


# ==================== K230视频流主窗口 ====================
class K230VideoWin(QWidget):
    """
    K230 H265视频流显示窗口

    使用方法:
        from RoadTestWin import K230VideoWin
        video_win = K230VideoWin(parent=None, w=1280, h=720)
        video_win.show()
    """

    def __init__(self, parent=None, w=1280, h=720):
        super().__init__(parent)
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        self.video_thread = None
        self.current_ip = None
        self.frame_count = 0
        self.start_time = None
        self.fps = 0
        self.last_fps_time = time.time()

        self.init_control()
        self.setAttribute(Qt.WA_DeleteOnClose)

    def init_control(self):
        self.totallayout = QVBoxLayout()
        self.setLayout(self.totallayout)

        center_container = QWidget()
        center_layout = QHBoxLayout(center_container)
        center_layout.setContentsMargins(0, 0, 0, 0)

        self.imgLab = QLabel('K230 H265 无线图传客户端\n\n点击【连接K230】开始', self)
        self.imgLab.setFixedSize(720, 480)
        self.imgLab.setAlignment(Qt.AlignCenter)
        self.imgLab.setStyleSheet("""
            QLabel {
                background-color: #000;
                color: #fff;
                font-size: 16px;
                padding: 10px;
                border: 2px solid #333;
                border-radius: 5px;
            }
        """)

        center_layout.addStretch(1)
        center_layout.addWidget(self.imgLab)
        center_layout.addStretch(1)

        self.tips = QLabel('就绪', self)
        self.tips.setAlignment(Qt.AlignCenter)
        self.tips.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #f0f0f0;
                border: 1px solid #ccc;
                border-radius: 5px;
                font-weight: bold;
            }
        """)

        self.totallayout.setContentsMargins(30, 20, 30, 20)

        self.play = QPushButton('连接K230')
        self.play.clicked.connect(self.connect_k230)
        self.play.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                font-size: 14px;
                font-weight: bold;
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)

        self.stop = QPushButton('断开连接')
        self.stop.clicked.connect(self.disconnect_k230)
        self.stop.setEnabled(False)

        info_widget = QWidget()
        info_layout = QHBoxLayout(info_widget)

        info_group = QGroupBox("连接信息 (H265)")
        info_group.setStyleSheet("QGroupBox { color: white; font-weight: bold; } QLabel { color: white; }")

        info_form = QFormLayout(info_group)

        self.ip_label = QLabel("未连接")
        self.status_label = QLabel("就绪")
        self.fps_label = QLabel("0.0")
        self.resolution_label = QLabel("未知")

        info_form.addRow("设备IP:", self.ip_label)
        info_form.addRow("状态:", self.status_label)
        info_form.addRow("帧率:", self.fps_label)
        info_form.addRow("分辨率:", self.resolution_label)

        info_layout.addWidget(info_group)

        self.totallayout.addWidget(center_container)

        button_container = QWidget()
        button_container_layout = QHBoxLayout(button_container)
        button_container_layout.setContentsMargins(0, 0, 0, 0)
        button_container_layout.addStretch(1)
        button_container_layout.addWidget(self.play)
        button_container_layout.addSpacing(20)
        button_container_layout.addWidget(self.stop)
        button_container_layout.addStretch(1)

        self.totallayout.addWidget(button_container)
        self.totallayout.addWidget(self.tips)
        self.totallayout.addWidget(info_widget)

        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)

    def connect_k230(self):
        self.play.setEnabled(False)
        self.stop.setEnabled(False)
        self.play.setText("正在连接...")

        dialog = ConnectionDialog(self)

        if dialog.exec_() == QDialog.Accepted:
            ip = dialog.get_found_ip()
            if ip:
                self.start_video_stream(ip)
        else:
            self.play.setEnabled(True)
            self.stop.setEnabled(False)
            self.play.setText("连接K230")
            self.update_status("连接取消", "info")

    def start_video_stream(self, ip):
        self.current_ip = ip
        self.play.setText("重新连接")
        self.stop.setEnabled(True)
        self.ip_label.setText(ip)
        self.update_status("已连接", "success")

        self.video_thread = H265StreamThread(ip)
        self.video_thread.frame_ready.connect(self.update_video_frame)
        self.video_thread.status_signal.connect(self.update_status)
        self.video_thread.stats_signal.connect(self.update_video_stats)
        self.video_thread.start()

        self.start_time = time.time()
        self.stats_timer.start(1000)
        self.frame_count = 0
        self.last_fps_time = time.time()

    def update_video_frame(self, frame):
        try:
            rgb_image = frame
            h, w, ch = rgb_image.shape

            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.imgLab.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.imgLab.setPixmap(scaled_pixmap)
            self.imgLab.setScaledContents(True)
            self.resolution_label.setText(f"{w}×{h}")
            self.frame_count += 1

        except Exception as e:
            print(f"显示错误: {e}")

    def update_status(self, msg_type, message):
        colors = {
            "info": "#2196F3",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336"
        }

        color = colors.get(msg_type, "#2196F3")
        self.status_label.setText(message)
        self.tips.setText(message)
        self.tips.setStyleSheet(f"""
            QLabel {{
                padding: 10px;
                background-color: {color};
                color: white;
                border: 1px solid {color};
                border-radius: 5px;
                font-weight: bold;
            }}
        """)

        if msg_type == "error":
            self.disconnect_k230()

    def update_video_stats(self, stats):
        self.fps_label.setText(f"{stats['fps']:.1f}")

    def update_stats(self):
        current_time = time.time()
        elapsed = current_time - self.last_fps_time
        if elapsed > 0:
            self.fps = self.frame_count / elapsed
            self.fps_label.setText(f"{self.fps:.1f}")
        self.frame_count = 0
        self.last_fps_time = current_time

    def disconnect_k230(self):
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait(2000)
            self.video_thread = None

        self.stats_timer.stop()

        self.play.setEnabled(True)
        self.stop.setEnabled(False)
        self.play.setText("连接K230")
        self.ip_label.setText("未连接")
        self.status_label.setText("已断开")
        self.fps_label.setText("0.0")
        self.resolution_label.setText("未知")
        self.update_status("已断开连接", "info")
        self.imgLab.setText("连接已断开\n\n点击【连接K230】重新开始")
        self.imgLab.setStyleSheet("""
            QLabel {
                background-color: #000;
                color: #fff;
                font-size: 16px;
                padding: 10px;
                border: 2px solid #333;
                border-radius: 5px;
            }
        """)

    def closeEvent(self, event):
        self.disconnect_k230()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = K230VideoWin(w=1280, h=800)
    window.setWindowTitle("K230 H265 无线图传客户端")
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
