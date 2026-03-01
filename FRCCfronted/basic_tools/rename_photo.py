import os

# 设置照片所在的文件夹路径
folder_path = 'img'
print(folder_path)
# 获取文件夹中所有照片文件的列表
photos = [f for f in os.listdir(folder_path) if f.endswith('.png')]
print(photos)
# 对照片文件进行排序，这里假设文件名可以转换为整数进行比较
photos.sort(key=lambda x: int(''.join(filter(str.isdigit, x))))

# 设置重命名后的文件名格式
new_file_name_format = 'photo_{}.png'

# 重命名文件，并将新文件名存储在列表中
new_file_names = []
for index, photo in enumerate(photos):
    # 构建新的文件名
    new_file_name = new_file_name_format.format(index + 1)
    # 重命名操作
    os.rename(os.path.join(folder_path, photo), os.path.join(folder_path, new_file_name))
    # 将新文件名添加到列表中
    new_file_names.append(new_file_name)

# 将新文件名写入当前文件夹下的txt文件
with open(os.path.join(folder_path, 'photo_filenames.txt'), 'w') as file:
    for name in new_file_names:
        file.write('data/img/'+name + '\n')

print("照片已重新命名，文件名列表已保存到photo_filenames.txt。")
