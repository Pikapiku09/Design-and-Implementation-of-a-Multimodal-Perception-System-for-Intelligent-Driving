# -*- coding: utf-8 -*-
# @Time    : 2024/11/22 15:17
# @Author  : zlh
# @File    : ShowVideoWin.py
import os
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from basic_tools import db
from basic_tools import ClickLabel
import cv2

class showvideowin(QWidget):  # Define a class named myWidget, inheriting from QWidget
    def __init__(self, w=1280, h=720):
        super().__init__()
        # Initialize window conditions
        self.w = w
        self.h = h
        self.resize(self.w, self.h)
        self.pagenow = 1
        self.pagecount = 2

        # Video playback timer
        self.Time1 = QTimer()# Video playback timer
        self.Time1.timeout.connect(self.play_video)
        # self.Time2 = QTimer()# Video pause
        # self.Time2.timeout.connect()

        # Set default placeholder image
        self.placeholder = QPixmap('basic_img/holderplace.png').scaled(300, 300, Qt.KeepAspectRatio,
                                                                       Qt.SmoothTransformation)

        # Create video display window
        self.videoWidget = QVideoWidget()
        self.videoWidget.resize(1280, 720)
        self.videoWidget.setWindowTitle('video play')
        self.imgLab = QLabel('', self.videoWidget)# Control attached to window
        self.imgLab.setGeometry(320,75,640,480)

        self.box = QComboBox(self.videoWidget)
        self.box.setGeometry(520, 0, 200, 50)
        self.box.addItem('1.0x')
        self.box.addItem('0.5x')
        self.box.addItem('1.5x')
        self.box.addItem('2.0x')

        # Connect activated signal to slot function
        self.box.activated[int].connect(self.video_speed)

        # Initialize video display preview
        CLICK = ClickLabel.clicklabel
        self.videos = [CLICK(self), CLICK(self)]

        # Create basic layout
        self.totalLayout = QVBoxLayout()
        self.totalLayout.setContentsMargins(50, 30, 50, 30)
        self.setLayout(self.totalLayout)

        # Create previous page button and set style
        self.lastpageBtn = QPushButton('next page', self)
        self.lastpageBtn.setStyleSheet('color:black;font:30px')
        # Create next page button and set style
        self.nextpageBtn = QPushButton('last page', self)
        self.nextpageBtn.setStyleSheet('color:black;font:30px')
        # Create play button and set style
        self.startBtn = QPushButton('play', self.videoWidget)
        self.startBtn.setStyleSheet('color:black;font:30px')
        self.startBtn.setGeometry(270, 0, 200, 50)
        # Create pause button and set style
        self.stopBtn = QPushButton('stop', self.videoWidget)
        self.stopBtn.setStyleSheet('color:black;font:30px')
        self.stopBtn.setGeometry(20, 0, 200, 50)
        # Create Delete button and set style to delete video
        self.delBtn = QPushButton('Delete', self.videoWidget)
        self.delBtn.setStyleSheet('color:red;font:30px')
        self.delBtn.setGeometry(740, 0, 200, 50)

        # Connect button signals to corresponding slot functions
        self.lastpageBtn.clicked.connect(self.last_page)
        self.nextpageBtn.clicked.connect(self.next_page)
        self.stopBtn.clicked.connect(self.stop_video) # Video pause
        self.startBtn.clicked.connect(self.start_vid) # Video playback
        self.delBtn.clicked.connect(self.delete_video)# Video delete

        # Add pages to layout
        self.totalLayout.addWidget(self.lastpageBtn)
        self.totalLayout.addWidget(self.nextpageBtn)


    def init_control(self):
        '''
        Initialize video list content
        :return:
        '''
        self.pages = db.db_search_pages_video(self.id)
        rs = db.db_VideoInterface(self.id, self.pagenow, self.pagecount) # Read video address from database
        if not self.pages[0]:
            # print('len(rs)',len(rs[0]))
            for video in self.videos:
                for j in range(2):
                    self.videos[j].setPixmap(
                        QPixmap(self.placeholder).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    print('The placeholder image was set successfully')
                self.totalLayout.addWidget(video)  # Display the read video
        else:
            print('video')
            for video in self.videos:
                for i in range(len(rs)):
                    if i < len(rs):
                        # Traverse and load video data to the interface
                        self.videos[i].setPixmap(QPixmap(rs[i][4]).scaled(300,300,Qt.KeepAspectRatio, Qt.SmoothTransformation))# Set rs[i][4] video preview image (path) to fill in the interface
                        self.videos[i].set_path(rs[i][3]) # Load video path into click event
                        self.videos[i].clicked.connect(self.label_click) # Receive slot function signal, each video image can get click response
                    else:
                        self.photos[i].setPixmap(
                            QPixmap(self.placeholder).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        print('The placeholder image was set successfully')
                self.totalLayout.addWidget(video) # Display the read video

    def init_id(self,Id):
        '''
        Get user id
        :param id: User ID
        '''
        self.id = Id

    def next_page(self):
        '''
        Display next page video
        '''
        print('self.pages[0]',self.pages[0])
        total_pages = self.pages[0] // self.pagecount # Total number of videos
        page = self.pages[0] % self.pagecount # Total number of pages
        print('Total pages:', total_pages)
        print('Current page:', self.pagenow)
        print('self.pages[0] % self.pagecount:', self.pages[0] % self.pagecount)
        if self.pagenow <= total_pages:
            self.pagenow += 1
            rs = db.db_VideoInterface(self.id, self.pagenow, self.pagecount)
            print(rs)
            if len(rs) > 0:
                for i in range(2):
                    self.videos[i].setPixmap(QPixmap(self.placeholder))
                for i in range(len(rs)):
                    self.videos[i].setPixmap(
                        QPixmap(rs[i][4]).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if page!=0:
                total_pages+=1
        else:
            QMessageBox.about(self,'tips',"It is the last page！")

    def last_page(self):
        '''
        Display previous page video
        '''
        if self.pagenow > 1:
            self.pagenow -= 1
        rs = db.db_VideoInterface(self.id, self.pagenow, self.pagecount)

        print(rs)
        if len(rs) > 0:
            for i in range(2):
                self.videos[i].setPixmap(QPixmap(self.placeholder))
            for i in range(len(rs)):
                self.videos[i].setPixmap(QPixmap(rs[i][4]).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def label_click(self,path):
        '''
        Click slot function
        :return:
        '''
        print('clicked me')
        self.path = path
        print('cilck on ：', self.path)
        if len(self.path) > 0:
             # Read current video path
            # self.imgLab.setPixmap(QPixmap(self.path).scaled(Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.videoWidget.show()
        else:
            QMessageBox.about(self, 'tips', 'None')

    def start_vid(self):
        '''
        Start timer
        :return:
        '''
        print('The path where the video needs to play:', self.path)
        self.cap = cv2.VideoCapture(self.path)

        if not self.cap.isOpened():
            print("Error: Could not open video.")
            return
        self.Time1.start(30)

    def play_video(self):
        '''
        Video playback
        :return:
        '''
        ret, frame = self.cap.read()
        print('ret:', ret)
        try:
            if ret:
                print('video play')
                h, w = frame.shape[:2]
                print('h,w:', h,w)
                newImg = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Color space conversion bgr->rgb
                # Build QImage
                videoImg = QImage(newImg, w, h, QImage.Format_RGB888)
                self.imgLab.setPixmap(QPixmap(videoImg).scaled(640,640,Qt.KeepAspectRatio, Qt.SmoothTransformation))
                # Fill into label
                self.imgLab.setScaledContents(True)
        except:
            print('The video cannot be played')

    def stop_video(self):
        '''
        Video pause
        :return:
        '''
        print('stop')
        self.Time1.stop()
        # self.Time2.stop()
        self.cap.release()
        self.imgLab.setPixmap(QPixmap(''))

    def video_speed(self, speed):
        '''
        Change video playback speed
        :return:
        '''
        try:
            self.fps = self.cap.get(5)  # Get video frames

            if speed == 1:
                print('The playback speed is adjusted to 0.5x')
                new_fps = self.fps*0.5
                self.Time1.start(60)
                # self.cap.set(cv2.CAP_PROP_FPS, new_fps)
            elif speed == 2:
                print('The playback speed is adjusted to 1.5x')
                new_fps = self.fps * 1.5
                self.Time1.start(20)
                # self.cap.set(cv2.CAP_PROP_FPS, new_fps)
            elif speed == 3:
                print('The playback speed is adjusted to 2.0x')
                new_fps = self.fps * 2.0
                self.Time1.start(15)
                # self.cap.set(cv2.CAP_PROP_FPS, new_fps)

        except:
            pass

    def delete_video(self):
        '''
        Delete the selected video file and database record
        '''
        # Check if a video is selected (self.path is set in label_click)
        if not hasattr(self, 'path') or not self.path: #make sure the path exits
            QMessageBox.about(self, 'Tips', 'Please select a video first')
            return

        # Confirm deletion with the user
        reply = QMessageBox.question(self, 'Confirm Delete',
                                     'Are you sure you want to delete this video?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                # 1. Delete the file from the file system
                if os.path.exists(self.path):
                    os.remove(self.path)
                    print(f"Deleted file: {self.path}")

                # 2. Delete from database
                # Note: Make sure you have implemented db.db_video_delete(id, path) in basic_tools.py
                # Assuming the function signature matches the save function structure
                db.db_video_delete(self.id, self.path)

                QMessageBox.about(self, 'Success', 'Video deleted successfully')

                # 3. Stop the current player if it is running and clear the display
                self.stop_video()

                # 4. Refresh the video list to update pagination/view
                self.init_control()

            except Exception as e:
                print(f"Error deleting video: {e}")
                QMessageBox.critical(self, 'Error', f'Failed to delete video: {str(e)}')
