# -*- coding: utf-8 -*-
"""
K230 H265 视频接收组件 - 调试版本
用于排查连接和显示问题
"""

import sys
import numpy as np
import av
import time
import socket
import struct
import threading
import traceback
from queue import Queue, Full, Empty
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, 
    QHBoxLayout, QMainWindow, QGroupBox, QFormLayout, QSpinBox,
    QTextEdit, QMessageBox
)

print(f"[*] PyAV 版本: {av.__version__}")
print(f"[*] 检查 FFmpeg 支持...")
try:
    print(f"    - libavcodec: {av.library_versions.get('libavcodec', 'unknown')}")
    print(f"    - libavformat: {av.library_versions.get('libavformat', 'unknown')}")
    print(f"    - libavutil: {av.library_versions.get('libavutil', 'unknown')}")
except Exception as e:
    print(f"    错误: {e}")


# ============== 日志组件 ==============
class LogWidget(QTextEdit):
    """日志显示组件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(150)
        self.setStyleSheet("font-family: Consolas, monospace; font-size: 10px;")
    
    def log(self, msg: str):
        """添加日志"""
        timestamp = time.strftime("%H:%M:%S")
        self.append(f"[{timestamp}] {msg}")
        # 滚动到底部
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())


# ============== 视频解码线程 ==============
class VideoDecoderThread(QThread):
    """独立解码线程"""
    frame_decoded = pyqtSignal(np.ndarray)
    log_signal = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = Queue(maxsize=3)
        self.running = False
        self.codec = None
        
    def init_decoder(self):
        """初始化 H265 解码器"""
        try:
            self.log_signal.emit("正在创建 H265 解码器...")
            
            # 尝试多种方式创建解码器
            try:
                # 方式 1: 使用 hevc 名称
                self.codec = av.CodecContext.create('hevc', 'r')
            except Exception as e1:
                self.log_signal.emit(f"方式1失败: {e1}")
                try:
                    # 方式 2: 使用 h265 名称
                    self.codec = av.CodecContext.create('h265', 'r')
                except Exception as e2:
                    self.log_signal.emit(f"方式2失败: {e2}")
                    # 方式 3: 查找解码器
                    codec = av.Codec('hevc', 'r')
                    self.codec = av.CodecContext.create(codec)
            
            # 设置线程数
            try:
                self.codec.thread_type = 'FRAME'
                self.codec.thread_count = 2
            except:
                pass
            
            self.log_signal.emit("H265 解码器创建成功")
            return True
            
        except Exception as e:
            self.log_signal.emit(f"解码器初始化失败: {e}")
            traceback.print_exc()
            return False
    
    def put_data(self, data: bytes) -> bool:
        """添加数据到解码队列"""
        try:
            self.queue.put_nowait(data)
            return True
        except Full:
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(data)
            except:
                pass
            return False
    
    def run(self):
        """解码主循环"""
        self.running = True
        frame_count = 0
        
        if not self.init_decoder():
            self.log_signal.emit("[错误] 解码器初始化失败，线程退出")
            return
        
        self.log_signal.emit("[解码线程] 开始运行")
        
        while self.running:
            try:
                data = self.queue.get(timeout=0.5)
                
                frame = self.decode_frame(data)
                if frame is not None:
                    self.frame_decoded.emit(frame)
                    frame_count += 1
                    
                    if frame_count % 30 == 0:
                        self.log_signal.emit(f"[解码] 已解码 {frame_count} 帧")
                        
            except Empty:
                continue
            except Exception as e:
                self.log_signal.emit(f"[解码错误] {e}")
                traceback.print_exc()
        
        self.log_signal.emit("[解码线程] 已停止")
    
    def decode_frame(self, data: bytes) -> np.ndarray:
        """解码 H265 数据"""
        if self.codec is None or not data:
            return None
        
        try:
            packet = av.Packet(data)
            packets = self.codec.parse(packet)
            
            if packets:
                for pkt in packets:
                    try:
                        frames = self.codec.decode(pkt)
                        for frame in frames:
                            return frame.to_rgb().to_ndarray()
                    except av.AVError as e:
                        continue
                    
        except Exception as e:
            pass
        
        return None
    
    def stop(self):
        """停止解码"""
        self.running = False
        if self.codec:
            try:
                self.codec.close()
            except:
                pass
            self.codec = None


# ============== 视频接收线程 ==============
class VideoReceiverThread(QThread):
    """视频接收线程"""
    status_changed = pyqtSignal(str, str)
    log_signal = pyqtSignal(str)
    
    def __init__(self, bind_ip: str, port: int, decoder: VideoDecoderThread, parent=None):
        super().__init__(parent)
        self.bind_ip = bind_ip
        self.port = port
        self.decoder = decoder
        self.running = False
        self.server_sock = None
        self.client_sock = None
        
    def run(self):
        """接收主循环"""
        self.running = True
        
        try:
            self.log_signal.emit(f"[网络] 创建 socket...")
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            self.log_signal.emit(f"[网络] 绑定到 {self.bind_ip}:{self.port}...")
            self.server_sock.bind((self.bind_ip, self.port))
            self.server_sock.listen(1)
            self.server_sock.settimeout(1.0)
            
            self.log_signal.emit(f"[网络] 服务器启动成功")
            self.status_changed.emit("info", f"等待连接 {self.bind_ip}:{self.port}")
            
            while self.running:
                try:
                    self.log_signal.emit("[网络] 等待客户端连接...")
                    self.client_sock, addr = self.server_sock.accept()
                    self.client_sock.settimeout(5.0)
                    
                    self.log_signal.emit(f"[网络] 客户端已连接: {addr}")
                    self.status_changed.emit("success", f"已连接: {addr[0]}")
                    
                    self.handle_connection()
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.log_signal.emit(f"[网络错误] {e}")
                        self.status_changed.emit("error", f"服务器错误: {e}")
                    break
                    
        except Exception as e:
            self.log_signal.emit(f"[启动错误] {e}")
            self.status_changed.emit("error", f"启动失败: {e}")
            traceback.print_exc()
        finally:
            self.cleanup()
    
    def handle_connection(self):
        """处理客户端连接"""
        buffer = b''
        packet_count = 0
        
        self.log_signal.emit("[接收] 开始接收数据...")
        
        try:
            while self.running:
                try:
                    chunk = self.client_sock.recv(65536)
                    if not chunk:
                        self.log_signal.emit("[接收] 连接断开 (无数据)")
                        break
                    buffer += chunk
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_signal.emit(f"[接收错误] {e}")
                    break
                
                # 处理缓冲区中的完整帧
                while len(buffer) >= 8:
                    try:
                        total_size, nalu_count = struct.unpack("<LL", buffer[:8])
                    except:
                        buffer = buffer[1:]
                        continue
                    
                    # 安全检查
                    if total_size > 2000000 or nalu_count > 500:
                        self.log_signal.emit(f"[警告] 异常数据: size={total_size}, count={nalu_count}")
                        buffer = buffer[1:]
                        continue
                    
                    if len(buffer) < 8 + total_size:
                        break
                    
                    data = buffer[8:8+total_size]
                    buffer = buffer[8+total_size:]
                    
                    nal_data = self.parse_nalus(data, nalu_count)
                    if nal_data and self.decoder:
                        self.decoder.put_data(nal_data)
                        packet_count += 1
                        
                        if packet_count % 30 == 0:
                            self.log_signal.emit(f"[接收] 已接收 {packet_count} 个数据包")
                        
        except Exception as e:
            self.log_signal.emit(f"[处理错误] {e}")
            traceback.print_exc()
        finally:
            if self.client_sock:
                try:
                    self.client_sock.close()
                except:
                    pass
                self.client_sock = None
            self.log_signal.emit("[网络] 连接断开")
            self.status_changed.emit("info", "连接断开，等待重连...")
    
    def parse_nalus(self, data: bytes, nalu_count: int) -> bytes:
        """解析 NALU 数据"""
        nal_data = bytearray()
        offset = 0
        
        for i in range(nalu_count):
            if offset + 4 > len(data):
                break
            
            size = struct.unpack("<L", data[offset:offset+4])[0]
            offset += 4
            
            if offset + size > len(data):
                break
            
            nal_data.extend(b'\x00\x00\x00\x01')
            nal_data.extend(data[offset:offset+size])
            offset += size
        
        return bytes(nal_data) if nal_data else None
    
    def cleanup(self):
        """清理资源"""
        if self.client_sock:
            try:
                self.client_sock.close()
            except:
                pass
        
        if self.server_sock:
            try:
                self.server_sock.close()
            except:
                pass
        
        self.log_signal.emit("[网络] 资源已清理")
    
    def stop(self):
        """停止接收"""
        self.log_signal.emit("[网络] 正在停止...")
        self.running = False
        self.cleanup()


# ============== 视频显示组件 ==============
class K230VideoWidget(QWidget):
    """K230 视频接收组件"""
    
    frame_received = pyqtSignal(np.ndarray)
    status_changed = pyqtSignal(str, str)
    
    def __init__(self, parent=None, width: int = 640, height: int = 480,
                 bind_ip: str = "192.168.137.1", port: int = 8888):
        super().__init__(parent)
        
        self.bind_ip = bind_ip
        self.port = port
        
        self.decoder_thread = None
        self.receiver_thread = None
        self.display_lock = threading.Lock()
        self.display_frame = None
        self.frame_count = 0
        self.fps = 0.0
        self.last_fps_time = time.time()
        
        self.init_ui(width, height)
    
    def init_ui(self, width: int, height: int):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # 视频显示
        self.video_label = QLabel(f"等待连接...\n{self.bind_ip}:{self.port}")
        self.video_label.setFixedSize(width, height)
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("""
            QLabel {
                background-color: #1a1a1a;
                color: #00ff00;
                font-size: 14px;
                border: 2px solid #333;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.video_label)
        
        # 日志显示
        self.log_widget = LogWidget(self)
        layout.addWidget(self.log_widget)
        
        # 状态栏
        self.status_bar = QLabel("就绪")
        self.status_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #2c3e50;
                color: white;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.status_bar)
        
        # 刷新定时器
        self.display_timer = QTimer(self)
        self.display_timer.timeout.connect(self.update_display)
        self.display_timer.start(33)
    
    def log(self, msg: str):
        """记录日志"""
        self.log_widget.log(msg)
    
    def start(self):
        """开始接收"""
        self.log("=" * 50)
        self.log("启动视频接收...")
        
        # 创建解码线程
        self.decoder_thread = VideoDecoderThread(self)
        self.decoder_thread.frame_decoded.connect(self.on_frame_decoded)
        self.decoder_thread.log_signal.connect(self.log)
        self.decoder_thread.start()
        
        # 等待解码器初始化
        time.sleep(0.5)
        
        # 创建接收线程
        self.receiver_thread = VideoReceiverThread(
            self.bind_ip, self.port, self.decoder_thread, self
        )
        self.receiver_thread.status_changed.connect(self.on_status_changed)
        self.receiver_thread.log_signal.connect(self.log)
        self.receiver_thread.start()
    
    def stop(self):
        """停止接收"""
        self.log("停止视频接收...")
        
        if self.receiver_thread:
            self.receiver_thread.stop()
            self.receiver_thread.wait(1000)
            self.receiver_thread = None
        
        if self.decoder_thread:
            self.decoder_thread.stop()
            self.decoder_thread.wait(1000)
            self.decoder_thread = None
        
        self.update_status_display("info", "已停止")
    
    def on_frame_decoded(self, frame: np.ndarray):
        """解码完成"""
        with self.display_lock:
            self.display_frame = frame.copy()
        
        self.frame_count += 1
        self.frame_received.emit(frame)
        
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            self.fps = self.frame_count / (now - self.last_fps_time)
            self.frame_count = 0
            self.last_fps_time = now
    
    def on_status_changed(self, status_type: str, message: str):
        """状态变化"""
        self.update_status_display(status_type, message)
        self.status_changed.emit(status_type, message)
    
    def update_status_display(self, status_type: str, message: str):
        """更新状态显示"""
        colors = {
            "info": "#3498db",
            "success": "#27ae60", 
            "warning": "#f39c12",
            "error": "#e74c3c"
        }
        color = colors.get(status_type, "#95a5a6")
        
        self.status_bar.setText(message)
        self.status_bar.setStyleSheet(f"""
            QLabel {{
                padding: 8px;
                background-color: {color};
                color: white;
                border-radius: 4px;
            }}
        """)
    
    def update_display(self):
        """更新显示"""
        frame = None
        with self.display_lock:
            if self.display_frame is not None:
                frame = self.display_frame
                self.display_frame = None
        
        if frame is not None:
            try:
                h, w, ch = frame.shape
                
                bytes_per_line = ch * w
                qt_image = QImage(
                    frame.data, w, h, 
                    bytes_per_line, QImage.Format_RGB888
                )
                
                pixmap = QPixmap.fromImage(qt_image)
                scaled_pixmap = pixmap.scaled(
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)
                
            except Exception as e:
                self.log(f"[显示错误] {e}")
    
    def closeEvent(self, event):
        """关闭"""
        self.stop()
        event.accept()


# ============== 主窗口 ==============
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("K230 视频接收 - 调试版")
        self.setGeometry(100, 100, 900, 750)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 配置
        config_group = QGroupBox("连接配置")
        config_layout = QFormLayout(config_group)
        
        self.ip_input = QSpinBox()
        self.ip_input.setRange(1, 255)
        self.ip_input.setValue(137)  # 192.168.x.1
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(8888)
        
        config_layout.addRow("IP: 192.168.", self.ip_input)
        config_layout.addRow("端口:", self.port_spin)
        
        layout.addWidget(config_group)
        
        # 视频组件
        self.video_widget = K230VideoWidget(
            parent=self,
            width=800,
            height=500,
            bind_ip="192.168.137.1",
            port=8888
        )
        layout.addWidget(self.video_widget, 1)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("▶ 开始接收")
        self.btn_start.setStyleSheet("""
            QPushButton {
                padding: 12px 30px;
                font-size: 14px;
                font-weight: bold;
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
            }
        """)
        self.btn_start.clicked.connect(self.start)
        
        self.btn_stop = QPushButton("⏹ 停止")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                padding: 12px 30px;
                font-size: 14px;
                font-weight: bold;
                background-color: #c0392b;
                color: white;
                border: none;
                border-radius: 5px;
            }
        """)
        self.btn_stop.clicked.connect(self.stop)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addStretch(1)
        
        layout.addLayout(btn_layout)
        
        # 状态栏
        self.statusBar().showMessage("就绪")
        
        self.video_widget.status_changed.connect(self.on_status)
    
    def start(self):
        ip = f"192.168.{self.ip_input.value()}.1"
        self.video_widget.bind_ip = ip
        self.video_widget.port = self.port_spin.value()
        
        self.video_widget.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.ip_input.setEnabled(False)
        self.port_spin.setEnabled(False)
    
    def stop(self):
        self.video_widget.stop()
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.ip_input.setEnabled(True)
        self.port_spin.setEnabled(True)
    
    def on_status(self, t, msg):
        self.statusBar().showText(msg)
    
    def closeEvent(self, event):
        self.video_widget.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
