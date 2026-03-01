# -*- coding: utf-8 -*-
# @Time    : 2024/11/12 19:40
# @Author  : zlh
# @File    : data_dispose.py

import os
from random import sample
xml_path='./datasets/images/'
file_list = os.listdir(xml_path)  # xml_path中是上述步骤OBS桶文件夹C中的所有文件，记得拷贝到本地
print(len(file_list))
val_file_list = sample(file_list, 200)  # 选择了300张做测试集
line = ''
for i in val_file_list:
    if i.endswith('.png'):
        line += 'datasets/images/' + i + '\n'  # datasets/Fatigue_driving_detection/images/ 是yolov7训练使用的
with open('./datasets/val.txt', 'w+') as f:
    f.writelines(line)

test_file_list = sample(file_list, 200)
line = ''
for i in test_file_list:
    if i.endswith('.png'):
        line += 'datasets/images/' + i + '\n'
with open('./datasets/test.txt', 'w+') as f:
    f.writelines(line)

line = ''
for i in file_list:
    if i not in val_file_list and i not in test_file_list:
        if i.endswith('.png'):
            line += 'datasets/images/' + i + '\n'
with open('./datasets/train.txt', 'w+') as f:
    f.writelines(line)
