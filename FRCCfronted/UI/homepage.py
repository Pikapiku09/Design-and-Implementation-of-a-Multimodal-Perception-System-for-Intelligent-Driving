# -*- coding: utf-8 -*-
# @Time    : 2024/11/18 8:41
# @Author  : zlh
# @File    : homepage.py

from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import time
from UI.RoadTestWin import K230VideoWin
from UI.CameraWin import camerawin
from UI.UserWin import userwin
from UI.carWin import carwin
from UI.ShowPhotoWin import showphotowin
from UI.ShowVideoWin import showvideowin

from basic_tools import Weather


class HomePage(QWidget):
    def __init__(self, w=1280, h=720):
        super().__init__()
        # Initialize window conditions
        print('Homepage')
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        self.init_control()

    def init_control(self):
        # Vertical layout for overall layout
        self.totallayout = QVBoxLayout()
        self.totallayout.setContentsMargins(50, 30, 50, 30)
        self.setLayout(self.totallayout)

        # First row: Basic information display
        # User welcome
        self.wel_user = QLabel('Hi')
        self.wel_user.setAlignment(Qt.AlignCenter)

        self.totallayout.addWidget(self.wel_user)
        self.wel_user.setStyleSheet('color:white;font:40px;font-family:Arial;')
        # # Time display
        timestr = time.strftime("%Y.%m.%d.%H.%M.%S", time.localtime())  # Get system time
        # # Time update
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_time)
        self.timer.start(1000)
        self.locktime = QLabel(timestr)
        self.locktime.setAlignment(Qt.AlignCenter)
        self.totallayout.addWidget(self.locktime)
        self.locktime.setStyleSheet('color:white;font:40px;font-family:Arial;')
        # # Weather display
        tianqi = Weather.get_weather()  # Call weather function
        self.weather = QLabel(tianqi)
        self.weather.setAlignment(Qt.AlignCenter)
        print(self.weather)
        self.totallayout.addWidget(self.weather)
        self.weather.setStyleSheet('color:white;font:40px;')

        # Second row: Stacked window
        self.line2 = QHBoxLayout()

        # # # Create stacked window
        self.middleStack = QStackedWidget(self)
        self.totallayout.addWidget(self.middleStack)

        # 6 middle windows
        self.photocat = camerawin()  # Camera window
        self.K230 = K230VideoWin()
        self.win3 = QWidget()
        self.car = carwin()  # Car image
        self.videopage = showvideowin()  # Video list
        self.photopage = showphotowin()  # Photo list
        self.userpage = userwin()  # User center

        self.middleStack.addWidget(self.photocat)
        self.middleStack.addWidget(self.K230)
        self.middleStack.addWidget(self.win3)
        self.middleStack.addWidget(self.car)
        self.middleStack.addWidget(self.videopage)
        self.middleStack.addWidget(self.photopage)
        self.middleStack.addWidget(self.userpage)

        # Third row: Bottom basic controls
        self.bottomlist = QListWidget(self)
        self.bottomlist.setStyleSheet("background-color:transparent")  # Set background transparent

        self.totallayout.addWidget(self.bottomlist, alignment=Qt.AlignCenter)

        self.bottomlist.setFlow(QListView.LeftToRight)
        self.bottomlist.setFixedSize(QSize(600, 90))  # w, h Set main control space size
        self.bottomlist.setIconSize(QSize(45, 45))  # Set icon size

        self.Driving = QIcon('./basic_img/images/fatigue-driving.png')
        self.Road = QIcon('./basic_img/images/daoludingwei.png')
        self.Home2 = QIcon('./basic_img/images/shouye.png')
        self.Video = QIcon('./basic_img/images/shipin.png')
        self.Pitures = QIcon('./basic_img/images/tupian.png')
        self.User = QIcon('./basic_img/images/yonghu.png')
        self.paizhao = QIcon('./basic_img/images/paizhao.png')

        self.bottomlist.setSpacing(10)  # Set spacing between icons
        self.bottom1 = QListWidgetItem(self.Driving, '',
                                       self.bottomlist)  # Create a QListWidgetItem object for displaying the list
        self.bottom2 = QListWidgetItem(self.Road, '',
                                       self.bottomlist)  # Create a QListWidgetItem object for displaying the list
        self.bottom3 = QListWidgetItem(self.paizhao, '',
                                       self.bottomlist)  # Create a QListWidgetItem object for displaying the list
        self.bottom4 = QListWidgetItem(self.Home2, '',
                                       self.bottomlist)  # Create a QListWidgetItem object for displaying the list
        self.bottom5 = QListWidgetItem(self.Video, '',
                                       self.bottomlist)  # Create a QListWidgetItem object for displaying the list
        self.bottom6 = QListWidgetItem(self.Pitures, '',
                                       self.bottomlist)  # Create a QListWidgetItem object for displaying the list
        self.bottom7 = QListWidgetItem(self.User, '',
                                       self.bottomlist)  # Create a QListWidgetItem object for displaying the list

        self.bottomlist.currentRowChanged.connect(self.display_Win)

    def update_time(self):
        # Update the time display of QLabel
        current_time = time.strftime("%Y.%m.%d.%H.%M")
        self.locktime.setText(current_time)

    # Define a method to display the stacked page corresponding to the current index
    def display_Win(self, index):
        # Set the current index of the stacked window to the passed index
        if index == 0:
            print('Open Camera')
        elif index == 1:
            print('Road Detection')
        elif index == 2:
            self.photocat.save_frame()
            print('Screenshot')
            return
        elif index == 3:
            print('Car Owner Interface') # Unable to display image for now
        elif index == 4:
            self.videopage.init_id(self.user_id)
            self.videopage.init_control()
            print('Video Saved List')
            self.middleStack.setCurrentIndex(index)  # Update window! Must update to show latest content
        elif index == 5:
            self.photopage.get_id(self.user_id)
            self.photopage.init_control()
            print('Photo Saved List')
            self.middleStack.setCurrentIndex(index) # Update window! Must update to show latest content
        elif index == 6:
            print('User Center')


        print('Current window index:', index)
        self.middleStack.setCurrentIndex(index)

    def update_name(self, name, id):
        '''
        Get login name and pass to homepage
        :return:
        '''
        self.user_name = name
        self.user_id = id
        self.wel_user.setText('Hi~{}'.format(name))
        self.photocat.update_id(id)
        self.userpage.update_name(name, id)
        self.userpage.up_avtar(id)
        self.photopage.get_id(id)
        self.videopage.init_id(id)
