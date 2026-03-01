# -*- coding: utf-8 -*-
"""
K230 H265 视频接收组件 (PyAV 版 - 修复卡顿)
固定 IP: 192.168.137.1:8888

依赖:
    pip install PyQt5 av numpy
"""

import sys
import numpy as np
import av
import time
import socket
import struct
import threading
from queue import Queue, Full, Empty
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, 
    QHBoxLayout, QMainWindow, QGroupBox, QFormLayout, QSpinBox,
    QStatusBar
)


# ============== 视频解码线程 ==============
class VideoDecoderThread(QThread):
    """独立解码线程，避免阻塞接收"""
    frame_decoded = pyqtSignal(np.ndarray)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.queue = Queue(maxsize=5)  # 限制缓冲区大小
        self.running = False
        self.codec = None
        
    def init_decoder(self):
        """初始化 H265 解码器"""
        try:
            # 创建解码器
            self.codec = av.CodecContext.create('hevc', 'r')
            # 设置线程数，提高解码性能
            self.codec.thread_type = 'FRAME'
            self.codec.thread_count = 2
            return True
        except Exception as e:
            print(f"[!] 解码器初始化失败: {e}")
            return False
    
    def put_data(self, data: bytes) -> bool:
        """添加数据到解码队列"""
        try:
            self.queue.put_nowait(data)
            return True
        except Full:
            # 队列满，丢弃旧数据
            try:
                self.queue.get_nowait()
                self.queue.put_nowait(data)
            except:
                pass
            return False
    
    def run(self):
        """解码主循环"""
        self.running = True
        
        if not self.init_decoder():
            return
        
        while self.running:
            try:
                data = self.queue.get(timeout=0.1)
                frame = self.decode_frame(data)
                if frame is not None:
                    self.frame_decoded.emit(frame)
            except Empty:
                continue
            except Exception as e:
                print(f"[!] 解码错误: {e}")
    
    def decode_frame(self, data: bytes) -> np.ndarray:
        """解码 H265 数据"""
        if self.codec is None or not data:
            return None

        try:
            packet = av.Packet(data)
            packets = self.codec.parse(packet)

            for pkt in packets:
                try:
                    frames = self.codec.decode(pkt)
                    for frame in frames:
                        # 转换为 RGB numpy 数组
                        return frame.to_rgb().to_ndarray()
                except av.AVError as e:
                    # 解码错误，继续尝试
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
    status_changed = pyqtSignal(str, str)  # type, message
    
    def __init__(self, bind_ip: str = "192.168.137.1", port: int = 8888, 
                 decoder: VideoDecoderThread = None, parent=None):
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
            # 创建服务器
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind((self.bind_ip, self.port))
            self.server_sock.listen(1)
            self.server_sock.settimeout(1.0)
            
            self.status_changed.emit("info", f"等待连接 {self.bind_ip}:{self.port}")
            
            while self.running:
                try:
                    self.client_sock, addr = self.server_sock.accept()
                    self.client_sock.settimeout(5.0)
                    self.status_changed.emit("success", f"已连接: {addr[0]}")
                    self.handle_connection()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.status_changed.emit("error", f"服务器错误: {e}")
                    break
                    
        except Exception as e:
            self.status_changed.emit("error", f"启动失败: {e}")
        finally:
            self.cleanup()
    
    def handle_connection(self):
        """处理客户端连接"""
        buffer = b''
        
        try:
            while self.running:
                # 接收数据
                try:
                    chunk = self.client_sock.recv(65536)
                    if not chunk:
                        break
                    buffer += chunk
                except socket.timeout:
                    continue
                except Exception as e:
                    break
                
                # 处理缓冲区中的完整帧
                while len(buffer) >= 8:
                    # 解析头部
                    total_size, nalu_count = struct.unpack("<LL", buffer[:8])
                    
                    # 安全检查
                    if total_size > 1000000 or nalu_count > 200:
                        buffer = buffer[1:]  # 丢弃一个字节，重新同步
                        continue
                    
                    # 检查是否收到完整数据
                    if len(buffer) < 8 + total_size:
                        break
                    
                    # 提取数据
                    data = buffer[8:8+total_size]
                    buffer = buffer[8+total_size:]
                    
                    # 解析 NALU
                    nal_data = self.parse_nalus(data, nalu_count)
                    if nal_data and self.decoder:
                        self.decoder.put_data(nal_data)
                        
        except Exception as e:
            self.status_changed.emit("error", f"接收错误: {e}")
        finally:
            if self.client_sock:
                try:
                    self.client_sock.close()
                except:
                    pass
                self.client_sock = None
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
            
            # 添加 NALU 起始码
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
    
    def stop(self):
        """停止接收"""
        self.running = False
        self.cleanup()


# ============== 视频显示组件 ==============
class K230VideoWidget(QWidget):
    """K230 视频接收组件"""
    
    # 信号
    frame_received = pyqtSignal(np.ndarray)
    status_changed = pyqtSignal(str, str)
    fps_updated = pyqtSignal(float)
    
    def __init__(self, parent=None, width: int = 640, height: int = 480,
                 bind_ip: str = "192.168.137.1", port: int = 8888,
                 show_controls: bool = True):
        super().__init__(parent)
        
        self.bind_ip = bind_ip
        self.port = port
        self.show_controls = show_controls
        
        self.decoder_thread = None
        self.receiver_thread = None
        self.current_frame = None
        self.frame_count = 0
        self.fps = 0.0
        self.last_fps_time = time.time()
        self.display_frame = None
        self.display_lock = threading.Lock()
        
        self.init_ui(width, height)
    
    def init_ui(self, width: int, height: int):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # 视频显示标签
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
        
        # 控制按钮区域
        if self.show_controls:
            btn_layout = QHBoxLayout()
            
            self.btn_start = QPushButton("开始")
            self.btn_start.setStyleSheet("""
                QPushButton {
                    padding: 8px 20px;
                    font-weight: bold;
                    background-color: #27ae60;
                    color: white;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #2ecc71; }
                QPushButton:disabled { background-color: #7f8c8d; }
            """)
            self.btn_start.clicked.connect(self.start)
            
            self.btn_stop = QPushButton("停止")
            self.btn_stop.setStyleSheet("""
                QPushButton {
                    padding: 8px 20px;
                    font-weight: bold;
                    background-color: #c0392b;
                    color: white;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #e74c3c; }
                QPushButton:disabled { background-color: #7f8c8d; }
            """)
            self.btn_stop.clicked.connect(self.stop)
            self.btn_stop.setEnabled(False)
            
            self.btn_save = QPushButton("截图")
            self.btn_save.setStyleSheet("""
                QPushButton {
                    padding: 8px 20px;
                    font-weight: bold;
                    background-color: #3498db;
                    color: white;
                    border: none;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #5dade2; }
            """)
            self.btn_save.clicked.connect(self.save_screenshot)
            
            btn_layout.addStretch(1)
            btn_layout.addWidget(self.btn_start)
            btn_layout.addWidget(self.btn_stop)
            btn_layout.addWidget(self.btn_save)
            btn_layout.addStretch(1)
            
            layout.addLayout(btn_layout)
        
        # 状态栏
        self.status_bar = QLabel("就绪")
        self.status_bar.setAlignment(Qt.AlignCenter)
        self.status_bar.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #2c3e50;
                color: white;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.status_bar)
        
        # 信息显示
        info_layout = QHBoxLayout()
        
        self.resolution_label = QLabel("分辨率: -")
        self.fps_label = QLabel("FPS: 0.0")
        self.ip_label = QLabel(f"{self.bind_ip}:{self.port}")
        
        for lbl in [self.resolution_label, self.fps_label, self.ip_label]:
            lbl.setStyleSheet("font-size: 11px; color: #666;")
            info_layout.addWidget(lbl)
        
        info_layout.addStretch(1)
        layout.addLayout(info_layout)
        
        # 刷新定时器 (30fps)
        self.display_timer = QTimer(self)
        self.display_timer.timeout.connect(self.update_display)
        self.display_timer.start(33)
    
    def start(self):
        """开始接收视频"""
        if self.receiver_thread is not None:
            return
        
        if self.show_controls:
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
        
        # 创建解码线程
        self.decoder_thread = VideoDecoderThread(self)
        self.decoder_thread.frame_decoded.connect(self.on_frame_decoded)
        self.decoder_thread.start()
        
        # 创建接收线程
        self.receiver_thread = VideoReceiverThread(
            self.bind_ip, self.port, self.decoder_thread, self
        )
        self.receiver_thread.status_changed.connect(self.on_status_changed)
        self.receiver_thread.start()
    
    def stop(self):
        """停止接收视频"""
        if self.receiver_thread:
            self.receiver_thread.stop()
            self.receiver_thread.wait(1000)
            self.receiver_thread = None
        
        if self.decoder_thread:
            self.decoder_thread.stop()
            self.decoder_thread.wait(1000)
            self.decoder_thread = None
        
        if self.show_controls:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
        
        self.update_status_display("info", "已停止")
    
    def on_frame_decoded(self, frame: np.ndarray):
        """解码完成回调"""
        with self.display_lock:
            self.display_frame = frame.copy()
            self.last_frame = frame.copy()
        
        self.frame_count += 1
        self.frame_received.emit(frame)
        
        # 计算 FPS
        now = time.time()
        elapsed = now - self.last_fps_time
        if elapsed >= 1.0:
            self.fps = self.frame_count / elapsed
            self.fps_label.setText(f"FPS: {self.fps:.1f}")
            self.fps_updated.emit(self.fps)
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
                font-size: 12px;
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
                self.resolution_label.setText(f"分辨率: {w}×{h}")
                
                # 创建 QImage
                bytes_per_line = ch * w
                qt_image = QImage(
                    frame.data, w, h, 
                    bytes_per_line, QImage.Format_RGB888
                )
                
                # 缩放并显示
                pixmap = QPixmap.fromImage(qt_image)
                scaled_pixmap = pixmap.scaled(
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled_pixmap)
                
            except Exception as e:
                print(f"[!] 显示错误: {e}")
    
    def save_screenshot(self):
        """保存截图"""
        # 获取当前帧
        frame = None
        with self.display_lock:
            if hasattr(self, 'last_frame'):
                frame = self.last_frame
        
        if frame is None:
            self.status_bar.setText("没有可保存的画面")
            return
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.bmp"
        
        try:
            # 保存为 BMP
            h, w, _ = frame.shape
            
            # 转换为 BGR
            bgr_frame = frame[:, :, ::-1]
            
            # BMP 文件头
            row_size = (w * 3 + 3) & ~3  # 每行对齐到 4 字节
            img_size = row_size * h
            file_size = 54 + img_size
            
            header = b'BM'
            header += struct.pack('<I', file_size)
            header += b'\x00\x00\x00\x00'
            header += struct.pack('<I', 54)
            header += struct.pack('<I', 40)
            header += struct.pack('<i', w)
            header += struct.pack('<i', h)
            header += struct.pack('<H', 1)
            header += struct.pack('<H', 24)
            header += struct.pack('<I', 0)
            header += struct.pack('<I', img_size)
            header += struct.pack('<i', 2835)
            header += struct.pack('<i', 2835)
            header += struct.pack('<I', 0)
            header += struct.pack('<I', 0)
            
            with open(filename, 'wb') as f:
                f.write(header)
                # 从下到上写入像素
                for i in range(h - 1, -1, -1):
                    row = bgr_frame[i].tobytes()
                    # 填充到 4 字节对齐
                    padding = (4 - (len(row) % 4)) % 4
                    f.write(row + b'\x00' * padding)
            
            self.status_bar.setText(f"截图已保存: {filename}")
            
        except Exception as e:
            self.status_bar.setText(f"保存失败: {e}")
    
    def get_frame(self) -> np.ndarray:
        """获取当前帧"""
        with self.display_lock:
            return self.last_frame.copy() if hasattr(self, 'last_frame') else None
    
    def is_running(self) -> bool:
        """是否正在运行"""
        return (self.receiver_thread is not None and 
                self.receiver_thread.isRunning())
    
    def closeEvent(self, event):
        """关闭事件"""
        self.stop()
        event.accept()


# ============== 主窗口 ==============
class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("K230 H265 视频接收 (PyAV)")
        self.setGeometry(100, 100, 900, 700)
        
        # 中心部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 配置组
        config_group = QGroupBox("连接配置")
        config_layout = QFormLayout(config_group)
        
        self.ip_label = QLabel("192.168.137.1")
        self.ip_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(8888)
        
        config_layout.addRow("服务器 IP:", self.ip_label)
        config_layout.addRow("端口:", self.port_spin)
        
        layout.addWidget(config_group)
        
        # 视频组件
        self.video_widget = K230VideoWidget(
            parent=self,
            width=800,
            height=600,
            bind_ip="192.168.137.1",
            port=8888,
            show_controls=False
        )
        self.video_widget.status_changed.connect(self.on_status_changed)
        layout.addWidget(self.video_widget, 1)
        
        # 控制按钮
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
            QPushButton:hover { background-color: #2ecc71; }
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
            QPushButton:hover { background-color: #e74c3c; }
        """)
        self.btn_stop.clicked.connect(self.stop)
        
        self.btn_shot = QPushButton("📷 截图")
        self.btn_shot.setStyleSheet("""
            QPushButton {
                padding: 12px 30px;
                font-size: 14px;
                font-weight: bold;
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #5dade2; }
        """)
        self.btn_shot.clicked.connect(self.video_widget.save_screenshot)
        
        btn_layout.addStretch(1)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addWidget(self.btn_shot)
        btn_layout.addStretch(1)
        
        layout.addLayout(btn_layout)
        
        # 状态栏
        self.statusBar().showMessage("就绪 - 点击开始接收")
    
    def start(self):
        """开始"""
        self.video_widget.port = self.port_spin.value()
        self.video_widget.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.port_spin.setEnabled(False)
    
    def stop(self):
        """停止"""
        self.video_widget.stop()
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.port_spin.setEnabled(True)
    
    def on_status_changed(self, status_type, message):
        """状态变化"""
        self.statusBar().showMessage(message)
    
    def closeEvent(self, event):
        """关闭"""
        self.video_widget.stop()
        event.accept()


def main():
    """主函数"""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # 设置字体
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
