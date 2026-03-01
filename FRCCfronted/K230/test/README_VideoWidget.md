# K230 视频接收组件使用说明 (PyAV 版 - 修复版)

## 更新说明

此版本修复了以下问题：
- ✅ **分离解码线程** - 解码在独立线程执行，不阻塞 UI
- ✅ **优化数据缓冲** - 使用带大小限制的队列，避免内存溢出
- ✅ **修复显示卡顿** - 使用双缓冲机制，显示和解码分离

## 依赖安装

```bash
pip install PyQt5 av numpy
```

Windows 下如果 PyAV 安装失败：
```bash
conda install av ffmpeg -c conda-forge
```

## 推荐版本

| 库 | 推荐版本 |
|---|---|
| **PyQt5** | 5.15.10+ |
| **PyAV** | 11.0.0+ |
| **FFmpeg** | 5.1.x / 6.x |
| **numpy** | 1.24+ |

## 使用方法

### 1. 直接运行

```bash
python K230VideoWidget.py
```

### 2. 嵌入到其他窗口

```python
from PyQt5.QtWidgets import *
from K230VideoWidget import K230VideoWidget

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # 创建视频组件 (IP 固定为 192.168.137.1)
        self.video = K230VideoWidget(
            parent=self,
            width=640,
            height=480,
            bind_ip="192.168.137.1",  # 固定 IP
            port=8888,
            show_controls=True
        )
        
        # 添加到布局
        layout = QVBoxLayout()
        layout.addWidget(self.video)
        
        # 开始接收
        self.video.start()
```

## 工作原理

```
┌─────────────────┐
│   接收线程       │  <-- 接收 K230 发送的 H265 数据
│ (VideoReceiver) │
└────────┬────────┘
         │ 数据包
         ▼
┌─────────────────┐
│   解码线程       │  <-- PyAV 解码 H265 -> RGB 帧
│ (VideoDecoder)  │
└────────┬────────┘
         │ numpy 数组
         ▼
┌─────────────────┐
│   主线程/UI     │  <-- 显示图像
│   (Qt Widget)   │
└─────────────────┘
```

## 注意事项

1. **先启动 PC 端**，等待连接
2. **再启动 K230**，K230 会主动连接 PC
3. 如果卡住，检查防火墙设置
4. 确保 K230 和 PC 在同一网段

## 故障排除

### 程序卡住无响应
- 检查 PyAV 是否正确安装: `python -c "import av; print(av.__version__)"`
- 检查端口 8888 是否被占用
- 检查防火墙是否阻止了连接

### 有连接但无画面
- 检查 K230 是否正确发送数据
- 检查网络连接是否稳定
- 查看控制台是否有解码错误信息

### 画面卡顿
- 降低 K230 发送的分辨率或帧率
- 确保 PC 性能足够
- 关闭其他占用 CPU 的程序
