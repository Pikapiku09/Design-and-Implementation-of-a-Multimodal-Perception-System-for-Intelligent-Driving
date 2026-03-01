# -*- coding: utf-8 -*-
# @Time    : 2024/11/11 15:59
# @Author  : zlh
# @File    : main.py

import sys
from PyQt5 import QtWidgets
from UI.LoginWin import LoginWin
# from UI.mainWin import HomePage
# from UI.mainWin import myWidget

if __name__ == '__main__':

    app = QtWidgets.QApplication(sys.argv)  # Standard format
    my_widget = LoginWin()

    my_widget.show()

    sys.exit(app.exec_())  # keep program Operation


