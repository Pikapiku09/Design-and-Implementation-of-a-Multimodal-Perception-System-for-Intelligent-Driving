# -*- coding: utf-8 -*-
# @Time    : 2024/11/25 9:52
# @Author  : zlh
# @File    : mytest.py

import cv2
from Mydetect import myDetect

m = myDetect()

cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    if ret:
        labels, boxs = m.detect(frame)
        print('labels:',labels)
        print('boxs:', boxs)
        if labels is not None:
            colors = [0, 255, 0]
            colors_float = colors[0] + colors[1] * 256 + colors[2] * 256 * 256
            i = 0
            for box in boxs:
                cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), colors_float, 5)
                cv2.putText(frame, labels[i], (box[0], box[1]), cv2.FONT_HERSHEY_COMPLEX, 1, colors_float, 5)
                i += 1
        cv2.imshow("image", frame)
        cv2.waitKey(3)

cv2.waitKey()
cv2.destoryAllWindows()