# -*- coding: utf-8 -*-
# @Time    : 2024/11/25 20:25
# @Author  : zlh
# @File    : NavigationWin.py
import requests
from PIL import Image
from io import BytesIO
from PyQt5 import QtGui,QtWidgets, QtCore
from PyQt5.QtCore import *  # Import all contents from the QtCore module of the PyQt5 library
from PyQt5.QtWidgets import *  # Import all contents from the QtWidgets module of the PyQt5 library
from PyQt5.QtGui import *
from basic_tools import Navigation
from PIL.ImageQt import ImageQt



class navigationwin(QWidget):  # Define a class named myWidget, inheriting from QWidget

    def __init__(self, w=1280, h=720):  # Class constructor for initializing objects
        super().__init__()  # Call the constructor of the parent class QWidget
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        self.init_control()


    def init_control(self):
        # Overall layout

        self.totalLayout = QVBoxLayout()
        self.setLayout(self.totalLayout)
        self.totalLayout.setContentsMargins(50, 30, 50, 30)
        self.piture = QLabel('', self)
        self.locationedit = QLineEdit()
        self.locationedit.setPlaceholderText('Please enter the place you want to go.')
        self.search = QPushButton('Search for nearby areas')

        self.totalLayout.addWidget(self.piture)
        self.totalLayout.addWidget(self.locationedit)
        self.totalLayout.addWidget(self.search)

        self.search.clicked.connect(self.navigation)

        print('nv1:', self.locationedit)


    def navigation(self):
        '''
        Navigation information transmission display
        :return:
        '''
        self.location = self.locationedit.text()
        self.zuobiao = self.gaode(self.location)
        self.navigation_gaode(self.zuobiao)



    def navigation_gaode(self, m):
        url = 'https://restapi.amap.com/v3/staticmap?params'

        params = {
            'location': m,  # Current location coordinates (longitude and latitude)
            'zoom': '14',  # Zoom level
            'size': '720*640',  # Map size, maximum value is 1024*1024
            'markers': 'mid,,A:{}'.format(m),  # Markers, size and location
            'key': 'd6201ee52bf315fc4d6fd80f1d9269c7'
        }

        r = requests.get(url, params=params)

        # Convert bytes result to byte stream
        bytes_stream = BytesIO(r.content)
        # Read the image
        roiimg = Image.open(bytes_stream)
        roiimg.show()
        # Convert PIL image to QImage
        # qimage = self.pil_to_qimage(roiimg)
        #
        # # Convert QImage to QPixmap and set to QLabel
        # pixmap = QPixmap.fromImage(qimage)


    def gaode(self, addr):
        para = {
            'key': 'd6201ee52bf315fc4d6fd80f1d9269c7',  # Key applied from Amap (AutoNavi) open platform
            'address': addr  # Input address parameter
        }
        url = 'https://restapi.amap.com/v3/geocode/geo?'  # Amap API interface
        req = requests.get(url, para)
        req = req.json()
        print('-' * 30)
        m = req['geocodes'][0]['location']
        print(m)

        return m
