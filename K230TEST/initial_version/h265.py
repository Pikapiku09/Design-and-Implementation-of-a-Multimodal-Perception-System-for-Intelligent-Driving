from libs.PipeLine import PipeLine, ScopedTiming
from libs.YOLO import YOLO11
import os, sys, gc
import image
import socket
import _thread
import ustruct
import struct
import uctypes  # 补充缺失的导入
import network
import time

# K230 媒体相关库
from media.sensor import Sensor
from media.media import MediaManager
from media.display import *
from media.vencoder import *
from machine import FPIOA
from machine import UART

# ==================== 全局配置 ====================
# 服务端IP和端口
SERVER_IP = "192.168.137.1"
SERVER_PORT = 8888

SSID = "ASUSBOOK"  # 想要接入热点的名称
PASSWORD = "12345678"  # 密码

# ==================== WiFi 连接函数 ====================
def sta_test():
    # 初始化STA模式（客户端模式）
    sta = network.WLAN(network.STA_IF)

    # 激活wifi模块
    if not sta.active():
        sta.active(True)
    print("wifi模块激活状态:", sta.active())

    # 查看初始连接状态
    print("初始连接状态:", sta.status())

    # 扫描当前环境中的WIFI
    wifi_list = sta.scan()
    # 打印周围WIFI信息
    for wifi in wifi_list:
        ssid = wifi.ssid
        rssi = wifi.rssi
        print(f"SSID:{ssid}, 信号强度:{rssi}dBm")

    # 尝试连接指定WIFI
    print(f"正在连接: {SSID}...")
    sta.connect(SSID, PASSWORD)

    # 等待连接结果（最多尝试5次）
    max_wait = 9
    while max_wait > 0:
        if sta.isconnected():  # 检查是否连接成功
            break
        max_wait -= 1
        time.sleep(1)  # 失败了就先休息一秒再说
        sta.connect(SSID, PASSWORD)
        print("剩余等待次数：", max_wait, "次")

    # 如果获取不到IP地址就一直在这里等待
    while sta.ifconfig()[0] == '0.0.0.0':
        print("IP错误")
        time.sleep(1)

    if sta.isconnected():
        print("\n连接成功！")
        # 重新获取并打印网络配置
        ip_info = sta.ifconfig()
        print(f"IP地址: {ip_info[0]}")
        print(f"子网掩码: {ip_info[1]}")
        print(f"网关: {ip_info[2]}")
        print(f"DNS服务器: {ip_info[3]}")
        return sta
    else:
        print("连接失败，请检查密码或信号强度")
        return None

# 先执行WiFi连接
wlan_interface = sta_test()

# ==================== 主程序类 ====================
class K230_Camera_Client:
    """K230相机客户端主类"""

    def __init__(self, server_addr=(SERVER_IP, SERVER_PORT)):
        self.resolution = (640, 480)
        self.server_addr = server_addr
        self.h265_initialized = False  # 初始化标志位

        self.sensor_init()
        self.socket_init()
        self.H265_init()

        MediaManager.init()
        self.sensor.run()

    def sensor_init(self):
        """初始化摄像头传感器"""
        self.sensor = Sensor(id=2)
        self.sensor.reset()
        self.sensor.set_hmirror(False)
        self.sensor.set_vflip(False)

        # 配置通道0：用于H265编码 (VGA分辨率, YUV格式)
        self.sensor.set_framesize(Sensor.VGA, chn=CAM_CHN_ID_0)
        self.sensor.set_pixformat(Sensor.YUV420SP, chn=CAM_CHN_ID_0)

        # 配置通道1：用于AI推理或JPEG传输 (VGA分辨率, RGB888格式)
        self.sensor.set_framesize(Sensor.VGA, chn=CAM_CHN_ID_1)
        self.sensor.set_pixformat(Sensor.RGB565, chn=CAM_CHN_ID_1)

        # 绑定通道0到编码器
        self.link = MediaManager.link(
            self.sensor.bind_info(chn=CAM_CHN_ID_0)['src'],
            (VIDEO_ENCODE_MOD_ID, VENC_DEV_ID, VENC_CHN_ID_0)
        )

    def H265_init(self):
        """初始化H265编码器"""
        self.encoder = Encoder()
        self.streamData = StreamData()
        self.encoder.SetOutBufs(chn=VENC_CHN_ID_0, buf_num=8, width=640, height=480)

        self.chnAttr = ChnAttrStr(
            self.encoder.PAYLOAD_TYPE_H265,
            self.encoder.H265_PROFILE_MAIN,
            640,
            480
        )

    def H265_Start(self):
        """启动H265编码器"""
        if not self.h265_initialized:
            self.encoder.Create(VENC_CHN_ID_0, self.chnAttr)
            self.encoder.Start(VENC_CHN_ID_0)
            self.h265_initialized = True
            print("H265编码器已启动")

    def H265_deint(self):
        """停止H265编码器"""
        if self.h265_initialized:
            self.encoder.Stop(VENC_CHN_ID_0)
            self.encoder.Destroy(VENC_CHN_ID_0)
            self.h265_initialized = False
            print("H265编码器已停止")

    def H265_send_frame(self, client):
        """发送H265编码帧到服务端"""
        # 获取编码流数据
        self.encoder.GetStream(VENC_CHN_ID_0, self.streamData)

        # 计算总大小
        total_size = sum(4 + self.streamData.data_size[i] for i in range(self.streamData.pack_cnt))
        nalu_count = self.streamData.pack_cnt

        # 打包头：总大小 + NALU数量
        header = ustruct.pack("<LL", total_size, nalu_count)
        data_buffer = bytearray()

        # 组装数据体
        for i in range(nalu_count):
            nalu_size = self.streamData.data_size[i]
            data_buffer += ustruct.pack("<L", nalu_size)  # 写入单个NALU大小

            # 注意：uctypes.bytearray_at 用于将内存地址转换为bytearray
            nalu_data = uctypes.bytearray_at(self.streamData.data[i], nalu_size)
            data_buffer.extend(nalu_data)

        # 发送头部
        client.send(header)

        # 分片发送数据体，防止缓冲区溢出
        total_sent = 0
        while total_sent < len(data_buffer):
            # 每次最多发送 65535 字节
            sent = client.send(data_buffer[total_sent:total_sent + 65535])
            if sent == 0:
                raise RuntimeError("连接中断")
            total_sent += sent

        return True

    def socket_init(self):
        """初始化Socket客户端"""
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 设置连接超时，防止一直卡住
        self.client_socket.settimeout(5.0)
        print(f"准备连接到服务端: {self.server_addr}")

    def H265_Transform(self, client):
        """H265编码传输模式"""
        self.H265_Start()  # 确保编码器已启动
        ret = self.H265_send_frame(client)
        self.encoder.ReleaseStream(VENC_CHN_ID_0, self.streamData)
        return ret

    def connect_server(self):
        """连接到服务端"""
        max_retries = 5
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 如果socket之前关闭过，需要重新创建
                self.client_socket.close()
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(5.0)

                self.client_socket.connect(self.server_addr)
                print(f"成功连接到服务端: {self.server_addr}")
                # 连接成功后设置为阻塞模式，不超时
                self.client_socket.settimeout(None)
                return True
            except Exception as e:
                retry_count += 1
                print(f"连接失败 ({retry_count}/{max_retries}): {e}")
                time.sleep(2)  # 等待2秒后重试

        print("达到最大重试次数，连接失败")
        return False

    def run(self):
        """运行客户端主循环"""
        try:
            # 连接到服务端
            if not self.connect_server():
                return

            print("开始发送H265视频流...")

            while True:
                try:
                    self.H265_Transform(self.client_socket)
                except OSError as e:
                    print(f"发送数据失败: {e}")
                    # 尝试重新连接
                    if not self.connect_server():
                        break
                except Exception as e:
                    print(f"发生未知错误: {e}")
                    break

        except KeyboardInterrupt:
            print("用户中断，程序退出")
        except Exception as e:
            print(f"程序被中断: {e}")
        finally:
            self.H265_deint()  # 确保程序退出时停止H265编码器
            self.sensor.stop()
            MediaManager.deinit()
            if hasattr(self, 'client_socket'):
                self.client_socket.close()
            print("客户端已关闭")


# ==================== 程序入口 ====================
if __name__ == "__main__":
    # 确保WiFi已连接后再启动客户端
    if wlan_interface and wlan_interface.isconnected():
        client = K230_Camera_Client()
        client.run()
    else:
        print("WiFi未连接，无法启动客户端")
