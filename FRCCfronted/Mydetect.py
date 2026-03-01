
import argparse
import time
from pathlib import Path
import numpy as np
import cv2
import torch
import torch.backends.cudnn as cudnn
from numpy import random

from models.experimental import attempt_load
from utils.datasets import LoadStreams, LoadImages, letterbox
from utils.general import check_img_size, check_requirements, check_imshow, non_max_suppression, apply_classifier, \
    scale_coords, xyxy2xywh, strip_optimizer, set_logging, increment_path
from utils.plots import plot_one_box
from utils.torch_utils import select_device, load_classifier, time_synchronized, TracedModel

class myDetect(): # Prediction classes do not inherit
    def __init__(self):
        self.devices = 'cpu'         # device
        self.weights = 'best.pt'    # weights file
        self.imgsz = 640            # detected images of size
        self.augment = False
        self.img_size = 640
        self.stride = 32

        # Initialize
        # cpu or cuda
        set_logging()
        self.device = select_device(self.devices)
        self.half = self.device.type != 'cpu'  # half precision only supported on CUDA
        # opt = parser.parse_args()
        # device = select_device(self.device)
        # Load model
        '''
       Load the weight file (if no weight file is uploaded, the pre-trained model calibration will be downloaded automatically). 
       At the same time, check the image size. If the test image size is not a multiple of 32, it will be automatically adjusted to a multiple of 32.
        '''
        self.model = attempt_load(self.weights, map_location=self.device)  # load FP32 model
        stride = int(self.model.stride.max())  # model stride
        self.imgsz = check_img_size(self.imgsz, s=stride)  # check img_size

        #LoadImages：Three parameters: the predicted image path, the predicted image size supported by the network, and the maximum step size of the network
        # dataset = LoadImages(source, img_size=imgsz, stride=stride)

    def detect(self, img0):
        '''
        Prediction function
        :param img0: A frame to be detected
        :return: labels、boxs
        '''

        # Matrix training is performed, and the original image is scaled in a regular way
        img = letterbox(img0, self.img_size, stride=self.stride)[0]

        # Convert
        # ascontiguousarrayThis converts a discontiguous array into a contiguous array
        # run fast
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, to 3x416x416
        img = np.ascontiguousarray(img)
        img = torch.from_numpy(img).to(self.device)
        # Get names and colors
        # Color classification is performed on all classes to be predicted
        names = self.model.module.names if hasattr(self.model, 'module') else self.model.names
        colors = [[random.randint(0, 255) for _ in range(3)] for _ in names]

        old_img_w = old_img_h = self.imgsz
        old_img_b = 1

        t0 = time.time()

        # img = torch.from_numpy(img).to(self.device)
        img = img.half() if self.half else img.float()  # uint8 to fp16/32
        img /= 255.0  # 0 - 255 to 0.0 - 1.0
        if img.ndimension() == 3:
            img = img.unsqueeze(0)

        # Inference
        # The test pictures are fed into the network to obtain the prediction results
        t1 = time_synchronized()
        with torch.no_grad():  # Calculating gradients would cause a GPU memory leak
            pred = self.model(img, augment=self.augment)[0]
        t2 = time_synchronized()

        # Apply NMS
        # nms operation is performed on the prediction results to remove redundant boxes
        pred = non_max_suppression(pred)
        t3 = time_synchronized()

        # Process detections
        labels = []
        boxs = []
        for i, det in enumerate(pred):  # detections per image
            s = ''
            gn = torch.tensor(img0.shape)[[1, 0, 1, 0]]  # normalization gain whwh
            if len(det):
                # Rescale boxes from img_size to im0 size
                det[:, :4] = scale_coords(img.shape[2:], det[:, :4], img0.shape).round()

                # Write results
                for *xyxy, conf, cls in reversed(det):
                    label = f'{names[int(cls)]} {conf:.2f}'
                    labels.append(label)
                    # tensor转成list[]
                    box = [int(i.item()) for i in xyxy]
                    boxs.append(box)
                    print('label:', label)
                    print('box:', box)
            # Print time (inference + NMS)
            print(f'{s}Done. ({(1E3 * (t2 - t1)):.1f}ms) Inference, ({(1E3 * (t3 - t2)):.1f}ms) NMS')

        print(f'Done. ({time.time() - t0:.3f}s)')
        if len(labels) == 0:
            return None, None
        else:
            return labels, boxs