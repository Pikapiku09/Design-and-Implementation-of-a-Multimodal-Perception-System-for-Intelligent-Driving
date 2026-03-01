# -*- coding: utf-8 -*-
# @Time    : 2024/11/21 20:23
# @Author  : zlh
# @File    : ShowPhotoWin.py

from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from basic_tools import db
from basic_tools import ClickLabel
import os


class showphotowin(QWidget):
    def __init__(self, w=1280, h=720):
        super().__init__()
        # Initialize window conditions
        self.w = w
        self.h = h
        self.resize(self.w, self.h)
        self.pagenow = 1
        self.pagecount = 2

        # Create a vertical layout
        self.totalLayout = QVBoxLayout()
        self.totalLayout.setContentsMargins(50, 30, 50, 30)  # Set margins, tighten interface
        self.setLayout(self.totalLayout)
        # Set default placeholder image
        self.placeholder = QPixmap('basic_img/holderplace.png').scaled(300, 300, Qt.KeepAspectRatio,
                                                                       Qt.SmoothTransformation)
        # Initialize photo display preview
        CLICK = ClickLabel.clicklabel
        # Create two ScalableLabel instances and add to layout
        self.photos = [CLICK(self), CLICK(self)]

        # Instantiate a visible window to display images
        self.photowin = QWidget()
        self.photowin.resize(1280, 720)
        self.photowin.setWindowTitle('photo show')

        self.imgLab = QLabel('', self.photowin)  # Control attached to window
        self.imgLab.setGeometry(320, 75, 640, 480)

        # Create previous page button and set style
        self.lastpageBtn = QPushButton('last Page', self)
        self.lastpageBtn.setStyleSheet('color:black;font:30px')
        # Create next page button and set style
        self.nextpageBtn = QPushButton('next page', self)
        self.nextpageBtn.setStyleSheet('color:black;font:30px')
        # Add buttons to layout
        self.totalLayout.addWidget(self.lastpageBtn)
        self.totalLayout.addWidget(self.nextpageBtn)

        # Create delete button in the photo display window
        self.deleteBtn = QPushButton('Delete', self.photowin)
        self.deleteBtn.setStyleSheet('color:red;font:30px')
        self.deleteBtn.setGeometry(740, 0, 200, 50)  # Position in the photo window

        # Connect button signals to corresponding slot functions
        self.lastpageBtn.clicked.connect(self.last_page)
        self.nextpageBtn.clicked.connect(self.next_page)
        self.deleteBtn.clicked.connect(self.delete_photo)  # Connect delete button to delete_photo function

    def init_control(self):
        self.pages = db.db_search_pages(self.id)
        # if self.pages[0] % self.pagecount == 0:
        #     # First case, pages is even, e.g., 8. When % pagecount is 0, it means it is the last page, no more photos, query not allowed
        # Initialize photo display preview
        rs = db.db_photo_select(self.pagenow, self.pagecount, self.id)
        # Second case, pages is odd, e.g., 5. When %, there is still one page left for turning

        # max = len(rs)
        print('photo list initcontrol')
        # print('self.pages：',rs[0])
        if not self.pages[0]:
            # print('len(rs)',len(rs[0]))
            for photo in self.photos:
                for j in range(2):
                    self.photos[j].setPixmap(
                        QPixmap(self.placeholder).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    print('The placeholder image was set successfully')
                self.totalLayout.addWidget(photo)
        else:
            print('picture')
            for photo in self.photos:
                for i in range(len(rs)):
                    if i < len(rs):
                        print('rs[i][3]', rs[i][3])
                        self.photos[i].setPixmap(
                            QPixmap(rs[i][3]).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        print('User image set successfully')
                        self.photos[i].set_path(rs[i][3])  # Load image path into click event
                        self.photos[i].clicked.connect(
                            self.clickphoto)  # Receive slot function signal, each video image can get click response
                    elif len(rs) == 0:
                        self.photos[i].setPixmap(
                            QPixmap(self.placeholder).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                        print('The placeholder image was set successfully')
                self.totalLayout.addWidget(photo)

    def next_page(self):
        '''
        Display photos of next page
        '''
        total_pages = self.pages[0] // self.pagecount  # Total number of photos
        page = self.pages[0] % self.pagecount  # Total number of pages
        print('Total pages:', total_pages)
        print('Current page:', self.pagenow)
        print('self.pages[0] % self.pagecount:', self.pages[0] % self.pagecount)
        if self.pagenow <= total_pages:
            self.pagenow += 1
            print('pagenow:', self.pagenow)
            rs = db.db_photo_select(self.pagenow, self.pagecount, self.id)
            print(rs)
            if len(rs) > 0:
                for i in range(2):
                    self.photos[i].setPixmap(QPixmap(self.placeholder))
                for i in range(len(rs)):
                    self.photos[i].setPixmap(
                        QPixmap(rs[i][3]).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            if page != 0:
                total_pages += 1
        else:
            QMessageBox.about(self, 'tips', "It's the last page！")

    def last_page(self):
        '''
        Display photos of last page
        '''
        if self.pagenow > 1:
            self.pagenow -= 1
            rs = db.db_photo_select(self.pagenow, self.pagecount, self.id)
            print(rs)
            if len(rs) > 0:
                for i in range(2):
                    self.photos[i].setPixmap(QPixmap(self.placeholder))
                    # Clear images first, then fill with fetched images
                for i in range(len(rs)):
                    self.photos[i].setPixmap(
                        QPixmap(rs[i][3]).scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        elif self.pagenow < 1:
            QMessageBox.about(self, 'tips', 'It is already the first page')

    def get_id(self, id):
        '''
        Get user id
        :param id: User ID
        '''
        self.id = id

    def clickphoto(self, path):
        '''
        When clicking on the picture
        :return:
        '''
        self.path = path
        print('click on ：', self.path)
        if len(self.path) > 0:
            # Read current photo path
            self.imgLab.setPixmap(QPixmap(self.path).scaled(480, 480, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.photowin.show()

    def delete_photo(self):
        '''
        Delete the selected photo file and database record
        '''
        # Check if a photo is selected (self.path is set in clickphoto)
        if not hasattr(self, 'path') or not self.path:
            QMessageBox.about(self, 'Tips', 'Please select a photo first')
            return

        # Confirm deletion with the user
        reply = QMessageBox.question(self, 'Confirm Delete',
                                     'Are you sure you want to delete this photo?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                # Delete the file from the file system
                if os.path.exists(self.path):
                    os.remove(self.path)
                    print(f"Deleted file: {self.path}")

                db.db_photo_delete(self.id, self.path)

                QMessageBox.about(self, 'Success', 'Photo deleted successfully')

                #  Refresh the photo list to update pagination/view
                self.init_control()

            except Exception as e:
                print(f"Error deleting photo: {e}")
                QMessageBox.critical(self, 'Error', f'Failed to delete photo: {str(e)}')
