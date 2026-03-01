# -*- coding: utf-8 -*-
# @Time    : 2024/11/20 18:01
# @Author  : zlh
# @File    : CameraWin.py
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
import cv2
import time
from basic_tools import db
from Mydetect import myDetect


class camerawin(QWidget):
    def __init__(self, w=1280, h=720):
        super().__init__()
        # Initialize window conditions
        self.w = w
        self.h = h
        self.resize(self.w, self.h)
        self.camera_state = False
        # self.model_flag = False

        # Define color map for different labels (BGR format for OpenCV)
        self.label_colors = {
            'normal': (0, 255, 0),  # Green
            'closeeyes': (0, 0, 255),  # Red
            'yawl': (0, 165, 255),  # Orange/Yellow
            'phone': (255, 0, 255),  # Purple/Magenta
            'lookaround': (255, 255, 0)  # Cyan
        }

        self.init_control()

    def init_control(self):
        '''
        Initialize controls
        :return:
        '''
        self.totallayout = QVBoxLayout()
        self.setLayout(self.totallayout)
        self.imgLab = QLabel('', self)  # Add control filler box

        self.opencameraBtn = QPushButton('Turn on the camera')

        self.closecameraBtn = QPushButton('Turn off the camera')

        self.opencameraBtn.clicked.connect(self.open_camera)

        self.closecameraBtn.clicked.connect(self.video_stop)

        self.totallayout.addWidget(self.imgLab)
        self.totallayout.addWidget(self.opencameraBtn)

        self.totallayout.addWidget(self.closecameraBtn)

        self.Time1 = QTimer()  # Timer for video list playback
        self.Time1.timeout.connect(self.update_frame)  # Bind to corresponding slot function
        self.Time2 = QTimer()  # Timer for video list playback
        self.Time2.timeout.connect(self.save_video)  # Bind to corresponding slot function

    def save_frame(self):
        '''
        Save one frame captured by camera
        :return:
        '''
        print('saveffff')
        # self.Time1.start(30)
        # # QMessageBox(self, 'tip', 'Opening camera...')
        if self.camera_state == False:
            QMessageBox.about(self, 'tip', 'Please turn on the camera first.')
        else:
            ret, frame = self.camera.read()
            file = time.strftime('%Y%m%d%H%M%S', time.localtime()) + '.jpg'
            photo_time = time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())
            file_path = 'basic_img/ScrathPhoto/' + file

            if ret:
                cv2.imwrite(file_path, frame)
                # Write to database
                db.db_photo_insert(file,  # photo_name
                                   file_path,  # photo_address
                                   photo_time,  # photo_time
                                   self.id  # id
                                   )
            print('insert into')
            QMessageBox.about(self, 'tip', 'Screenshot completed successfully')

    def open_camera(self):
        '''
        Open camera when clicking fatigue check
        :return:
        '''
        print('open_camera')
        self.frameCount = 0
        self.sec = 0
        self.camera_state = True
        self.camera = cv2.VideoCapture(0)
        self.detect = myDetect()
        self.cam_w = int(self.camera.get(3))
        self.cam_h = int(self.camera.get(4))
        timestr = time.strftime('%Y%m%d-%H%M%S', time.localtime())
        # 2. Create object to save video
        SavePath = '{}.mp4'.format(timestr)
        retval = cv2.VideoWriter.fourcc('D', 'I', 'V', 'X')  # Determine the encoding format for saving video
        self.out = cv2.VideoWriter(SavePath, retval, 24,
                                   (self.cam_w, self.cam_h))  # Path, encoding format, frame rate, width and height

        self.Time1.start(30)
        self.Time2.start(30)

    def update_frame(self):
        '''
        Refresh frame display
        :return:
        '''

        self.sec = self.sec + 1

        ret, frame = self.camera.read()
        if ret:
            print('self.sec:', self.sec)
            if self.sec == 5:

                labels, boxs = self.detect.detect(frame)
                if labels is not None:
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    i = 0
                    for box in boxs:
                        # Get the full label string (e.g., "yawl 0.85")
                        full_label = labels[i]
                        # Extract the class name (remove confidence score)
                        class_name = full_label.split()[0] if ' ' in full_label else full_label

                        # Get color from the dictionary, default to white if not found
                        box_color = self.label_colors.get(class_name, (255, 255, 255))

                        cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), box_color, 5)
                        cv2.putText(frame, full_label, (box[0], box[1]), font, 1, box_color, 5)
                        i += 1

                self.sec = 0
            h, w = frame.shape[:2]
            newImg = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Color space conversion bgr->rgb
            # Build QImage
            videoImg = QImage(newImg, w, h, QImage.Format_RGB888)
            self.imgLab.setPixmap(QPixmap(videoImg))
            # Fill into label
            self.imgLab.setScaledContents(True)

    def video_stop(self):
        '''
        Stop video playback
        :return:
        '''

        print('Stop')
        if self.camera_state == True:
            self.Time1.stop()  # Close camera
            self.Time2.stop()  # Recording ends
            self.camera.release()  # Release video resources to achieve pause

    def update_id(self, ID):
        self.id = ID
        print("id:", ID)

    def model_detect(self):
        '''
        Open camera for prediction, call model
        :return:
        '''

        # self.model_flag = True

        ret, frame = self.camera.read()
        if ret:
            labels, boxs = self.detect.detect(frame)
            print('labels:', labels)
            print('boxs:', boxs)
            if labels is not None:
                font = cv2.FONT_HERSHEY_SIMPLEX
                i = 0
                for box in boxs:
                    # Get the full label string
                    full_label = labels[i]
                    # Extract the class name
                    class_name = full_label.split()[0] if ' ' in full_label else full_label

                    # Get color from the dictionary
                    box_color = self.label_colors.get(class_name, (255, 255, 255))

                    cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), box_color, 5)
                    cv2.putText(frame, full_label, (box[0], box[1]), font, 1, box_color, 5)
                    i += 1

            # # Display processed image on interface
            # h, w = frame.shape[:2]
            # newImg = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)  # Color space conversion bgr->rgb
            # videoImg = QImage(newImg, w, h, QImage.Format_RGB888)
            # self.imgLab.setPixmap(QPixmap(videoImg))
            # self.imgLab.setScaledContents(True)
            # cv2.waitKey(600)

    def save_video(self):
        '''
        Save video recording
        :return:
        '''
        # Get system time
        timestr = time.strftime('%Y%m%d-%H%M%S', time.localtime())
        ret, frame = self.camera.read()
        if ret:
            self.out.write(frame)
            if self.frameCount == 1:
                print('save video cover')
                self.facepath = 'basic_img/videointerface/{}.jpg'.format(timestr)
                cv2.imwrite(self.facepath, frame)
            self.frameCount += 1
            # print(self.frameCount)
            if self.frameCount == 150:
                print('Save the video recording')
                self.frameCount = 0
                # 2. Create object to save video
                SavePath = 'basic_img/Video/{}.mp4'.format(timestr)
                retval = cv2.VideoWriter.fourcc('D', 'I', 'V', 'X')  # Determine the encoding format for saving video
                self.out = cv2.VideoWriter(SavePath, retval, 24, (
                self.cam_w, self.cam_h))  # Path, encoding format, frame rate, width and height
                db.db_video_save(self.id, video_name=timestr, video_address=SavePath, video_interface=self.facepath)
