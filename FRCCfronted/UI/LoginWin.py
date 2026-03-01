# -*- coding: utf-8 -*-
# @Time    : 2024/11/11 16:12
# @Author  : zlh
# @File    : LoginWin.py
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
import random
from UI.RegisterWin import RegisterWin
from UI.OpenVideo import VideoPlayer
from UI.mainWin import myWidget
from basic_tools import db
import os


class LoginWin(QWidget):
    LoginSignal = pyqtSignal()
    mainW = pyqtSignal()

    RegisterSignal = pyqtSignal()

    def __init__(self, w=1280, h=720):
        super().__init__()
        self.w = w
        self.h = h
        self.resize(self.w, self.h)  # Set width and height properties

        self.setWindowTitle('OpenCockpit')  # title
        self.setWindowIcon(QIcon('./basic_img/logo.png'))  # Icon

        self.ovideo = VideoPlayer()
        self.ovideo.ov_signal.connect(self.reback)
        self.init_control()

    def init_control(self):
        '''
        Initialize controls
        :return:
        '''

        # Layout settings
        self.totalLayout = QVBoxLayout()
        self.setLayout(self.totalLayout)
        # Set layout margins
        self.totalLayout.setContentsMargins(150, 100, 150, 150)
        # Title settings
        self.titleLab = QLabel('OpenCockpit', self)
        self.titleLab.setStyleSheet("color:white;font-family:Brush Script MT;font-weight: bold;font-size: 150px;")
        self.totalLayout.addWidget(self.titleLab)

        # First row
        self.line1 = QHBoxLayout()  # Horizontal layout
        # Control properties
        self.userLabel = QLabel('Username:', self)
        self.userLabel.setStyleSheet("color: white;")  # Set text color to white
        self.usernameEdit = QLineEdit(self)
        # Control font style
        self.usernameEdit.setStyleSheet("color: black;")  # Set text color to black
        # Add layout and widgets
        self.totalLayout.addLayout(self.line1)  # Add layout
        self.line1.addWidget(self.userLabel)  # Add widget
        self.line1.addWidget(self.usernameEdit)

        # Second row
        self.line2 = QHBoxLayout()  # Horizontal layout
        # Control properties settings
        self.passwordLabel = QLabel('Password:', self)  # Display character
        self.passwordLabel.setStyleSheet("color: white;")  # Set text color to white
        self.passwordEdit = QLineEdit(self)  # Input field
        self.passwordEdit.setEchoMode(QLineEdit.Password)
        # Control font style
        self.passwordEdit.setStyleSheet("color: black;")  # Set text color to black

        # 添加密码显示/隐藏按钮
        self.showPasswordBtn = QPushButton('Show', self)
        self.showPasswordBtn.setCheckable(True)
        self.showPasswordBtn.clicked.connect(self.toggle_password_visibility)

        # Add layout and widgets
        self.totalLayout.addLayout(self.line2)  # Add layout
        self.line2.addWidget(self.passwordLabel)  # Add widget
        self.line2.addWidget(self.passwordEdit)
        self.line2.addWidget(self.showPasswordBtn)  # 添加密码显示按钮

        # Third row
        self.line3 = QHBoxLayout()  # Horizontal layout
        self.CheckTextLabel = QLabel('Verification Code:', self)  # Display character
        self.CheckTextLabel.setStyleSheet("color: white;")  # Set text color to white
        self.CheckLabel = QLineEdit(self)  # Input field
        # Select and display captcha
        captcha_path = 'basic_img/Message'
        rs = os.listdir(captcha_path)
        self.captcha = random.choice(rs)
        print('Captcha is:', self.captcha)
        self.yzm = QLabel()
        self.yzm.setPixmap(QPixmap('{}/{}'.format(captcha_path, self.captcha)))
        self.yzm.mousePressEvent = self.refresh_captcha  # Add mouse click event
        # Add layout to window
        self.totalLayout.addLayout(self.line3)  # Add layout to window
        self.line3.addWidget(self.CheckTextLabel)
        self.line3.addWidget(self.CheckLabel)
        self.line3.addWidget(self.yzm)

        # Fourth row
        self.line4 = QHBoxLayout()  # Horizontal layout

        # Control properties
        self.loginBtn = QPushButton('Login', self)
        self.regBtn = QPushButton('Register', self)

        # Control font style
        self.loginBtn.setStyleSheet('color:black;font:20px')
        self.regBtn.setStyleSheet('color:black;font:20px')

        # Add layout
        self.totalLayout.addLayout(self.line4)  # Add layout
        self.line4.addWidget(self.regBtn)  # Add widget
        self.line4.addWidget(self.loginBtn)

        self.ReWin = RegisterWin()
        self.MAIN = myWidget()
        # Connect signals and slots
        self.ReWin.reback_signal.connect(self.reback)
        # Connect buttons to signals
        self.loginBtn.clicked.connect(self.db_user_login)
        self.regBtn.clicked.connect(self.registWin)

        self.LoginSignal.emit()
        self.RegisterSignal.emit()

    def registWin(self):
        '''
        Register function
        :return:
        '''
        print('Register')

        self.ReWin.L_signal.connect(self.reback)
        self.hide()
        self.ReWin.show()

    def db_user_login(self):

        # Open the database connection
        name = self.usernameEdit.text()
        password = self.passwordEdit.text()
        message = self.CheckLabel.text()
        rs = db.db_user_login(name, password)
        print('User input:', message)
        check = self.captcha.split(".")[0]
        print(check)
        print("Actual:", check)
        # Convert both input and captcha to lowercase for case-insensitive comparison
        if rs > 0 and message.lower() == check.lower():
            self.id = rs
            print('Success')
            self.hide()
            self.MAIN.update_name(name, self.id)
            self.MAIN.show()
        elif rs > 0 and message.lower() != check.lower():
            print('Verification code wrong')
            QMessageBox.about(self, 'Tip', 'Verification code is incorrect')
        else:
            print('Username or password is incorrect')
            QMessageBox.about(self, 'Tip', 'Username or password is incorrect!')

    def reback(self):
        '''
        Return button function, slot function for returning to login screen from registration screen
        :return:
        '''
        print('GoBack')
        self.show()

    def closeEvent(self, event):
        '''
        Close window event
        :param QCloseEvent:
        :return:
        '''
        self.setStyleSheet("color: black;")
        if QMessageBox.question(self, 'Tip', 'Are you sure you want to exit?') == QMessageBox.Yes:
            event.accept()  # Accept 'Yes' to exit the program
        else:
            event.ignore()

    def paintEvent(self, event):
        painter = QPainter(self)
        # Auto-scale image size
        self.bg_image = QPixmap('./basic_img/bg.jpg')  # Set background
        scaled_bg = self.bg_image.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled_bg)

    def refresh_captcha(self, event):
        """
        Refresh captcha
        :param event: Mouse event
        :return:
        """
        captcha_path = 'basic_img/Message'
        rs = os.listdir(captcha_path)
        self.captcha = random.choice(rs)
        print('New verification code is:', self.captcha)
        self.yzm.setPixmap(QPixmap('{}/{}'.format(captcha_path, self.captcha)))

        # Clear input field
        self.CheckLabel.clear()

    def toggle_password_visibility(self):
        """
        Switch password display/hide
        """
        if self.showPasswordBtn.isChecked():
            # show pwd
            self.passwordEdit.setEchoMode(QLineEdit.Normal)
            self.showPasswordBtn.setText('Hide')
        else:
            # hide pwd
            self.passwordEdit.setEchoMode(QLineEdit.Password)
            self.showPasswordBtn.setText('Show')
