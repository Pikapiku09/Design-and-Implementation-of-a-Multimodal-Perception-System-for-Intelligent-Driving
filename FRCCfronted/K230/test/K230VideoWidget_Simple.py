# -*- coding: utf-8 -*-
"""
K230 H265 视频接收 - 简化版 (兼容 PyAV 15.x)
最小化实现，排除其他问题
"""

import sys
import socket
import struct
import time
import traceback
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *


class SimpleVideoReceiver(QThread):
    """简化版视频接收"""
    log_signal = pyqtSignal(str)
    frame_ready = pyqtSignal(bytes, int, int)  # data, width, height
    
    def __init__(self, bind_ip="192.168.137.1", port=8888):
        super().__init__()
        self.bind_ip = bind_ip
        self.port = port
        self.running = False
        
    def run(self):
        self.running = True
        self.log_signal.emit(f"[*] 启动服务器 {self.bind_ip}:{self.port}")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((self.bind_ip, self.port))
            sock.listen(1)
            sock.settimeout(1.0)
            
            self.log_signal.emit("[*] 等待连接...")
            
            while self.running:
                try:
                    client, addr = sock.accept()
                    self.log_signal.emit(f"[+] 已连接: {addr}")
                    self.handle_client(client)
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_signal.emit(f"[!] 错误: {e}")
                    break
                    
        except Exception as e:
            self.log_signal.emit(f"[!] 启动失败: {e}")
            traceback.print_exc()
    
    def handle_client(self, client):
        """处理客户端"""
        buffer = b''
        frame_count = 0
        
        try:
            client.settimeout(5.0)
            
            while self.running:
                try:
                    data = client.recv(65536)
                    if not data:
                        break
                    buffer += data
                except socket.timeout:
                    continue
                
                # 解析帧
                while len(buffer) >= 8:
                    total_size, nalu_count = struct.unpack("<LL", buffer[:8])
                    
                    if total_size > 1000000 or nalu_count > 200:
                        buffer = buffer[1:]
                        continue
                    
                    if len(buffer) < 8 + total_size:
                        break
                    
                    # 提取 H265 数据
                    h265_data = buffer[8:8+total_size]
                    buffer = buffer[8+total_size:]
                    
                    # 解析 NALU
                    nal_data = self.parse_nalu(h265_data, nalu_count)
                    if nal_data:
                        # 这里只保存数据，不解码
                        self.frame_ready.emit(nal_data, 640, 480)
                        frame_count += 1
                        
                        if frame_count % 30 == 0:
                            self.log_signal.emit(f"[*] 收到 {frame_count} 帧")
                            
        except Exception as e:
            self.log_signal.emit(f"[!] 客户端错误: {e}")
        finally:
            client.close()
            self.log_signal.emit("[*] 连接断开")
    
    def parse_nalu(self, data, count):
        """解析 NALU"""
        result = bytearray()
        offset = 0
        
        for i in range(count):
            if offset + 4 > len(data):
                break
            size = struct.unpack("<L", data[offset:offset+4])[0]
            offset += 4
            
            if offset + size > len(data):
                break
            
            result.extend(b'\x00\x00\x00\x01')
            result.extend(data[offset:offset+size])
            offset += size
        
        return bytes(result)
    
    def stop(self):
        self.running = False


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("K230 测试 - 简化版")
        self.setGeometry(100, 100, 600, 500)
        
        # 主布局
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        
        # 信息显示
        self.info = QLabel("点击'开始'启动服务器\n等待 K230 连接...")
        self.info.setAlignment(Qt.AlignCenter)
        self.info.setStyleSheet("font-size: 16px; padding: 20px;")
        layout.addWidget(self.info)
        
        # 日志
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(200)
        layout.addWidget(self.log)
        
        # 按钮
        btn_layout = QHBoxLayout()
        
        self.btn_start = QPushButton("开始")
        self.btn_start.clicked.connect(self.start)
        btn_layout.addWidget(self.btn_start)
        
        self.btn_stop = QPushButton("停止")
        self.btn_stop.clicked.connect(self.stop)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_stop)
        
        layout.addLayout(btn_layout)
        
        self.receiver = None
        
    def log_msg(self, msg):
        """添加日志"""
        self.log.append(msg)
        print(msg)
    
    def start(self):
        self.log_msg("=" * 40)
        self.log_msg("启动接收...")
        
        self.receiver = SimpleVideoReceiver("192.168.137.1", 8888)
        self.receiver.log_signal.connect(self.log_msg)
        self.receiver.frame_ready.connect(self.on_frame)
        self.receiver.start()
        
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.info.setText("服务器运行中...\n等待 K230 连接")
    
    def stop(self):
        if self.receiver:
            self.receiver.stop()
            self.receiver.wait(1000)
            self.receiver = None
        
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.info.setText("已停止")
        self.log_msg("停止接收")
    
    def on_frame(self, data, w, h):
        """收到帧"""
        self.info.setText(f"收到数据: {len(data)} bytes\n分辨率: {w}x{h}")
    
    def closeEvent(self, event):
        self.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    
    # 检查 PyAV
    try:
        import av
        print(f"[*] PyAV 版本: {av.__version__}")
    except:
        print("[!] 未安装 PyAV")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
