# -*- coding: utf-8 -*-
# @Time    : 2024/11/25 20:11
# @Author  : zlh
# @File    : PhonePage.py
from PyQt5 import QtGui,QtWidgets, QtCore
from PyQt5.QtCore import *  # 从PyQt5库中导入QtCore模块的所有内容
from PyQt5.QtWidgets import *  # 从PyQt5库中导入QtWidgets模块的所有内容
from PyQt5.QtGui import *

class phonewin(QWidget):  # 定义一个名为myWidget的类，继承自QWidget

    def __init__(self, w=1280, h=720):  # 类的构造函数，用于初始化对象
        super().__init__()  # 调用父类QWidget的构造函数
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        self.init_control()


    def init_control(self):
        # 总布局

        self.totalLayout = QHBoxLayout()
        self.setLayout(self.totalLayout)
        self.totalLayout.setContentsMargins(50, 30, 50, 30)
        self.Phonepicture = QLabel()
        car = QPixmap('basic_img/images/bohao.png')
        self.Phonepicture.setPixmap(car)
        self.totalLayout.addWidget(self.Phonepicture)

