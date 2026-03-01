# -*- coding: utf-8 -*-
# @Time    : 2024/11/21 21:36
# @Author  : zlh
# @File    : carWin.py
import sys
from PyQt5 import QtGui, QtWidgets, QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QLabel, QApplication
from PyQt5.QtGui import QPixmap


class carwin(QWidget):
    def __init__(self, w=1280, h=720):
        super().__init__()
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        # 可以设置一个窗口标题方便调试
        self.setWindowTitle("Fatigue Detection - Initial View")

        self.init_control()

    def init_control(self):
        # 使用水平布局
        self.totalLayout = QHBoxLayout()
        self.setLayout(self.totalLayout)

        # 设置边距，保持原有的留白风格
        self.totalLayout.setContentsMargins(50, 30, 50, 30)

        self.Carpiture = QLabel()

        # 加载图片
        car = QPixmap('basic_img/images/motorcar.png')

        self.Carpiture.setAlignment(Qt.AlignCenter)

        # 图片自适应Label大小
        self.Carpiture.setScaledContents(True)

        self.Carpiture.setPixmap(car)

        # --- 优化点 2：将Label添加到布局时，指定在布局中居中 ---
        # alignment=Qt.AlignCenter 是关键
        self.totalLayout.addWidget(self.Carpiture, alignment=Qt.AlignCenter)


