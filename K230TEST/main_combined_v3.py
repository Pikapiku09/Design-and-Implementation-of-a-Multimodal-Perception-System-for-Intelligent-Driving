"""
K230 综合控制程序 - H265视频图传 + PID舵机转向控制
CANMV平台使用，集成WiFi、视频编码、车道检测和舵机控制功能
"""

# ==================== 导入部分 ====================
from libs.PipeLine import PipeLine, ScopedTiming
from libs.YOLO import YOLO11
import os, sys, gc
import image
import socket
import _thread
import ustruct
import struct
import uctypes
import network
import time

# K230 媒体相关库
from media.sensor import Sensor
from media.media import MediaManager
from media.display import *
from media.vencoder import *
from machine import FPIOA, Pin, PWM, UART

# ==================== 全局配置 ====================
# 服务端IP和端口 (H265视频传输)
SERVER_IP = "192.168.137.1"
SERVER_PORT = 8888

# WiFi配置
SSID = "ASUSBOOK"  # 想要接入热点的名称
PASSWORD = "12345678"  # 密码

# 显示模式配置 (用于车道检测显示)
DISPLAY_MODE = "LCD"  # 可选: "VIRT", "LCD", "HDMI"

# 图像分辨率配置
# 通道0: H265编码用 (YUV420SP)
H265_WIDTH = 320
H265_HEIGHT = 240

# 通道1: 车道检测用 (GRAYSCALE)
LANE_WIDTH = 544
LANE_HEIGHT = 288

# 显示分辨率
if DISPLAY_MODE == "VIRT":
    DISPLAY_WIDTH = ALIGN_UP(1920, 16)
    DISPLAY_HEIGHT = 1080
elif DISPLAY_MODE == "LCD":
    DISPLAY_WIDTH = 800
    DISPLAY_HEIGHT = 480
elif DISPLAY_MODE == "HDMI":
    DISPLAY_WIDTH = 1920
    DISPLAY_HEIGHT = 1080
else:
    raise ValueError("Unknown DISPLAY_MODE")

# 舵机控制配置
SERVO_PIN = 47
PWM_ID = 3
MAX_LEFT_ANGLE = -45
MAX_RIGHT_ANGLE = 45
CENTER_ANGLE = 0
STEP_DELAY = 0.02
ANGLE_STEP = 2

# PID控制参数
Kp = 0.55  # 比例增益
Kd = 0.3  # 微分增益
Ki = 0.001  # 积分增益

# ==================== WiFi 连接函数 ====================
def sta_test():
    """初始化STA模式并连接WiFi"""
    sta = network.WLAN(network.STA_IF)

    # 激活wifi模块
    if not sta.active():
        sta.active(True)
    print("wifi模块激活状态:", sta.active())

    # 查看初始连接状态
    print("初始连接状态:", sta.status())

    # 扫描当前环境中的WIFI
    wifi_list = sta.scan()
    for wifi in wifi_list:
        ssid = wifi.ssid
        rssi = wifi.rssi
        print(f"SSID:{ssid}, 信号强度:{rssi}dBm")

    # 尝试连接指定WIFI
    print(f"正在连接: {SSID}...")
    sta.connect(SSID, PASSWORD)

    # 等待连接结果（最多尝试9次）
    max_wait = 9
    while max_wait > 0:
        if sta.isconnected():
            break
        max_wait -= 1
        time.sleep(1)
        sta.connect(SSID, PASSWORD)
        print("剩余等待次数：", max_wait, "次")

    # 如果获取不到IP地址就一直等待
    while sta.ifconfig()[0] == '0.0.0.0':
        print("IP错误")
        time.sleep(1)

    if sta.isconnected():
        print("\n连接成功！")
        ip_info = sta.ifconfig()
        print(f"IP地址: {ip_info[0]}")
        print(f"子网掩码: {ip_info[1]}")
        print(f"网关: {ip_info[2]}")
        print(f"DNS服务器: {ip_info[3]}")
        return sta
    else:
        print("连接失败，请检查密码或信号强度")
        return None


# ==================== 舵机控制类 ====================
class SteeringControl:
    """舵机转向控制类"""

    def __init__(self, servo_pwm):
        self.servo = servo_pwm
        self.current_angle = CENTER_ANGLE
        self.move_to(CENTER_ANGLE)

    def _clamp(self, angle, min_val, max_val):
        return max(min_val, min(angle, max_val))

    def _set_pwm(self, angle):
        """将角度转换为PWM占空比"""
        duty = (angle + 90) / 180 * 10 + 2.5
        self.servo.duty(duty)

    def move_to(self, target_angle):
        """平滑移动到目标角度"""
        target_angle = self._clamp(target_angle, MAX_LEFT_ANGLE, MAX_RIGHT_ANGLE)

        while abs(self.current_angle - target_angle) > 0.1:
            if self.current_angle < target_angle:
                self.current_angle += ANGLE_STEP
                if self.current_angle > target_angle:
                    self.current_angle = target_angle
            else:
                self.current_angle -= ANGLE_STEP
                if self.current_angle < target_angle:
                    self.current_angle = target_angle

            self._set_pwm(self.current_angle)
            time.sleep(STEP_DELAY)

    def set_angle(self, angle):
        """直接设置角度（用于快速PID控制）"""
        angle = self._clamp(angle, MAX_LEFT_ANGLE, MAX_RIGHT_ANGLE)
        self.current_angle = angle
        self._set_pwm(angle)

    def stop(self):
        """回中并停止"""
        self.move_to(CENTER_ANGLE)

    def deinit(self):
        """释放资源"""
        self.servo.deinit()


# ==================== 车道检测与PID控制 ====================
class LaneTracker:
    """车道检测与PID控制类"""

    def __init__(self, img_width):
        self.img_width = img_width
        self.last_error = 0
        self.integral = 0
        self.image_center = img_width // 2

    def calculate_steering_angle(self, lines):
        """基于检测到的车道线计算转向角度"""
        if not lines:
            return 0

        left_lines = []
        right_lines = []

        # 根据位置分类左右车道线
        for line in lines:
            line_center_x = (line.x1() + line.x2()) // 2
            if line_center_x < self.image_center:
                left_lines.append(line)
            else:
                right_lines.append(line)

        left_center = None
        right_center = None

        # 计算左侧车道线平均位置
        if left_lines:
            left_centers = [(line.x1() + line.x2()) // 2 for line in left_lines]
            left_center = sum(left_centers) / len(left_centers)

        # 计算右侧车道线平均位置
        if right_lines:
            right_centers = [(line.x1() + line.x2()) // 2 for line in right_lines]
            right_center = sum(right_centers) / len(right_centers)

        # 计算目标中心位置
        if left_center is not None and right_center is not None:
            # 检测到两条车道线，瞄准中间
            target_center = (left_center + right_center) / 2
        elif left_center is not None:
            # 仅检测到左车道线，向右偏移
            target_center = left_center + 100
        elif right_center is not None:
            # 仅检测到右车道线，向左偏移
            target_center = right_center - 100
        else:
            return 0

        # 计算误差
        error = self.image_center - target_center

        # PID控制计算
        self.integral += error
        derivative = error - self.last_error
        steering_correction = Kp * error + Ki * self.integral + Kd * derivative
        self.last_error = error

        # 将像素误差转换为转向角度
        max_pixel_error = self.img_width // 2
        steering_angle = (steering_correction / max_pixel_error) * MAX_RIGHT_ANGLE

        # 限制转向角度范围
        steering_angle = max(min(steering_angle, MAX_RIGHT_ANGLE), MAX_LEFT_ANGLE)

        return steering_angle

    def detect_lanes(self, gray_img, roi):
        """执行车道线检测"""
        # Canny边缘检测
        canny_img = gray_img.find_edges(image.EDGE_CANNY,
                                        threshold=(150, 200),
                                        roi=roi)

        # Hough变换检测直线
        lines = canny_img.find_line_segments(roi=roi,
                                              merge_distance=20,
                                              max_theta_diff=10)

        # 过滤近水平线
        filtered_lines = []
        for line in lines:
            if abs(line.theta()) > 20 and abs(line.theta()) < 160:
                filtered_lines.append(line)
                canny_img.draw_line(line.line(), color=(255, 0, 0), thickness=2)

        return filtered_lines, canny_img


# ==================== 主程序类 ====================
class K230_Vehicle_Control:
    """K230车辆综合控制类 - 视频图传 + 舵机控制"""

    def __init__(self, server_addr=(SERVER_IP, SERVER_PORT)):
        self.server_addr = server_addr
        self.h265_initialized = False
        self.connected = False

        # PID相关变量
        self.last_error = 0
        self.integral = 0
        self.frame_count = 0
        self.update_interval = 2  # 每N帧更新一次舵机

        # ROI区域配置 (用于车道检测)
        self.roi = (100, LANE_HEIGHT // 2, LANE_WIDTH - 150, LANE_HEIGHT // 2)

        # 初始化各个模块
        self.init_servo()
        self.sensor_init()
        self.socket_init()
        self.H265_init()
        self.init_display()

        # 初始化媒体管理器
        MediaManager.init()
        self.sensor.run()

        print("系统初始化完成")

    def init_servo(self):
        """初始化舵机"""
        fpioa = FPIOA()
        fpioa.set_function(SERVO_PIN, FPIOA.PWM3)
        self.servo_pwm = PWM(PWM_ID, 50, duty=0, enable=True)
        self.steering = SteeringControl(self.servo_pwm)
        self.lane_tracker = LaneTracker(LANE_WIDTH)
        print("舵机初始化完成")

    def sensor_init(self):
        """初始化摄像头传感器 - 配置多通道"""
        self.sensor = Sensor(id=2)
        self.sensor.reset()
        self.sensor.set_hmirror(False)
        self.sensor.set_vflip(False)

        # 通道0: H265编码用 (VGA分辨率, YUV420SP格式)
        self.sensor.set_framesize(Sensor.VGA, chn=CAM_CHN_ID_0)
        self.sensor.set_pixformat(Sensor.YUV420SP, chn=CAM_CHN_ID_0)

        # 通道1: 车道检测用 (544x288, 灰度图)
        self.sensor.set_framesize(width=LANE_WIDTH, height=LANE_HEIGHT, chn=CAM_CHN_ID_1)
        self.sensor.set_pixformat(Sensor.GRAYSCALE, chn=CAM_CHN_ID_1)

        # 通道2: AI推理/显示用 (VGA分辨率, RGB565格式)
        self.sensor.set_framesize(Sensor.VGA, chn=CAM_CHN_ID_2)
        self.sensor.set_pixformat(Sensor.RGB565, chn=CAM_CHN_ID_2)

        # 绑定通道0到编码器
        self.link = MediaManager.link(
            self.sensor.bind_info(chn=CAM_CHN_ID_0)['src'],
            (VIDEO_ENCODE_MOD_ID, VENC_DEV_ID, VENC_CHN_ID_0)
        )
        print("摄像头传感器初始化完成")

    def init_display(self):
        """初始化显示"""
        try:
            if DISPLAY_MODE == "VIRT":
                Display.init(Display.VIRT, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, fps=60)
            elif DISPLAY_MODE == "LCD":
                Display.init(Display.ST7701, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=True)
            elif DISPLAY_MODE == "HDMI":
                Display.init(Display.LT9611, width=DISPLAY_WIDTH, height=DISPLAY_HEIGHT, to_ide=True)
            print("显示初始化完成")
        except Exception as e:
            print(f"显示初始化失败: {e}")

    def H265_init(self):
        """初始化H265编码器"""
        self.encoder = Encoder()
        self.streamData = StreamData()
        self.encoder.SetOutBufs(chn=VENC_CHN_ID_0, buf_num=1, width=H265_WIDTH, height=H265_HEIGHT)

        self.chnAttr = ChnAttrStr(
            self.encoder.PAYLOAD_TYPE_H265,
            self.encoder.H265_PROFILE_MAIN,
            H265_WIDTH,
            H265_HEIGHT
        )
        print("H265编码器初始化完成")

    def H265_Start(self):
        """启动H265编码器"""
        if not self.h265_initialized:
            try:
                # 确保之前的资源已释放
                gc.collect()
                time.sleep(0.05)

                self.encoder.Create(VENC_CHN_ID_0, self.chnAttr)
                time.sleep(0.05)
                self.encoder.Start(VENC_CHN_ID_0)
                self.h265_initialized = True
                print("H265编码器已启动")
            except Exception as e:
                print(f"启动编码器错误: {e}")
                # 如果启动失败，尝试清理
                try:
                    self.encoder.Destroy(VENC_CHN_ID_0)
                except:
                    pass
                raise

    def H265_deint(self):
        """停止H265编码器"""
        if self.h265_initialized:
            try:
                self.encoder.Stop(VENC_CHN_ID_0)
                time.sleep(0.1)  # 给编码器时间停止
            except Exception as e:
                print(f"停止编码器警告: {e}")

            try:
                self.encoder.Destroy(VENC_CHN_ID_0)
                time.sleep(0.1)  # 给编码器时间销毁
            except Exception as e:
                print(f"销毁编码器警告: {e}")

            self.h265_initialized = False
            gc.collect()  # 强制垃圾回收
            print("H265编码器已停止")

    def H265_send_frame(self):
        """发送H265编码帧到服务端"""
        # 获取编码流数据
        self.encoder.GetStream(VENC_CHN_ID_0, self.streamData)

        # 计算总大小
        total_size = sum(4 + self.streamData.data_size[i] for i in range(self.streamData.pack_cnt))
        nalu_count = self.streamData.pack_cnt

        # 打包头部信息
        header = ustruct.pack("<LL", total_size, nalu_count)
        data_buffer = bytearray()

        # 组装数据
        for i in range(nalu_count):
            nalu_size = self.streamData.data_size[i]
            data_buffer += ustruct.pack("<L", nalu_size)
            nalu_data = uctypes.bytearray_at(self.streamData.data[i], nalu_size)
            data_buffer.extend(nalu_data)

        # 发送数据
        if self.connected and self.client_socket:
            try:
                self.client_socket.send(header)
                total_sent = 0
                while total_sent < len(data_buffer):
                    sent = self.client_socket.send(data_buffer[total_sent:total_sent + 65535])
                    if sent == 0:
                        raise RuntimeError("连接中断")
                    total_sent += sent
                return True
            except Exception as e:
                print(f"发送数据失败: {e}")
                self.connected = False
                return False

        self.encoder.ReleaseStream(VENC_CHN_ID_0, self.streamData)
        return True

    def socket_init(self):
        """初始化Socket客户端"""
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_socket.settimeout(5.0)
        print(f"准备连接到服务端: {self.server_addr}")

    def connect_server(self):
        """连接到服务端 - 无限重试直到成功"""
        retry_count = 0

        while True:
            try:
                # 如果socket之前关闭过，重新创建
                if hasattr(self, 'client_socket'):
                    try:
                        self.client_socket.close()
                    except:
                        pass
                self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.settimeout(5.0)

                self.client_socket.connect(self.server_addr)
                print(f"成功连接到服务端: {self.server_addr}")
                self.client_socket.settimeout(None)
                self.connected = True
                return True
            except Exception as e:
                retry_count += 1
                if retry_count % 5 == 1:  # 每5次打印一次日志，避免刷屏
                    print(f"连接失败，正在重试... ({e})")
                time.sleep(1)  # 缩短重试间隔，更快响应

    def process_lane_detection(self, gray_img):
        """处理车道检测和舵机控制"""
        # 执行车道线检测
        filtered_lines, canny_img = self.lane_tracker.detect_lanes(gray_img, self.roi)

        # 定期更新舵机角度
        if self.frame_count % self.update_interval == 0:
            steering_angle = self.lane_tracker.calculate_steering_angle(filtered_lines)
            self.steering.set_angle(steering_angle)
            print(f"Steering Angle: {steering_angle:.1f}°")

            # 防止frame_count溢出
            if self.frame_count > 1000:
                self.frame_count = 0

        return canny_img

    def run(self):
        """运行主循环 - 同时处理视频传输和舵机控制，支持后台永久重连"""
        try:
            print("开始主循环 - 视频传输 + 舵机控制")
            print("等待服务器连接...")
            fps = time.clock()

            # 连接重试计数器
            connect_retry_counter = 0
            encoder_started = False

            while True:
                fps.tick()
                os.exitpoint()
                self.frame_count += 1

                # ========== 1. H265视频传输 ==========
                if self.connected:
                    # 确保编码器已启动
                    if not encoder_started:
                        try:
                            self.H265_Start()
                            encoder_started = True
                            print("H265编码器已启动")
                        except Exception as e:
                            print(f"启动编码器失败: {e}")
                            self.connected = False
                            continue

                    try:
                        self.encoder.GetStream(VENC_CHN_ID_0, self.streamData)

                        # 计算总大小
                        total_size = sum(4 + self.streamData.data_size[i] for i in range(self.streamData.pack_cnt))
                        nalu_count = self.streamData.pack_cnt

                        # 打包并发送
                        header = ustruct.pack("<LL", total_size, nalu_count)
                        data_buffer = bytearray()

                        for i in range(nalu_count):
                            nalu_size = self.streamData.data_size[i]
                            data_buffer += ustruct.pack("<L", nalu_size)
                            nalu_data = uctypes.bytearray_at(self.streamData.data[i], nalu_size)
                            data_buffer.extend(nalu_data)

                        self.client_socket.send(header)
                        total_sent = 0
                        while total_sent < len(data_buffer):
                            sent = self.client_socket.send(data_buffer[total_sent:total_sent + 65535])
                            if sent == 0:
                                raise RuntimeError("连接中断")
                            total_sent += sent

                        self.encoder.ReleaseStream(VENC_CHN_ID_0, self.streamData)

                    except Exception as e:
                        print(f"视频传输错误: {e}")
                        self.connected = False
                        encoder_started = False
                        # 停止编码器释放资源
                        try:
                            self.H265_deint()
                            print("编码器已停止，资源已释放")
                        except Exception as deinit_e:
                            print(f"停止编码器时出错: {deinit_e}")
                        print("连接断开，将在后台尝试重连...")

                else:
                    # 未连接时，确保编码器停止
                    if encoder_started:
                        try:
                            self.H265_deint()
                            encoder_started = False
                            print("编码器已停止")
                        except:
                            pass

                    # 定期尝试连接
                    connect_retry_counter += 1
                    if connect_retry_counter >= 30:  # 每30帧尝试一次连接（约1秒）
                        connect_retry_counter = 0
                        try:
                            # 尝试快速连接（不重试，避免阻塞）
                            if hasattr(self, 'client_socket'):
                                try:
                                    self.client_socket.close()
                                except:
                                    pass
                            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            self.client_socket.settimeout(0.5)  # 短超时，不阻塞
                            self.client_socket.connect(self.server_addr)
                            self.client_socket.settimeout(None)
                            self.connected = True
                            print(f"成功连接到服务端: {self.server_addr}")
                        except:
                            # 连接失败，继续运行其他功能
                            pass

                # ========== 2. 车道检测与舵机控制 ==========
                # 从通道1获取灰度图像用于车道检测
                gray_img = self.sensor.snapshot(chn=CAM_CHN_ID_1)

                # 处理车道检测
                canny_img = self.process_lane_detection(gray_img)

                # 显示图像 (可选)
                try:
                    Display.show_image(gray_img, layer=Display.LAYER_OSD1)
                except:
                    pass

                # 打印FPS
                if self.frame_count % 30 == 0:
                    print(f"FPS: {fps.fps():.1f}")

        except KeyboardInterrupt:
            print("用户中断，程序退出")
        except Exception as e:
            print(f"发生错误: {e}")
        finally:
            self.cleanup()

    def cleanup(self):
        """清理资源"""
        print("正在清理资源...")

        # 停止H265编码
        self.H265_deint()

        # 停止传感器
        self.sensor.stop()

        # 回中舵机
        self.steering.stop()
        time.sleep(1)

        # 释放舵机
        self.steering.deinit()

        # 释放显示
        try:
            Display.deinit()
        except:
            pass

        # 释放媒体管理器
        MediaManager.deinit()

        # 关闭socket
        if hasattr(self, 'client_socket'):
            self.client_socket.close()

        print("资源清理完成")


# ==================== 程序入口 ====================
if __name__ == "__main__":
    # 连接WiFi
    print("正在连接WiFi...")
    wlan_interface = sta_test()

    if wlan_interface and wlan_interface.isconnected():
        print("WiFi已连接，启动车辆控制系统")
        # 创建并运行控制系统
        controller = K230_Vehicle_Control()
        controller.run()
    else:
        print("WiFi未连接，是否继续启动? (y/n)")
        # 即使没有WiFi也可以选择启动（仅舵机控制）
        try:
            controller = K230_Vehicle_Control()
            controller.run()
        except Exception as e:
            print(f"启动失败: {e}")
