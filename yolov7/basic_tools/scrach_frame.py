import cv2
import argparse
import json
import os
import numpy as np
import errno


def getInfo(sourcePath):
    cap = cv2.VideoCapture(sourcePath)
    info = {
        "framecount": cap.get(cv2.CAP_PROP_FRAME_COUNT),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "heigth": int(cap.get(cv2.CAP_PROP_FRAME_Heigth)),
        "codec": int(cap.get(cv2.CAP_PROP_FOURCC))
    }
    cap.release()
    return info


def scale(img, xScale, yScale):
    res = cv2.resize(img, None, fx=xScale, fy=yScale, interpolation=cv2.INTER_AREA)
    return res


def resize(img, width, heigth):
    res = cv2.resize(img, (width, heigth), interpolation=cv2.INTER_AREA)
    return res


def extract_cols(image, numCols):
    # convert to np.float32 matrix that can be clustered
    Z = image.reshape((-1, 3))
    Z = np.float32(Z)

    # Set parameters for the clustering
    max_iter = 20
    epsilon = 1.0
    K = numCols
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, max_iter, epsilon)
    labels = np.array([])
    # cluster
    compactness, labels, centers = cv2.kmeans(Z, K, labels, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

    clusterCounts = []
    for idx in range(K):
        count = len(Z[np.where(labels == idx)])
        clusterCounts.append(count)

    rgbCenters = []
    for center in centers:
        bgr = center.tolist()
        bgr.reverse()
        rgbCenters.append(bgr)

    cols = []
    for i in range(K):
        iCol = {
            "count": clusterCounts[i],
            "col": rgbCenters[i]
        }
        cols.append(iCol)

    return cols


def calculateFrameStats(sourcePath, verbose=True, after_frame=0):  # 提取相邻帧的差别

    cap = cv2.VideoCapture(sourcePath)  # 提取视频

    data = {
        "frame_info": []
    }

    lastFrame = None
    while (cap.isOpened()):
        ret, frame = cap.read()
        if frame is None:
            break

        frame_number = cap.get(cv2.CAP_PROP_POS_FRAMES) - 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)  # 提取灰度信息
        gray = scale(gray, 0.25, 0.25)  # 缩放为原来的四分之一
        gray = cv2.GaussianBlur(gray, (9, 9), 0.0)  # 做高斯模糊
        # lastFrame = gray
        if frame_number < after_frame:
            lastFrame = gray
            continue

        if lastFrame is not None:
            diff = cv2.subtract(gray, lastFrame)  # 用当前帧减去上一帧
            diffMag = cv2.countNonZero(diff)  # 计算两帧灰度值不同的像素点个数
            frame_info = {
                "frame_number": int(frame_number),
                "diff_count": int(diffMag)
            }
            data["frame_info"].append(frame_info)
            if verbose:
                cv2.imshow('diff', diff)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        # Keep a ref to this frame for differencing on the next iteration
        lastFrame = gray

    cap.release()
    cv2.destroyAllWindows()

    # compute some states
    diff_counts = [fi["diff_count"] for fi in data["frame_info"]]
    data["stats"] = {
        "num": len(diff_counts),
        "min": np.min(diff_counts),
        "max": np.max(diff_counts),
        "mean": np.mean(diff_counts),
        "median": np.median(diff_counts),
        "sd": np.std(diff_counts)  # 计算所有帧之间, 像素变化个数的标准差
    }
    greater_than_mean = [fi for fi in data["frame_info"] if fi["diff_count"] > data["stats"]["mean"]]
    greater_than_median = [fi for fi in data["frame_info"] if fi["diff_count"] > data["stats"]["median"]]
    greater_than_one_sd = [fi for fi in data["frame_info"] if
                           fi["diff_count"] > data["stats"]["sd"] + data["stats"]["mean"]]
    greater_than_two_sd = [fi for fi in data["frame_info"] if
                           fi["diff_count"] > (data["stats"]["sd"] * 2) + data["stats"]["mean"]]
    greater_than_three_sd = [fi for fi in data["frame_info"] if
                             fi["diff_count"] > (data["stats"]["sd"] * 3) + data["stats"]["mean"]]

    # 统计其他信息
    data["stats"]["greater_than_mean"] = len(greater_than_mean)
    data["stats"]["greater_than_median"] = len(greater_than_median)
    data["stats"]["greater_than_one_sd"] = len(greater_than_one_sd)
    data["stats"]["greater_than_three_sd"] = len(greater_than_three_sd)
    data["stats"]["greater_than_two_sd"] = len(greater_than_two_sd)

    return data


def writeImagePyramid(destPath, name, seqNumber, image):
    fullPath = os.path.join(destPath, name + "_" + str(seqNumber) + ".png")
    cv2.imwrite(fullPath, image)


def detectScenes(sourcePath, destPath, data, name, verbose=False):
    destDir = os.path.join(destPath, "images")

    # TODO make sd multiplier externally configurable
    # diff_threshold = (data["stats"]["sd"] * 1.85) + data["stats"]["mean"]
    diff_threshold = (data["stats"]["sd"] * 2.05) + (data["stats"]["mean"])

    cap = cv2.VideoCapture(sourcePath)
    for index, fi in enumerate(data["frame_info"]):
        if fi["diff_count"] < diff_threshold:
            continue

        cap.set(cv2.CAP_PROP_POS_FRAMES, fi["frame_number"])
        ret, frame = cap.read()

        # extract dominant color
        small = resize(frame, 100, 100)
        cols = extract_cols(small, 5)
        data["frame_info"][index]["dominant_cols"] = cols

        if frame is not None:
            # file_name = sourcePath.split('.')[0]
            writeImagePyramid(destDir, name, fi["frame_number"], frame)

            if verbose:
                cv2.imshow('extract', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    cap.release()
    cv2.destroyAllWindows()
    return data


def makeOutputDirs(path):
    try:
        os.makedirs(os.path.join(path, "metadata"))
        os.makedirs(os.path.join(path, "images"))

    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise
# 定义不同命名规则对应的文件名匹配模式
filename_patterns = {
    "day_man": "./video/day_man_{}_{}_{}.mp4",
    "night_man": "./video/night_man_{}_{}_{}.mp4",
    "day_woman": "./video/day_woman_{}_{}_{}.mp4",
    "night_woman": "./video/night_woman_{}_{}_{}.mp4"
}

# 遍历所有文件名匹配模式
for pattern_name, filename_pattern in filename_patterns.items():
    for collector_id in range(1, 1000):
        for action_id in ["00", "10", "11", "20", "21", "30", "31", "40", "41"]:
            for segment_id in range(1, 10):
                # 使用字符串格式化函数构造具体的文件名
                filename = filename_pattern.format(str(collector_id).zfill(3), action_id, str(segment_id))
                # 判断文件是否存在
                if os.path.exists(filename):
                    # 如果文件存在，读取视频并抽帧
                    cap = cv2.VideoCapture(filename)
                    fps = cap.get(cv2.CAP_PROP_FPS)
                    imageNum = 0
                    sum = 0
                    timef = 6  # 隔6帧保存一张图片
                    while True:
                        (frameState, frame) = cap.read()  # 记录每帧及获取状态
                        sum += 1
                        if frameState == True and (sum % timef == 0):
                            # 格式转变，BGRtoRGB
                            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                            # 转变成Image
                            frame = Image.fromarray(np.uint8(frame))
                            frame = np.array(frame)
                            # RGBtoBGR满足opencv显示格式
                            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                            imageNum = imageNum + 1
                            # 存储路径
                            output_dir = "./output/{}_{}_{}".format(pattern_name, str(collector_id).zfill(3), action_id)
                            os.makedirs(output_dir, exist_ok=True)
                            filename = os.path.join(output_dir, "{}.jpg".format(str(imageNum).zfill(5)))
                            cv2.imwrite(filename, frame, [cv2.IMWRITE_JPEG_QUALITY, 100])
                            print(filename + " successful")  # 输出存储状态
                        elif frameState == False:
                            break
                    print('finish!')
                    cap.release()
"""
最终存储位置在"./output/{}{}{}"，其中{}的部分分别是pattern_name（命名规则），
collector_id（采集员编号）和action_id（动作编号）。存储的文件格式为jpg，命名方式为"{imageNum}.jpg"，
其中imageNum为图像编号，以0填充到5位。例如，第一张图像的文件名为"00001.jpg"。
"""

dest = "key frame"  # 抽取图像保存路径

makeOutputDirs(dest)
test_path = 'Fgatiue_driving_detection_video'  # 在这里修改视频路径
filenames = os.listdir(test_path)
count = 0
for filename in filenames:
    source = os.path.join(test_path, filename)

    name = filename.split('.')[0]

    data = calculateFrameStats(source, False, 0)
    data = detectScenes(source, dest, data, name, False)
    keyframeInfo = [frame_info for frame_info in data["frame_info"] if "dominant_cols" in frame_info]

    # Write out the results

    data_fp = os.path.join(dest, "metadata", name + "-meta.txt")
    with open(data_fp, 'w') as f:
        f.write(str(data))

    keyframe_info_fp = os.path.join(dest, "metadata", name + "-keyframe-meta.txt")
    with open(keyframe_info_fp, 'w') as f:
        f.write(str(keyframeInfo))
print(count)