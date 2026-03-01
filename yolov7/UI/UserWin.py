# -*- coding: utf-8 -*-
# @Time    : 2024/11/21 17:07
# @Author  : zlh
# @File    : UserWin.py
from PyQt5 import QtGui, QtWidgets, QtCore
import sys, os
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from basic_tools import db
from PIL import Image


class userwin(QWidget):
    logout_signal = pyqtSignal()  # 添加退出信号

    def __init__(self, w=1280, h=720):
        super().__init__()
        # Automatically initialize window conditions
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        self.init_control()

    def init_control(self):
        self.totalLayout = QVBoxLayout()  # Total layout
        self.setLayout(self.totalLayout)
        self.totalLayout.setContentsMargins(50, 30, 50, 30)
        self.initpicture = QLabel()  # Avatar frame control
        self.initpicture.setAlignment(Qt.AlignCenter)  # Center
        self.up_avtar('')  # Get and update avatar

        self.username = QLabel()  # Username display
        self.username.setStyleSheet('font:40px; font-family:Arial; color:white')
        self.username.setAlignment(Qt.AlignCenter)

        self.initpicture.setFixedSize(640, 640)  # Set avatar max size (width/height)

        self.headpicture = QPushButton('Change profile picture')  # Change avatar button
        self.headpicture.clicked.connect(self.openimage)  # Click button to trigger image change
        self.changepd = QPushButton('Change password')  # Change password button
        self.changepd.clicked.connect(self.change_pwd)  # Click button to trigger password change

        # Add controls to layout
        self.totalLayout.addWidget(self.initpicture)
        self.totalLayout.addWidget(self.username)
        self.totalLayout.addWidget(self.changepd)
        self.totalLayout.addWidget(self.headpicture)

    def update_name(self, name, id):
        '''
        Get user id and name via login
        :param name:
        :param id:
        :return:
        '''
        self.name = name
        self.id = id
        self.username.setText(name)  # Display on window

    def openimage(self):
        '''
        Pop up window to upload image
        :return:
        '''
        try:
            imgName, imgType = QFileDialog.getOpenFileName(self, "Open the picture", "",
                                                           "*.jpg;;*.png;;All Files(*)")  # Pop up window to select photo to change
            img = Image.open(imgName)
            # Save the path of the newly added image to a file
            file_cut = imgName.split('/')[-1]

            # Copy the image to the img directory
            file_path = 'basic_img/avatar/' + file_cut

            img.save(file_path)  # Save locally
            # self.initpicture.setPixmap(QPixmap(file_path))
            print('Updated avatar path:', file_path)

            self.up_avtar(file_path)  # Update on the interface

            db.update_avatars(file_path, self.id)  # Modify database information
            QMessageBox.about(self, 'tips', 'Avatar modification successful')
        except Exception as e:
            print(f"Error opening image: {e}")
            QMessageBox.critical(self, 'Error', f'The picture cannot be opened.: {str(e)}')

    def change_pwd(self):
        '''
        Change password with old password verification and new password confirmation
        :return:
        '''
        try:
            # 输入旧密码
            old_pwd, ok1 = QInputDialog.getText(self, 'Change password', 'Please enter old password:',
                                                QLineEdit.Password)
            if not ok1 or not old_pwd:
                return

            # 验证旧密码
            # 调用db.db_user_login验证，注意db.db_user_login返回的是user_id
            user_id = db.db_user_login(self.name, old_pwd)
            if user_id != self.id:
                QMessageBox.critical(self, 'Error', 'Old password is incorrect!')
                return

            # 输入新密码
            new_pwd, ok2 = QInputDialog.getText(self, 'Change password', 'Please enter new password:',
                                                QLineEdit.Password)
            if not ok2 or not new_pwd:
                return

            # 确认新密码
            confirm_pwd, ok3 = QInputDialog.getText(self, 'Change password', 'Please confirm new password:',
                                                    QLineEdit.Password)
            if not ok3 or new_pwd != confirm_pwd:
                QMessageBox.critical(self, 'Error', 'Passwords do not match!')
                return

            # 更新密码
            db.update_password(new_pwd, self.id)
            QMessageBox.about(self, 'Success', 'Password modified successfully')

            # 发射退出信号，触发重新登录
            self.logout_signal.emit()

        except Exception as e:
            print(f"Error changing password: {e}")
            QMessageBox.critical(self, 'Error', f'Failed to change password: {str(e)}')

    def up_avtar(self, path):
        try:
            filepath = db.db_headpicture(path)
            if not filepath:  # Change this to a more accurate judgment
                # Load default avatar automatically if there is no avatar
                default_path = os.path.abspath('basic_img/images/momo.jpg')
                self.initpicture.setPixmap(QPixmap(default_path))
            else:
                # Load user's avatar
                user_path = os.path.abspath(filepath)
                self.initpicture.setPixmap(QPixmap(user_path))
        except Exception as e:
            print(f"Error updating avatar: {e}")
            # QMessageBox.critical(self, 'Error', f'Unable to update the profile picture: {str(e)}')
