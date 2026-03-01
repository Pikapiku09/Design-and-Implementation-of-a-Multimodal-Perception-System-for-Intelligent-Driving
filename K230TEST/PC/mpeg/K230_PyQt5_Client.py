# -*- coding: utf-8 -*-
# @Time    : 2026/2/11 12:09
# @Author  : zlh
# @File    : K230_PyQt5_Client.py.py
import sys
import cv2
import numpy as np
import time
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import socket
import threading

from fast_scanner import quick_connect_k230
from K230_Fast_Connector import FastK230Scanner

class VideoStreamThread(QThread):
    """视频流接收线程"""
    frame_ready = pyqtSignal(np.ndarray)
    status_signal = pyqtSignal(str, str)

    def __init__(self, ip, port=8888):
        super().__init__()
        self.ip = ip
        self.port = port
        self.running = False
        self.socket = None
        self.frame_count = 0

    def run(self):
        self.running = True

        try:
            # 建立连接
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(5)
            self.socket.connect((self.ip, self.port))

            # 发送HTTP请求
            request = "GET / HTTP/1.0\r\n\r\n"
            self.socket.send(request.encode())

            # 读取响应头
            self._read_until(b"\r\n\r\n", timeout=3)

            self.status_signal.emit("success", "视频流连接成功")

            # 接收视频
            self.receive_video()

        except Exception as e:
            self.status_signal.emit("error", f"连接失败: {str(e)}")
        finally:
            self.stop()

    def _read_until(self, delimiter, timeout=3):
        data = b""
        end_time = time.time() + timeout

        while time.time() < end_time and self.running:
            try:
                chunk = self.socket.recv(1024)
                if not chunk:
                    break
                data += chunk
                if delimiter in data:
                    return data
            except socket.timeout:
                continue
        return None

    def receive_video(self):
        buffer = b""
        boundary = b"--frame"
        last_report = time.time()

        while self.running:
            try:
                chunk = self.socket.recv(65536)
                if not chunk:
                    break

                buffer += chunk

                # 解析帧
                while True:
                    start_idx = buffer.find(boundary)
                    if start_idx < 0:
                        break

                    header_end = buffer.find(b"\r\n\r\n", start_idx)
                    if header_end < 0:
                        break

                    # 解析内容长度
                    header = buffer[start_idx:header_end].decode('ascii', errors='ignore')
                    content_length = None

                    for line in header.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            try:
                                content_length = int(line.split(':')[1].strip())
                                break
                            except:
                                pass

                    if content_length is None:
                        buffer = buffer[header_end + 4:]
                        continue

                    # 提取JPEG数据
                    frame_start = header_end + 4
                    frame_end = frame_start + content_length

                    if len(buffer) < frame_end:
                        break

                    jpeg_data = buffer[frame_start:frame_end]
                    buffer = buffer[frame_end:]

                    # 解码和发射
                    self.decode_and_emit(jpeg_data)
                    self.frame_count += 1

                    # 定期报告
                    current_time = time.time()
                    if current_time - last_report > 2.0:
                        fps = self.frame_count / 2.0
                        self.status_signal.emit("info", f"FPS: {fps:.1f}")
                        self.frame_count = 0
                        last_report = current_time

                time.sleep(0.001)

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.status_signal.emit("warning", f"接收错误: {str(e)}")
                break

    def decode_and_emit(self, jpeg_data):
        try:
            nparr = np.frombuffer(jpeg_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                # ====== 关键修复：BGR转RGB ======
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # =================================
                self.frame_ready.emit(frame)
        except Exception as e:
            print(f"解码错误: {e}")

    def stop(self):
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass


class ConnectionDialog(QDialog):
    """连接对话框 - 显示实时进度"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setup_ui()

        # 创建扫描器
        self.scanner = FastK230Scanner()
        self.scanner.moveToThread(QThread.currentThread())

        # 连接信号
        self.scanner.progress_signal.connect(self.update_progress)
        self.scanner.found_signal.connect(self.on_device_found)
        self.scanner.finished_signal.connect(self.on_scan_finished)

        # 启动扫描
        QTimer.singleShot(100, self.start_scanning)

    def setup_ui(self):
        self.setWindowTitle("连接K230")
        self.setModal(True)
        self.setFixedSize(500, 300)

        layout = QVBoxLayout(self)

        # 标题
        title = QLabel("正在连接K230...")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; padding: 20px;")
        layout.addWidget(title)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.progress_bar)

        # 状态标签
        self.status_label = QLabel("正在初始化扫描器...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        # 详细日志
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setStyleSheet("font-family: 'Consolas', monospace; font-size: 10px;")
        layout.addWidget(self.log_text)

        # 按钮
        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_scanning)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

    def start_scanning(self):
        """开始扫描"""
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] 开始极速扫描...")

        # 在新线程中启动扫描
        self.scan_thread = threading.Thread(target=self.scanner.start_scan)
        self.scan_thread.daemon = True
        self.scan_thread.start()

        # 启动超时检查
        self.timeout_timer = QTimer()
        self.timeout_timer.timeout.connect(self.check_timeout)
        self.timeout_timer.start(100)  # 每100ms检查一次

    def update_progress(self, message, msg_type):
        """更新进度显示"""
        timestamp = time.strftime("%H:%M:%S")

        # 更新状态标签
        self.status_label.setText(message)

        # 添加日志
        prefix = {
            "info": "[INFO]",
            "success": "[SUCCESS]",
            "warning": "[WARNING]",
            "error": "[ERROR]"
        }.get(msg_type, "[INFO]")

        self.log_text.append(f"[{timestamp}] {prefix} {message}")

        # 自动滚动到底部
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        # 更新进度条颜色
        colors = {
            "info": "#2196F3",
            "success": "#4CAF50",
            "warning": "#FF9800",
            "error": "#F44336"
        }

        if msg_type in colors:
            self.progress_bar.setStyleSheet(f"""
                QProgressBar::chunk {{
                    background-color: {colors[msg_type]};
                }}
            """)

    def on_device_found(self, ip):
        """找到设备"""
        self.found_ip = ip
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] [SUCCESS] 找到设备: {ip}")

        # 延迟一点时间，让用户看到成功消息
        QTimer.singleShot(500, self.accept)

    def on_scan_finished(self):
        """扫描完成"""
        self.log_text.append(f"[{time.strftime('%H:%M:%S')}] 扫描完成")

        # 如果没有找到设备，启用取消按钮
        if not hasattr(self, 'found_ip'):
            self.cancel_button.setEnabled(True)

    def check_timeout(self):
        """检查超时"""
        if not self.scan_thread.is_alive():
            self.timeout_timer.stop()

    def cancel_scanning(self):
        """取消扫描"""
        self.scanner.stop_scan()
        self.reject()

    def get_found_ip(self):
        """获取找到的IP"""
        return getattr(self, 'found_ip', None)


class K230Client(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.video_thread = None
        self.current_ip = None
        self.frame_count = 0
        self.start_time = None

        self.init_ui()

        # 3秒后自动连接
        QTimer.singleShot(3000, self.auto_connect)

    def init_ui(self):
        self.setWindowTitle("K230 极速图传客户端")
        self.setGeometry(100, 100, 900, 700)

        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        layout = QVBoxLayout(central_widget)

        # 1. 工具栏
        self.create_toolbar(layout)

        # 2. 视频显示
        self.create_video_display(layout)

        # 3. 信息面板
        self.create_info_panel(layout)

    def create_toolbar(self, layout):
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)

        # 连接按钮
        self.connect_btn = QPushButton("连接K230")
        self.connect_btn.setIcon(self.style().standardIcon(QStyle.SP_BrowserReload))
        self.connect_btn.clicked.connect(self.connect_k230)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                font-size: 14px;
                font-weight: bold;
                background-color: #4CAF50;
                color: white;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)

        # 断开按钮
        self.disconnect_btn = QPushButton("断开连接")
        self.disconnect_btn.setIcon(self.style().standardIcon(QStyle.SP_DialogCloseButton))
        self.disconnect_btn.clicked.connect(self.disconnect_k230)
        self.disconnect_btn.setEnabled(False)

        # 退出按钮
        quit_btn = QPushButton("退出程序")
        quit_btn.clicked.connect(self.close)

        toolbar_layout.addWidget(self.connect_btn)
        toolbar_layout.addWidget(self.disconnect_btn)
        toolbar_layout.addWidget(quit_btn)
        toolbar_layout.addStretch()

        layout.addWidget(toolbar)

    def create_video_display(self, layout):
        video_frame = QFrame()
        video_frame.setFrameStyle(QFrame.Box | QFrame.Raised)
        video_frame.setLineWidth(2)

        video_layout = QVBoxLayout(video_frame)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000;
                color: #fff;
                font-size: 16px;
                padding: 10px;
            }
        """)
        self.video_label.setText("K230 无线图传客户端\n\n点击【连接K230】开始")

        video_layout.addWidget(self.video_label)
        layout.addWidget(video_frame, 1)

    def create_info_panel(self, layout):
        panel = QWidget()
        panel_layout = QHBoxLayout(panel)

        # 连接信息
        info_group = QGroupBox("连接信息")
        info_layout = QFormLayout(info_group)

        self.ip_label = QLabel("未连接")
        self.status_label = QLabel("就绪")
        self.fps_label = QLabel("0.0")
        self.resolution_label = QLabel("未知")

        info_layout.addRow("设备IP:", self.ip_label)
        info_layout.addRow("状态:", self.status_label)
        info_layout.addRow("帧率:", self.fps_label)
        info_layout.addRow("分辨率:", self.resolution_label)

        panel_layout.addWidget(info_group)

        # 性能统计
        stats_group = QGroupBox("性能统计")
        stats_layout = QFormLayout(stats_group)

        self.frames_label = QLabel("0")
        self.time_label = QLabel("00:00:00")
        self.bitrate_label = QLabel("0 KB/s")

        stats_layout.addRow("总帧数:", self.frames_label)
        stats_layout.addRow("运行时间:", self.time_label)
        stats_layout.addRow("估算码率:", self.bitrate_label)

        panel_layout.addWidget(stats_group)

        layout.addWidget(panel)

    def auto_connect(self):
        """自动连接"""
        self.connect_k230()

    def connect_k230(self):
        """连接K230"""
        self.connect_btn.setEnabled(False)
        self.disconnect_btn.setEnabled(False)
        self.connect_btn.setText("正在连接...")

        # 显示连接对话框
        dialog = ConnectionDialog(self)

        if dialog.exec_() == QDialog.Accepted:
            ip = dialog.get_found_ip()
            if ip:
                self.start_video_stream(ip)
        else:
            # 用户取消或连接失败
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.connect_btn.setText("连接K230")
            self.status_label.setText("连接取消")

    def start_video_stream(self, ip):
        """启动视频流"""
        self.current_ip = ip

        # 更新UI
        self.connect_btn.setText("重新连接")
        self.disconnect_btn.setEnabled(True)
        self.ip_label.setText(ip)
        self.status_label.setText("已连接")

        # 启动视频线程
        self.video_thread = VideoStreamThread(ip)
        self.video_thread.frame_ready.connect(self.update_video_frame)
        self.video_thread.status_signal.connect(self.update_status)
        self.video_thread.start()

        # 启动统计定时器
        self.start_time = time.time()
        self.stats_timer = QTimer()
        self.stats_timer.timeout.connect(self.update_stats)
        self.stats_timer.start(1000)

        self.frame_count = 0
        self.last_fps_time = time.time()

    def update_video_frame(self, frame):
        """更新视频帧"""
        try:
            # 转换颜色空间
            rgb_image = cv2.cvtColor(frame, cv2.IMREAD_COLOR)
            h, w, ch = rgb_image.shape

            # 创建QImage
            bytes_per_line = ch * w
            qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)

            # 缩放并显示
            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            self.video_label.setPixmap(scaled_pixmap)

            # 更新分辨率
            self.resolution_label.setText(f"{w}×{h}")

            # 更新帧统计
            self.frame_count += 1

        except Exception as e:
            print(f"显示错误: {e}")

    def update_status(self, msg_type, message):
        """更新状态"""
        self.status_label.setText(message)

        if msg_type == "error":
            self.disconnect_k230()

    def update_stats(self):
        """更新统计信息"""
        current_time = time.time()

        # 计算FPS
        elapsed = current_time - self.last_fps_time
        if elapsed > 0:
            fps = self.frame_count / elapsed
            self.fps_label.setText(f"{fps:.1f}")

        self.frame_count = 0
        self.last_fps_time = current_time

        # 更新其他统计
        if self.video_thread:
            self.frames_label.setText(str(self.video_thread.frame_count))

        # 运行时间
        if self.start_time:
            run_seconds = int(current_time - self.start_time)
            hours = run_seconds // 3600
            minutes = (run_seconds % 3600) // 60
            seconds = run_seconds % 60
            self.time_label.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def disconnect_k230(self):
        """断开连接"""
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait(2000)
            self.video_thread = None

        if hasattr(self, 'stats_timer'):
            self.stats_timer.stop()

        # 重置UI
        self.connect_btn.setEnabled(True)
        self.disconnect_btn.setEnabled(False)
        self.connect_btn.setText("连接K230")
        self.ip_label.setText("未连接")
        self.status_label.setText("已断开")
        self.fps_label.setText("0.0")
        self.resolution_label.setText("未知")
        self.frames_label.setText("0")
        self.time_label.setText("00:00:00")
        self.video_label.setText("连接已断开\n\n点击【连接K230】重新开始")
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #000;
                color: #fff;
                font-size: 16px;
                padding: 10px;
            }
        """)

    def closeEvent(self, event):
        """关闭事件"""
        self.disconnect_k230()
        event.accept()


def main():
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 创建窗口
    window = K230Client()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()