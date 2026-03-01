# -*- coding: utf-8 -*-
"""
PyAV 测试脚本 - 验证解码器是否正常工作
"""

import sys
import numpy as np

print("=" * 50)
print("PyAV 测试")
print("=" * 50)

# 1. 检查 PyAV 版本
import av
print(f"\n[1] PyAV 版本: {av.__version__}")

# 2. 检查 FFmpeg 库版本
print("\n[2] FFmpeg 库版本:")
try:
    print(f"    libavcodec: {av.library_versions.get('libavcodec', 'unknown')}")
    print(f"    libavformat: {av.library_versions.get('libavformat', 'unknown')}")
    print(f"    libavutil: {av.library_versions.get('libavutil', 'unknown')}")
    print(f"    libswscale: {av.library_versions.get('libswscale', 'unknown')}")
except Exception as e:
    print(f"    错误: {e}")

# 3. 检查 H265/HEVC 解码器
print("\n[3] 检查 H265/HEVC 解码器:")
try:
    # 尝试查找解码器
    try:
        codec = av.Codec('hevc', 'r')
        print(f"    ✓ hevc 解码器可用")
        print(f"      名称: {codec.name}")
        print(f"      长名称: {codec.long_name}")
    except Exception as e:
        print(f"    ✗ hevc 解码器不可用: {e}")
    
    try:
        codec = av.Codec('h265', 'r')
        print(f"    ✓ h265 解码器可用")
    except:
        print(f"    ✗ h265 解码器不可用")
        
except Exception as e:
    print(f"    错误: {e}")

# 4. 尝试创建解码器
print("\n[4] 创建解码器上下文:")
try:
    # 方式 1
    try:
        ctx = av.CodecContext.create('hevc', 'r')
        print("    ✓ 方式1成功: av.CodecContext.create('hevc', 'r')")
        ctx.close()
    except Exception as e1:
        print(f"    ✗ 方式1失败: {e1}")
        
        # 方式 2
        try:
            codec = av.Codec('hevc', 'r')
            ctx = av.CodecContext.create(codec)
            print("    ✓ 方式2成功: av.CodecContext.create(codec)")
            ctx.close()
        except Exception as e2:
            print(f"    ✗ 方式2失败: {e2}")
            
except Exception as e:
    print(f"    错误: {e}")

# 5. 测试解码功能
print("\n[5] 测试解码功能:")
try:
    # 创建一个最小的 H265 帧 (I 帧头)
    # H265 NALU 起始码 + VPS + SPS + PPS + IDR
    
    # 这只是一个测试用的假数据，真正的解码需要有效的 H265 流
    test_data = b'\x00\x00\x00\x01\x40\x01'  # VPS 起始
    test_data += b'\x00\x00\x00\x01\x42\x01'  # SPS 起始
    test_data += b'\x00\x00\x00\x01\x44\x01'  # PPS 起始
    
    ctx = av.CodecContext.create('hevc', 'r')
    packet = av.Packet(test_data)
    
    try:
        frames = ctx.decode(packet)
        print(f"    ✓ 解码成功 (返回 {len(frames)} 帧)")
    except av.AVError as e:
        print(f"    ! 解码返回错误 (预期，因为数据无效): {e}")
    except Exception as e:
        print(f"    ✗ 解码异常: {e}")
    
    ctx.close()
    
except Exception as e:
    print(f"    ✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 6. 检查多线程支持
print("\n[6] 检查多线程支持:")
try:
    ctx = av.CodecContext.create('hevc', 'r')
    
    # 尝试设置线程
    try:
        ctx.thread_type = 'FRAME'
        ctx.thread_count = 2
        print("    ✓ 支持 FRAME 级多线程")
    except Exception as e:
        print(f"    ! 不支持 FRAME 级多线程: {e}")
    
    ctx.close()
except Exception as e:
    print(f"    错误: {e}")

print("\n" + "=" * 50)
print("测试完成")
print("=" * 50)

# 7. 网络测试
print("\n[7] 网络绑定测试:")
import socket

try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    test_ip = "192.168.137.1"
    test_port = 8888
    
    try:
        sock.bind((test_ip, test_port))
        print(f"    ✓ 成功绑定到 {test_ip}:{test_port}")
        sock.close()
    except Exception as e:
        print(f"    ✗ 绑定失败: {e}")
        print(f"      请检查:")
        print(f"      1. IP 地址 {test_ip} 是否属于本机")
        print(f"      2. 端口 {test_port} 是否被占用")
        print(f"      3. 是否有防火墙阻止")
        
        # 尝试绑定到所有接口
        try:
            sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock2.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock2.bind(("0.0.0.0", test_port))
            print(f"    ✓ 可以绑定到 0.0.0.0:{test_port}")
            sock2.close()
        except Exception as e2:
            print(f"    ✗ 绑定到 0.0.0.0 也失败: {e2}")
        
except Exception as e:
    print(f"    错误: {e}")

print("\n" + "=" * 50)
print("如果以上测试都通过，但视频仍然无法显示，")
print("请运行 K230VideoWidget_Debug.py 查看详细日志")
print("=" * 50)

input("\n按回车键退出...")
