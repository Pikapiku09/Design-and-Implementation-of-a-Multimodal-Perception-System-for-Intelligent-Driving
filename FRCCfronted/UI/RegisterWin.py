# -*- coding: utf-8 -*-
# @Time    : 2024/11/15 16:14
# @Author  : zlh
# @File    : RegisterWin.py
from PyQt5.QtWidgets import *  # Import all contents from the QtWidgets module of the PyQt5 library
from PyQt5.QtGui import QIcon, QPixmap, QPainter
from PyQt5.QtCore import *
from basic_tools import PhoneCheck, db


class RegisterWin(QWidget):

    reback_signal = pyqtSignal() # Create a signal to return to the main interface
    L_signal = pyqtSignal() # Create a signal to return to the login screen

    def __init__(self, w=1280, h=720):
        super().__init__()
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        self.setWindowTitle('Register')

        # Set the size and color of the text
        # self.setStyleSheet('color:white;font:20px')

        self.init_control()


    def init_control(self):
        # Vertical layout
        self.totalLayout = QVBoxLayout()
        self.setLayout(self.totalLayout)
        self.totalLayout.setContentsMargins(50,50,50,50)

        # First row
        self.line1 = QHBoxLayout() # Horizontal layout
        self.totalLayout.addLayout(self.line1) # Add layout
        self.userLabel = QLabel('Username:', self)
        self.usernameEdit = QLineEdit(self)
        self.line1.addWidget(self.userLabel)  # Add widget
        self.line1.addWidget(self.usernameEdit)
        self.usernameEdit.setStyleSheet("color: black;")  # Set text color to black
        self.userLabel.setStyleSheet("color: white;")  # Set text color to white

        # Second row
        self.line2 = QHBoxLayout()  # Horizontal layout
        self.totalLayout.addLayout(self.line2)  # Add layout
        self.passwordLabel = QLabel('Password:', self)
        self.passwordEdit = QLineEdit(self)
        self.line2.addWidget(self.passwordLabel)  # Add widget
        self.line2.addWidget(self.passwordEdit)
        self.passwordEdit.setStyleSheet("color: black;")  # Set text color to black
        self.passwordLabel.setStyleSheet("color: white;")  # Set text color to white

        # Third row
        self.line3 = QHBoxLayout()  # Horizontal layout
        self.totalLayout.addLayout(self.line3)  # Add layout
        self.PhoneLabel = QLabel('Phone Number:', self)
        self.PhoneEdit = QLineEdit(self)
        self.line3.addWidget(self.PhoneLabel)  # Add widget
        self.line3.addWidget(self.PhoneEdit)
        self.PhoneEdit.setStyleSheet("color: black;")  # Set text color to black
        self.PhoneLabel.setStyleSheet("color: white;")  # Set text color to white

        # Fourth row
        self.line4 = QHBoxLayout()  # Horizontal layout
        # Basic property settings
        self.IdCodeLabel = QLabel('Verification Code:', self)
        self.IdCodeEdit = QLineEdit(self)
        self.phoneBtn = QPushButton('Get Verification Code', self)
        self.phoneBtn.clicked.connect(self.PhoneCheck)
        self.phoneBtn.setStyleSheet("color: black;")  # Set text color to black
        self.IdCodeLabel.setStyleSheet("color: white;")  # Set text color to white
        # Add layout and widgets
        self.totalLayout.addLayout(self.line4)
        self.line4.addWidget(self.IdCodeLabel)
        self.line4.addWidget(self.IdCodeEdit)
        self.line4.addWidget(self.phoneBtn)
        self.IdCodeEdit.setStyleSheet("color: black;")  # Set text color to black

        # Fifth row
        self.line5 = QHBoxLayout()  # Horizontal layout
        self.totalLayout.addLayout(self.line5)  # Add layout
        self.regBtn = QPushButton('Register', self)
        self.quitBtn = QPushButton('Back', self)
        self.regBtn.setStyleSheet('color:black;font:20px')
        self.quitBtn.setStyleSheet('color:black;font:20px')
        self.line5.addWidget(self.regBtn)  # Add widget
        self.line5.addWidget(self.quitBtn)

        self.regBtn.clicked.connect(self.registWin)
        self.quitBtn.clicked.connect(self.return_method)
        # self.LoginWin.connect()
        # Set label layout margins
        self.totalLayout.setContentsMargins(300, 300, 300, 300)

    def sign_up(self):
        '''
        Login verification function
        :return:
        '''
        print('init')

    def PhoneCheck(self):
        '''
        Phone number verification
        :return:
        '''
        self.Phone = self.PhoneEdit.text()
        if self.Phone is not None:
            self.rs = PhoneCheck.phonecheck(self.Phone)
            print('Sent verification code is:', self.rs)
            QMessageBox.about(self, 'Tips', 'Sent successfully')
        else:
            QMessageBox.about(self, 'Tips', 'Phone number cannot be empty')


    def return_method(self):
        '''
        Slot function for clicking the 'Back' button to return to the login interface
        :return:
        '''
        print('Return')
        self.hide()
        self.reback_signal.emit()

    def registWin(self):
        '''
        Registration function
        :return:
        '''
        print('Register 2')
        try:
            self.setStyleSheet("color: black;")
            name = self.usernameEdit.text()
            pwd = self.passwordEdit.text()
            Phone = self.PhoneEdit.text()
            check = self.IdCodeEdit.text()
            print('Phone:', Phone)
            print('Check:', check)
            if not all([name, pwd, Phone]):
                raise ValueError("All fields must be filled in")
            if check != self.rs:
                raise ValueError("Verification code is incorrect")
            else:
                db.db_user_Register(name, pwd)
                print("Registration successful")
                QMessageBox.about(self, 'Tips', "Registration successful")
            self.hide()
            self.L_signal.emit()
        except Exception as e:
            print(f"Registration failed: {e}")
            QMessageBox.critical(self, 'Error', f'Registration failed: it is a wrong code')


    def paintEvent(self, event):
        painter = QPainter(self)
        # Auto-scale image size
        self.bg_image = QPixmap('./basic_img/Geek001.jpg')  # Set background
        scaled_bg = self.bg_image.scaled(self.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        painter.drawPixmap(0, 0, scaled_bg)