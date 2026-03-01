# -*- coding: utf-8 -*-
"""
K230 H265 视频接收组件 - 稳定版
固定 IP: 192.168.137.1:8888
"""

import sys
import numpy as np
import av
import time
import socket
import struct
import threading
from queue import Queue, Full
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QVBoxLayout, 
    QHBoxLayout, QMainWindow, QGroupBox, QFormLayout, QSpinBox
)

print(f"[*] PyAV 版本: {av.__version__}")


# ============== 视频接收和解码线程 ==============
class VideoThread(QThread):
    """视频接收+解码线程"""
    frame_ready = pyqtSignal(np.ndarray)
    status_signal = pyqtSignal(str, str)
    
    def __init__(self, bind_ip="192.168.137.1", port=8888):
        super().__init__()
        self.bind_ip = bind_ip
        self.port = port
        self.running = False
        self.codec = None
        
    def init_decoder(self):
        """初始化 H265 解码器"""
        try:
            try:
                self.codec = av.CodecContext.create('hevc', 'r')
            except:
                codec = av.Codec('hevc', 'r')
                self.codec = av.CodecContext.create(codec)
            
            # 设置多线程解码
            try:
                self.codec.thread_type = 'FRAME'
                self.codec.thread_count = 2
            except:
                pass
            
            print("[*] H265 解码器初始化成功")
            return True
        except Exception as e:
            print(f"[!] 解码器初始化失败: {e}")
            return False
    
    def decode(self, data):
        """解码 H265 数据"""
        if not self.codec or not data:
            return None
        
        try:
            packet = av.Packet(data)
            packets = self.codec.parse(packet)
            
            for pkt in packets:
                try:
                    frames = self.codec.decode(pkt)
                    for frame in frames:
                        return frame.to_rgb().to_ndarray()
                except av.AVError:
                    continue
        except:
            pass
        return None
    
    def run(self):
        """主循环"""
        self.running = True
        
        # 初始化解码器
        if not self.init_decoder():
            self.status_signal.emit("error", "解码器初始化失败")
            return
        
        # 创建服务器
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
            server.bind((self.bind_ip, self.port))
            server.listen(1)
            server.settimeout(1.0)
            
            print(f"[*] 服务器启动: {self.bind_ip}:{self.port}")
            self.status_signal.emit("info", f"等待连接 {self.bind_ip}:{self.port}")
        except Exception as e:
            print(f"[!] 服务器启动失败: {e}")
            self.status_signal.emit("error", f"启动失败: {e}")
            return
        
        while self.running:
            try:
                # 等待连接
                client, addr = server.accept()
                client.settimeout(5.0)
                
                # 低延迟设置
                try:
                    client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except:
                    pass
                
                print(f"[+] 客户端连接: {addr}")
                self.status_signal.emit("success", f"已连接: {addr[0]}")
                
                # 处理连接
                self.handle_client(client)
                
            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    print(f"[!] 接受连接错误: {e}")
        
        # 清理
        try:
            server.close()
        except:
            pass
        
        if self.codec:
            try:
                self.codec.close()
            except:
                pass
    
    def handle_client(self, client):
        """处理客户端数据"""
        buffer = b''
        frame_count = 0
        
        try:
            while self.running:
                # 接收数据
                try:
                    data = client.recv(131072)
                    if not data:
                        break
                    buffer += data
                except socket.timeout:
                    continue
                except Exception as e:
                    break
                
                # 解析帧
                while len(buffer) >= 8:
                    try:
                        total_size, nalu_count = struct.unpack("<LL", buffer[:8])
                    except:
                        buffer = buffer[1:]
                        continue
                    
                    # 安全检查
                    if total_size > 2000000 or nalu_count > 500:
                        buffer = buffer[1:]
                        continue
                    
                    if len(buffer) < 8 + total_size:
                        break
                    
                    # 提取 H265 数据
                    frame_data = buffer[8:8+total_size]
                    buffer = buffer[8+total_size:]
                    
                    # 解析 NALU
                    nal_data = bytearray()
                    offset = 0
                    for i in range(nalu_count):
                        if offset + 4 > len(frame_data):
                            break
                        size = struct.unpack("<L", frame_data[offset:offset+4])[0]
                        offset += 4
                        if offset + size > len(frame_data):
                            break
                        nal_data.extend(b'\x00\x00\x00\x01')
                        nal_data.extend(frame_data[offset:offset+size])
                        offset += size
                    
                    # 解码并发送
                    if nal_data:
                        frame = self.decode(bytes(nal_data))
                        if frame is not None:
                            self.frame_ready.emit(frame)
                            frame_count += 1
                            
        except Exception as e:
            print(f"[!] 处理客户端错误: {e}")
        finally:
            client.close()
            print("[*] 客户端断开")
            self.status_signal.emit("info", "连接断开，等待重连...")
    
    def stop(self):
        """停止"""
        self.running = False


# ============== 视频显示组件 ==============
class K230VideoWidget(QWidget):
    """K230 视频接收组件"""
    
    frame_received = pyqtSignal(np.ndarray)
    status_changed = pyqtSignal(str, str)
    fps_updated = pyqtSignal(float)
    
    def __init__(self, parent=None, width=640, height=480,
                 bind_ip="192.168.137.1", port=8888, show_controls=True):
        super().__init__(parent)
        
        self.bind_ip = bind_ip
        self.port = port
        self.show_controls = show_controls
        
        self.video_thread = None
        self.current_frame = None
        self.frame_lock = threading.Lock()
        self.frame_count = 0
        self.fps = 0.0
        self.last_fps_time = time.time()
        
        self.init_ui(width, height)
    
    def init_ui(self, width, height):
        """初始化 UI"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
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
        
        # 控制按钮
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
        
        # 显示刷新定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_display)
        self.timer.start(33)
    
    def start(self):
        """开始接收"""
        if self.video_thread is not None:
            return
        
        if self.show_controls:
            self.btn_start.setEnabled(False)
            self.btn_stop.setEnabled(True)
        
        self.video_thread = VideoThread(self.bind_ip, self.port)
        self.video_thread.frame_ready.connect(self.on_frame)
        self.video_thread.status_signal.connect(self.on_status)
        self.video_thread.start()
    
    def stop(self):
        """停止接收"""
        if self.video_thread:
            self.video_thread.stop()
            self.video_thread.wait(2000)
            self.video_thread = None
        
        if self.show_controls:
            self.btn_start.setEnabled(True)
            self.btn_stop.setEnabled(False)
        
        self.status_bar.setText("已停止")
        self.status_bar.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #e67e22;
                color: white;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
    
    def on_frame(self, frame):
        """收到帧"""
        with self.frame_lock:
            self.current_frame = frame
        
        self.frame_count += 1
        self.frame_received.emit(frame)
        
        now = time.time()
        if now - self.last_fps_time >= 1.0:
            self.fps = self.frame_count / (now - self.last_fps_time)
            self.fps_label.setText(f"FPS: {self.fps:.1f}")
            self.fps_updated.emit(self.fps)
            self.frame_count = 0
            self.last_fps_time = now
    
    def on_status(self, status_type, message):
        """状态更新"""
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
        self.status_changed.emit(status_type, message)
    
    def update_display(self):
        """更新显示"""
        with self.frame_lock:
            frame = self.current_frame
        
        if frame is not None:
            try:
                h, w, ch = frame.shape
                self.resolution_label.setText(f"分辨率: {w}×{h}")
                
                bytes_per_line = ch * w
                qt_image = QImage(
                    frame.data, w, h,
                    bytes_per_line, QImage.Format_RGB888
                )
                
                pixmap = QPixmap.fromImage(qt_image)
                scaled = pixmap.scaled(
                    self.video_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.video_label.setPixmap(scaled)
                
            except Exception as e:
                print(f"[!] 显示错误: {e}")
    
    def save_screenshot(self):
        """保存截图"""
        with self.frame_lock:
            frame = self.current_frame
        
        if frame is None:
            self.status_bar.setText("没有可保存的画面")
            return
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.bmp"
        
        try:
            h, w, _ = frame.shape
            bgr = frame[:, :, ::-1]
            
            row_size = (w * 3 + 3) & ~3
            img_size = row_size * h
            
            header = b'BM'
            header += struct.pack('<I', 54 + img_size)
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
                for i in range(h - 1, -1, -1):
                    row = bgr[i].tobytes()
                    padding = (4 - (len(row) % 4)) % 4
                    f.write(row + b'\x00' * padding)
            
            self.status_bar.setText(f"截图已保存: {filename}")
        except Exception as e:
            self.status_bar.setText(f"保存失败: {e}")
    
    def closeEvent(self, event):
        self.stop()
        event.accept()


# ============== 主窗口 ==============
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("K230 H265 视频接收")
        self.setGeometry(100, 100, 900, 700)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 配置
        config_group = QGroupBox("连接配置")
        config_layout = QFormLayout(config_group)
        
        self.ip_label = QLabel("192.168.137.1")
        self.ip_label.setStyleSheet("font-weight: bold; color: #27ae60;")
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(8888)
        
        config_layout.addRow("服务器 IP (固定):", self.ip_label)
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
        self.video_widget.status_changed.connect(self.on_status)
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
        
        self.statusBar().showMessage("就绪 - 点击开始接收")
    
    def start(self):
        self.video_widget.port = self.port_spin.value()
        self.video_widget.start()
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.port_spin.setEnabled(False)
    
    def stop(self):
        self.video_widget.stop()
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.port_spin.setEnabled(True)
    
    def on_status(self, t, msg):
        self.statusBar().showMessage(msg)
    
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
