# -*- coding: utf-8 -*-
# @Time    : 2024/12/4 23:58
# @Author  : zlh
# @File    : ClickLabel.py

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *

class clicklabel(QLabel):
    clicked = pyqtSignal(str)
    def __init__(self,parent=None):
        super().__init__(parent)

    def mousePressEvent(self, event):
        '''
        触发点击事件
        :param event:
        :return:
        '''
        if hasattr(self, 'path') and self.path:  # 确保self.path存在且不是空字符串,hasattr(self, 'path')检查对象是否包含一个特定的属性
            self.clicked.emit(self.path)
        else:
            # 如果没有设置路径，可以发射一个特定的信号或者不做任何操作
            pass

    def set_path(self, path):
        '''
        用来显示放展示的文件路径
        :return:
        '''
        self.path = path
