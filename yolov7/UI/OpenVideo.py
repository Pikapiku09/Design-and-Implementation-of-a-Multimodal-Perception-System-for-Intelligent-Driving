# -*- coding: utf-8 -*-
# @Time    : 2024/11/13 8:30
# @Author  : zlh
# @File    : OpenVideo.py

import cv2
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from ffpyplayer.player import MediaPlayer


class VideoPlayer(QWidget):
    ov_signal = pyqtSignal()

    def __init__(self, w=1280, h=720):
        super().__init__()
        self.w = w
        self.h = h
        self.resize(self.w, self.h)
        self.tips = QLabel(self)
        self.tips.setText('Press Esc to skip')
        self.openvideo()

    def openvideo(self):
        path = 'basic_img/rainbowcat.mp4'
        cap = cv2.VideoCapture(path)  # Read video
        player = MediaPlayer(path)
        print(f"Video opened: {cap.isOpened()}")
        while cap.isOpened():
            ret, frame = cap.read()
            if ret:
                # Add text hint on the top-left corner of the video frame
                cv2.putText(frame, 'Press Esc to skip', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                cv2.imshow('OpenCockpit', frame)
                key = cv2.waitKey(25)
                if key == 27:  # ESC key code
                    print('ESC pressed')
                    cap.release()
                    cv2.destroyAllWindows()
                    break
            else:
                cap.release()
                cv2.destroyAllWindows()
                break
        print('Playback finished')
        self.ov_signal.emit()
