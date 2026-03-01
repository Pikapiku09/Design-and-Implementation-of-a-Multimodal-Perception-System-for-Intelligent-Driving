# -*- coding: utf-8 -*-
# @Time    : 2024/11/13 20:53
# @Author  : zlh
# @File    : mainWin.py

import sys  # Import sys module for interaction with Python interpreter
from PyQt5.QtCore import *  # Import all contents from the QtCore module of the PyQt5 library
from PyQt5.QtWidgets import *  # Import all contents from the QtWidgets module of the PyQt5 library
from PyQt5.QtGui import *
from UI.homepage import HomePage
from UI.PhonePage import phonewin
from UI.NavigationWin import navigationwin
from UI.UserWin import userwin
from UI.musicpage import MusicPage


class myWidget(QWidget):  # Define a class named myWidget, inheriting from QWidget

    def __init__(self, w=1280, h=720):  # Class constructor for initializing objects
        super().__init__()  # Call the constructor of the parent class QWidget
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        # Main layout
        self.totalLay = QHBoxLayout()
        self.setLayout(self.totalLay)
        self.totalLay.setContentsMargins(50, 30, 50, 30)
        # Create a total QListWidget instance
        self.leftlist = QListWidget(self)

        self.totalLay.addWidget(self.leftlist)

        self.leftlist.setFixedSize(QSize(80, 320)) # w, h Set the size of the main control space
        self.leftlist.setIconSize(QSize(40, 40)) # Set icon size
        self.leftlist.setStyleSheet("background-color:transparent")  # Set background to transparent
        # Paths for main button controls
        # Left side
        self.Music = QIcon('./basic_img/images/yinle.png')
        self.navigation = QIcon('./basic_img/images/daohang.png')
        self.Phone = QIcon('./basic_img/images/dianhua.png')
        self.Home = QIcon('./basic_img/images/shouye.png')

        # Add button stack window to the left list
        self.leftlist.setSpacing(10) # Set spacing between icons
        self.left = QListWidgetItem(self.navigation, '', self.leftlist)  # Create a QListWidgetItem object for displaying the list
        self.left = QListWidgetItem(self.Phone, '', self.leftlist)  # Create a QListWidgetItem object for displaying the list
        self.left = QListWidgetItem(self.Music, '', self.leftlist)  # Create a QListWidgetItem object for displaying the list
        self.left = QListWidgetItem(self.Home, '', self.leftlist)  # Create a QListWidgetItem object for displaying the list

        # Right side
        # Create a QStackedWidget object to manage multiple sub-windows (stack)
        self.rightStack = QStackedWidget(self)
        self.totalLay.addWidget(self.rightStack)

        self.homepage = HomePage()
        self.navigationpage = navigationwin()
        self.musicpage = MusicPage()
        self.phonepage = phonewin()


        # # Add the previously created windows to the stack widget
        self.rightStack.addWidget(self.navigationpage)
        self.rightStack.addWidget(self.phonepage)
        self.rightStack.addWidget(self.musicpage)
        self.rightStack.addWidget(self.homepage)

        self.leftlist.currentRowChanged.connect(self.display_Win)


    # Define a method to display the stacked page corresponding to the current index
    def display_Win(self, index):
        # Set the current index of the stack window to the passed index
        print('Current window index:', index)
        self.rightStack.setCurrentIndex(index)

    def update_name(self, name, id):
        '''
        Get login name and pass to homepage
        :return:
        '''
        self.name = name
        self.usr_id = id
        self.homepage.update_name(name, id)



    def paintEvent(self, event):
        painter = QPainter(self)  # Drawing initialization function
        # Auto-scale image size
        self.bg_image = QPixmap('./basic_img/images/back-image.png')  # Set background
        scaled_bg = self.bg_image.scaled(self.size(),  # Image size drawing
                                         Qt.KeepAspectRatioByExpanding,  # Scaling
                                         Qt.SmoothTransformation)  # Smooth transformation
        painter.drawPixmap(0, 0, scaled_bg)  # Draw the scaled image starting from the top-left corner (0, 0)

    def closeEvent(self, event):
        '''
        Close event
        :param QCloseEvent:
        :return:
        '''
        self.setStyleSheet("color: black;")
        if QMessageBox.question(self, 'Tips', 'Are you sure you want to exit?') == QMessageBox.Yes:
            event.accept()  # Accept 'Yes' to exit the program
        else:
            event.ignore()

