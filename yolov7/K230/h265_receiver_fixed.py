"""
K230 H265 视频流接收器 - PyQt5 图传显示程序 (修复版)
用于接收K230发送的H265编码视频流并实时显示
"""

import sys
import socket
import struct
import time
from collections import deque
from datetime import datetime

import numpy as np
import cv2
import av
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QLineEdit, QSpinBox, QGroupBox,
    QPlainTextEdit, QStatusBar, QMessageBox, QSplitter
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt5.QtGui import QImage, QPixmap


# ============== 视频解码线程 ==============
class VideoDecoder(QThread):
    """H265视频解码线程"""
    frame_ready = pyqtSignal(np.ndarray)
    stats_update = pyqtSignal(dict)
    log_message = pyqtSignal(str)

    def __init__(self, frame_buffer_size=10):
        super().__init__()
        self.frame_buffer = deque(maxlen=frame_buffer_size)
        self.codec = None
        self.running = False
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.fps = 0
        self.decoder_errors = 0
        self._init_decoder()

    def _init_decoder(self):
        """初始化H265解码器"""
        try:
            self.codec = av.CodecContext.create('hevc', 'r')
            # 设置解码器参数
            self.codec.thread_type = 'AUTO'
            self.log_message.emit("H265解码器初始化成功")
        except Exception as e:
            self.log_message.emit(f"解码器初始化失败: {e}")
            self.codec = None

    def add_packet(self, data):
        """添加H265数据包到缓冲区"""
        try:
            self.frame_buffer.append(data)
        except:
            pass

    def run(self):
        """解码主循环"""
        self.running = True
        self.log_message.emit("视频解码线程已启动")

        while self.running:
            try:
                if len(self.frame_buffer) > 0 and self.codec:
                    # 获取数据包
                    packet_data = self.frame_buffer.popleft()

                    # 确保数据有效
                    if not packet_data or len(packet_data) < 4:
                        continue

                    # 创建AV Packet
                    packet = av.Packet(packet_data)

                    # 解码
                    frames = self.codec.decode(packet)

                    for frame in frames:
                        try:
                            # 转换为numpy数组 (RGB格式)
                            img = frame.to_ndarray(format='rgb24')

                            # 计算FPS
                            self.frame_count += 1
                            current_time = time.time()
                            if current_time - self.last_fps_time >= 1.0:
                                self.fps = self.frame_count
                                self.frame_count = 0
                                self.last_fps_time = current_time

                            # 发送帧
                            self.frame_ready.emit(img)

                            # 发送统计信息
                            self.stats_update.emit({
                                'fps': self.fps,
                                'resolution': f"{frame.width}x{frame.height}",
                                'buffer_size': len(self.frame_buffer),
                                'decoder_errors': self.decoder_errors
                            })
                        except Exception as e:
                            self.decoder_errors += 1

                else:
                    time.sleep(0.001)

            except av.AVError as e:
                self.decoder_errors += 1
                if self.decoder_errors % 20 == 1:
                    self.log_message.emit(f"解码错误: {e}")
            except Exception as e:
                self.decoder_errors += 1
                if self.decoder_errors % 20 == 1:
                    self.log_message.emit(f"解码异常: {e}")

        self.log_message.emit("视频解码线程已停止")

    def stop(self):
        """停止解码线程"""
        self.running = False
        self.wait(1000)


# ============== 网络接收线程 ==============
class NetworkReceiver(QThread):
    """网络数据接收线程"""
    packet_ready = pyqtSignal(bytes)
    connection_status = pyqtSignal(bool, str)
    log_message = pyqtSignal(str)
    stats_update = pyqtSignal(dict)

    def __init__(self, host='0.0.0.0', port=8888):
        super().__init__()
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.running = False
        self.connected = False
        self.bytes_received = 0
        self.packets_received = 0
        self.last_stats_time = time.time()

    def run(self):
        """网络接收主循环"""
        self.running = True

        try:
            # 创建服务器socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.server_socket.settimeout(1.0)

            self.log_message.emit(f"服务器已启动，监听 {self.host}:{self.port}")
            self.connection_status.emit(False, "等待连接...")

            while self.running:
                try:
                    # 等待客户端连接
                    self.client_socket, addr = self.server_socket.accept()
                    self.connected = True
                    self.log_message.emit(f"客户端已连接: {addr}")
                    self.connection_status.emit(True, f"已连接: {addr[0]}:{addr[1]}")

                    # 设置超时
                    self.client_socket.settimeout(5.0)

                    # 接收数据循环
                    while self.running and self.connected:
                        try:
                            # 接收头部 (8字节: total_size + nalu_count)
                            header = self._recv_all(8)
                            if not header or len(header) != 8:
                                break

                            # 解析头部
                            total_size, nalu_count = struct.unpack("<LL", header)

                            # 验证数据合理性
                            if total_size > 5 * 1024 * 1024 or nalu_count > 50:
                                self.log_message.emit(f"异常数据包: size={total_size}, count={nalu_count}")
                                break

                            # 接收NALU数据
                            data_buffer = self._recv_all(total_size)
                            if not data_buffer or len(data_buffer) != total_size:
                                self.log_message.emit(f"数据接收不完整: 期望{total_size}, 实际{len(data_buffer) if data_buffer else 0}")
                                break

                            # 组装完整数据包
                            full_packet = header + data_buffer

                            # 发送数据包信号
                            self.packet_ready.emit(full_packet)

                            # 更新统计
                            self.bytes_received += len(full_packet)
                            self.packets_received += 1

                            # 每秒更新统计
                            current_time = time.time()
                            if current_time - self.last_stats_time >= 1.0:
                                bitrate = (self.bytes_received * 8) / 1024
                                self.stats_update.emit({
                                    'bitrate': f"{bitrate:.1f}",
                                    'packets': self.packets_received
                                })
                                self.bytes_received = 0
                                self.packets_received = 0
                                self.last_stats_time = current_time

                        except socket.timeout:
                            continue
                        except Exception as e:
                            self.log_message.emit(f"接收数据错误: {e}")
                            break

                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_message.emit(f"服务器错误: {e}")

                finally:
                    # 清理客户端连接
                    if self.client_socket:
                        try:
                            self.client_socket.close()
                        except:
                            pass
                        self.client_socket = None

                    self.connected = False
                    self.connection_status.emit(False, "连接断开，等待重连...")
                    self.log_message.emit("客户端连接已关闭")

        except Exception as e:
            self.log_message.emit(f"服务器启动失败: {e}")
            self.connection_status.emit(False, f"错误: {e}")

        finally:
            if self.server_socket:
                try:
                    self.server_socket.close()
                except:
                    pass
            self.log_message.emit("服务器已停止")

    def _recv_all(self, size):
        """接收指定大小的数据"""
        data = bytearray()
        while len(data) < size and self.running:
            try:
                chunk = self.client_socket.recv(size - len(data))
                if not chunk:
                    return None
                data.extend(chunk)
            except socket.timeout:
                continue
            except:
                return None
        return bytes(data)

    def stop(self):
        """停止接收线程"""
        self.running = False
        if self.client_socket:
            try:
                self.client_socket.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        self.wait(2000)


# ============== 主窗口 ==============
class H265VideoReceiver(QMainWindow):
    """H265视频接收器主窗口"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("K230 H265 视频图传接收器")
        self.setGeometry(100, 100, 1200, 800)

        # 初始化变量
        self.current_frame = None
        self.is_recording = False
        self.video_writer = None
        self.frame_count = 0

        # 创建UI
        self._create_ui()

        # 创建线程
        self.network_receiver = None
        self.video_decoder = VideoDecoder()

        # 连接信号
        self.video_decoder.frame_ready.connect(self._update_frame)
        self.video_decoder.log_message.connect(self._add_log)
        self.video_decoder.stats_update.connect(self._update_decoder_stats)

        # 启动解码器
        self.video_decoder.start()

        self._add_log("程序已启动，请点击'启动服务器'开始接收视频")

    def _create_ui(self):
        """创建用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # 左侧: 视频显示区域
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)

        # 视频显示标签
        self.video_label = QLabel("等待视频流...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(640, 480)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #888888;
                font-size: 16px;
                border: 2px solid #333333;
                border-radius: 5px;
            }
        """)
        left_layout.addWidget(self.video_label)

        # 状态栏
        self.status_frame = QWidget()
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(0, 0, 0, 0)

        self.resolution_label = QLabel("分辨率: --")
        self.fps_label = QLabel("FPS: --")
        self.bitrate_label = QLabel("码率: -- Kbps")
        self.buffer_label = QLabel("缓冲: --")

        for label in [self.resolution_label, self.fps_label, self.bitrate_label, self.buffer_label]:
            label.setStyleSheet("""
                QLabel {
                    background-color: #2d2d2d;
                    color: #00ff00;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-family: Consolas, monospace;
                }
            """)
            status_layout.addWidget(label)

        status_layout.addStretch()
        left_layout.addWidget(self.status_frame)

        splitter.addWidget(left_panel)

        # 右侧: 控制面板
        right_panel = QWidget()
        right_panel.setMaximumWidth(350)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)

        # 连接设置组
        conn_group = QGroupBox("连接设置")
        conn_layout = QVBoxLayout(conn_group)

        ip_layout = QHBoxLayout()
        ip_layout.addWidget(QLabel("监听IP:"))
        self.ip_input = QLineEdit("0.0.0.0")
        ip_layout.addWidget(self.ip_input)
        conn_layout.addLayout(ip_layout)

        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("端口:"))
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(8888)
        port_layout.addWidget(self.port_input)
        conn_layout.addLayout(port_layout)

        btn_layout = QHBoxLayout()

        self.start_btn = QPushButton("启动服务器")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #218838; }
        """)
        self.start_btn.clicked.connect(self._toggle_server)
        btn_layout.addWidget(self.start_btn)

        self.record_btn = QPushButton("开始录制")
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #dc3545;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #c82333; }
        """)
        self.record_btn.clicked.connect(self._toggle_record)
        self.record_btn.setEnabled(False)
        btn_layout.addWidget(self.record_btn)

        conn_layout.addLayout(btn_layout)

        self.conn_status_label = QLabel("状态: 未启动")
        self.conn_status_label.setStyleSheet("QLabel { color: #ffc107; font-weight: bold; padding: 5px; }")
        conn_layout.addWidget(self.conn_status_label)

        right_layout.addWidget(conn_group)

        # 截图按钮
        snapshot_btn = QPushButton("截图保存")
        snapshot_btn.setStyleSheet("""
            QPushButton {
                background-color: #17a2b8;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #138496; }
        """)
        snapshot_btn.clicked.connect(self._take_snapshot)
        right_layout.addWidget(snapshot_btn)

        # 日志显示
        log_group = QGroupBox("运行日志")
        log_layout = QVBoxLayout(log_group)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumBlockCount(500)
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1a1a1a;
                color: #00ff00;
                font-family: Consolas, monospace;
                font-size: 11px;
                border: 1px solid #333333;
                border-radius: 3px;
            }
        """)
        log_layout.addWidget(self.log_text)

        right_layout.addWidget(log_group)

        # 说明信息
        info_label = QLabel(
            "使用说明:\n"
            "1. 先启动PC端服务器\n"
            "2. 再启动K230设备\n"
            "3. 视频流自动显示\n"
            "4. 支持H265/HEVC编码"
        )
        info_label.setStyleSheet("QLabel { color: #888888; font-size: 11px; padding: 10px; background-color: #2d2d2d; border-radius: 5px; }")
        info_label.setWordWrap(True)
        right_layout.addWidget(info_label)

        right_layout.addStretch()
        splitter.addWidget(right_panel)
        splitter.setSizes([850, 350])

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    def _toggle_server(self):
        """启动/停止服务器"""
        if self.network_receiver is None or not self.network_receiver.isRunning():
            host = self.ip_input.text() or "0.0.0.0"
            port = self.port_input.value()

            self.network_receiver = NetworkReceiver(host, port)
            self.network_receiver.packet_ready.connect(self._process_packet)
            self.network_receiver.connection_status.connect(self._update_connection_status)
            self.network_receiver.log_message.connect(self._add_log)
            self.network_receiver.stats_update.connect(self._update_network_stats)

            self.network_receiver.start()

            self.start_btn.setText("停止服务器")
            self.start_btn.setStyleSheet("""
                QPushButton { background-color: #dc3545; color: white; padding: 10px; font-weight: bold; border-radius: 5px; }
                QPushButton:hover { background-color: #c82333; }
            """)
            self.ip_input.setEnabled(False)
            self.port_input.setEnabled(False)

        else:
            self.network_receiver.stop()
            self.network_receiver = None

            self.start_btn.setText("启动服务器")
            self.start_btn.setStyleSheet("""
                QPushButton { background-color: #28a745; color: white; padding: 10px; font-weight: bold; border-radius: 5px; }
                QPushButton:hover { background-color: #218838; }
            """)
            self.ip_input.setEnabled(True)
            self.port_input.setEnabled(True)
            self.record_btn.setEnabled(False)

    def _process_packet(self, packet_data):
        """处理接收到的数据包"""
        try:
            if len(packet_data) < 8:
                return

            # 解析头部
            total_size, nalu_count = struct.unpack("<LL", packet_data[:8])
            data_buffer = packet_data[8:]

            # 验证数据
            if len(data_buffer) < total_size:
                self._add_log(f"数据包不完整: 期望{total_size}, 实际{len(data_buffer)}")
                return

            # 提取所有NALU数据
            offset = 0
            for i in range(nalu_count):
                if offset + 4 > len(data_buffer):
                    break

                nalu_size = struct.unpack("<L", data_buffer[offset:offset+4])[0]
                offset += 4

                if offset + nalu_size > len(data_buffer):
                    self._add_log(f"NALU数据超出范围: size={nalu_size}, offset={offset}, buffer={len(data_buffer)}")
                    break

                nalu_data = data_buffer[offset:offset+nalu_size]
                offset += nalu_size

                # 发送到解码器
                if nalu_data:
                    self.video_decoder.add_packet(nalu_data)

        except Exception as e:
            self._add_log(f"数据包处理错误: {e}")

    def _update_frame(self, frame):
        """更新视频帧显示"""
        try:
            self.current_frame = frame
            self.frame_count += 1

            # 录制
            if self.is_recording and self.video_writer is not None:
                # 转换为BGR格式用于录制
                bgr_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                self.video_writer.write(bgr_frame)

            # 获取显示区域大小
            label_width = max(self.video_label.width(), 320)
            label_height = max(self.video_label.height(), 240)

            # 获取帧尺寸
            height, width, channels = frame.shape

            # 缩放以适应显示区域
            scale = min(label_width / width, label_height / height)
            new_width = max(int(width * scale), 1)
            new_height = max(int(height * scale), 1)

            # 使用OpenCV缩放
            resized_frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_LINEAR)

            # 创建QImage - 使用copy确保数据连续
            height, width, channels = resized_frame.shape
            bytes_per_line = channels * width

            # 确保数据是连续的
            if not resized_frame.flags['C_CONTIGUOUS']:
                resized_frame = np.ascontiguousarray(resized_frame)

            q_image = QImage(resized_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image.copy())  # 使用copy避免数据问题

            self.video_label.setPixmap(pixmap)

        except Exception as e:
            if self.frame_count % 30 == 1:
                self._add_log(f"帧显示错误: {e}")

    def _update_connection_status(self, connected, message):
        """更新连接状态"""
        if connected:
            self.conn_status_label.setText(f"状态: {message}")
            self.conn_status_label.setStyleSheet("QLabel { color: #28a745; font-weight: bold; padding: 5px; }")
            self.record_btn.setEnabled(True)
        else:
            self.conn_status_label.setText(f"状态: {message}")
            self.conn_status_label.setStyleSheet("QLabel { color: #ffc107; font-weight: bold; padding: 5px; }")
            self.record_btn.setEnabled(False)

    def _update_decoder_stats(self, stats):
        """更新解码器统计信息"""
        self.fps_label.setText(f"FPS: {stats.get('fps', '--')}")
        self.resolution_label.setText(f"分辨率: {stats.get('resolution', '--')}")
        self.buffer_label.setText(f"缓冲: {stats.get('buffer_size', '--')}")

    def _update_network_stats(self, stats):
        """更新网络统计信息"""
        self.bitrate_label.setText(f"码率: {stats.get('bitrate', '--')} Kbps")

    def _add_log(self, message):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.appendPlainText(f"[{timestamp}] {message}")

    def _toggle_record(self):
        """开始/停止录制"""
        if not self.is_recording:
            if self.current_frame is None:
                QMessageBox.warning(self, "警告", "没有视频流，无法录制")
                return

            filename = f"record_{datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
            height, width = self.current_frame.shape[:2]

            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(filename, fourcc, 30.0, (width, height))

            if self.video_writer.isOpened():
                self.is_recording = True
                self.record_btn.setText("停止录制")
                self._add_log(f"开始录制: {filename}")
            else:
                QMessageBox.critical(self, "错误", "无法创建视频文件")
        else:
            self.is_recording = False
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
            self.record_btn.setText("开始录制")
            self._add_log("录制已停止")

    def _take_snapshot(self):
        """截图保存"""
        if self.current_frame is None:
            QMessageBox.warning(self, "警告", "没有视频流，无法截图")
            return

        filename = f"snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        # 转换为BGR保存
        bgr_frame = cv2.cvtColor(self.current_frame, cv2.COLOR_RGB2BGR)
        cv2.imwrite(filename, bgr_frame)
        self._add_log(f"截图已保存: {filename}")
        QMessageBox.information(self, "截图", f"已保存到: {filename}")

    def closeEvent(self, event):
        """窗口关闭事件"""
        if self.is_recording and self.video_writer:
            self.video_writer.release()

        if self.video_decoder:
            self.video_decoder.stop()

        if self.network_receiver:
            self.network_receiver.stop()

        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setStyleSheet("""
        QMainWindow { background-color: #1a1a1a; }
        QGroupBox { color: #ffffff; font-weight: bold; border: 1px solid #444444; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
        QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
        QLabel { color: #cccccc; }
        QLineEdit, QSpinBox { background-color: #2d2d2d; color: #ffffff; border: 1px solid #444444; border-radius: 3px; padding: 5px; }
    """)

    window = H265VideoReceiver()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
