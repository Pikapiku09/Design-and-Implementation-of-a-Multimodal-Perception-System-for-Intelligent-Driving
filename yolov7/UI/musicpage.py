# -*- coding: utf-8 -*-
# @Time    : 2026/2/11 16:15
# @Author  : zlh
# @File    : musicpage.py
# -*- coding: utf-8 -*-
# @FileName: MusicPage.py
# @Author  : zlh
# @Time    : 2024/1/15

import sys
import os
import shutil
import json
from datetime import datetime
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent, QMediaPlaylist
from PyQt5.QtMultimediaWidgets import QVideoWidget
import eyed3  # 用于读取MP3元数据


class MusicPage(QWidget):
    """音乐播放器页面 - 支持上传、保存和播放MP3文件"""

    def __init__(self, parent=None, w=1280, h=720):
        super().__init__(parent)

        # 初始化窗口条件
        self.w = w
        self.h = h
        self.resize(self.w, self.h)

        # 初始化音乐相关变量
        self.current_song = None
        self.current_song_path = None
        self.song_list = []  # 存储歌曲信息列表
        self.current_index = -1

        # 设置音乐存储目录
        self.music_dir = "user_music"
        if not os.path.exists(self.music_dir):
            os.makedirs(self.music_dir)

        # 设置配置文件
        self.config_file = "music_config.json"

        # 初始化媒体播放器
        self.player = QMediaPlayer()
        self.playlist = QMediaPlaylist()
        self.player.setPlaylist(self.playlist)

        # 初始化UI
        self.init_control()

        # 加载保存的音乐
        self.load_saved_music()

        # 连接信号
        self.connect_signals()

    def init_control(self):
        """初始化控件"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)

        # =========== 标题区域 ===========
        title_label = QLabel("🎵 个人音乐播放器")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 32px;
                font-weight: bold;
                color: #2c3e50;
                padding: 15px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3498db, stop:1 #9b59b6);
                border-radius: 10px;
                color: white;
            }
        """)
        main_layout.addWidget(title_label)

        # =========== 上传区域 ===========
        upload_group = QGroupBox("📤 上传音乐")
        upload_group.setStyleSheet("""
            QGroupBox {
                font-size: 16px;
                font-weight: bold;
                color: #34495e;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 10px 0 10px;
            }
        """)

        upload_layout = QHBoxLayout()

        self.upload_btn = QPushButton("选择MP3文件")
        self.upload_btn.setIcon(QIcon.fromTheme("document-open"))
        self.upload_btn.setStyleSheet("""
            QPushButton {
                padding: 12px 24px;
                font-size: 14px;
                font-weight: bold;
                background-color: #3498db;
                color: white;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
        """)
        self.upload_btn.clicked.connect(self.upload_music)

        self.upload_label = QLabel("未选择文件")
        self.upload_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #f8f9fa;
                border: 1px dashed #bdc3c7;
                border-radius: 5px;
                color: #7f8c8d;
                font-style: italic;
            }
        """)

        upload_layout.addWidget(self.upload_btn)
        upload_layout.addWidget(self.upload_label, 1)

        upload_group.setLayout(upload_layout)
        main_layout.addWidget(upload_group)

        # =========== 音乐列表区域 ===========
        list_group = QGroupBox("🎼 我的音乐库")
        list_group.setStyleSheet(upload_group.styleSheet())

        list_layout = QVBoxLayout()

        # 列表控制按钮
        list_control_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("刷新列表")
        self.refresh_btn.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_btn.clicked.connect(self.load_saved_music)

        self.delete_btn = QPushButton("删除选中")
        self.delete_btn.setIcon(QIcon.fromTheme("edit-delete"))
        self.delete_btn.clicked.connect(self.delete_selected_song)
        self.delete_btn.setEnabled(False)

        list_control_layout.addWidget(self.refresh_btn)
        list_control_layout.addWidget(self.delete_btn)
        list_control_layout.addStretch()

        # 音乐列表
        self.music_list = QListWidget()
        self.music_list.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #ecf0f1;
            }
            QListWidget::item:hover {
                background-color: #ecf0f1;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """)
        self.music_list.setAlternatingRowColors(True)
        self.music_list.itemSelectionChanged.connect(self.on_song_selected)

        list_layout.addLayout(list_control_layout)
        list_layout.addWidget(self.music_list)

        list_group.setLayout(list_layout)
        main_layout.addWidget(list_group, 1)  # 给列表更多空间

        # =========== 播放控制区域 ===========
        control_group = QGroupBox("🎮 播放控制")
        control_group.setStyleSheet(upload_group.styleSheet())

        control_layout = QVBoxLayout()

        # 歌曲信息显示
        self.song_info_label = QLabel("未选择歌曲")
        self.song_info_label.setAlignment(Qt.AlignCenter)
        self.song_info_label.setStyleSheet("""
            QLabel {
                font-size: 14px;
                padding: 8px;
                background-color: #f1f8ff;
                border: 1px solid #d1e7ff;
                border-radius: 5px;
                color: #0366d6;
            }
        """)
        control_layout.addWidget(self.song_info_label)

        # 播放进度条
        progress_layout = QHBoxLayout()

        self.time_label = QLabel("00:00")
        self.time_label.setStyleSheet("color: white")
        self.time_label.setFixedWidth(50)

        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.sliderMoved.connect(self.seek_position)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #bdc3c7;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #3498db;
                border-radius: 3px;
            }
            QSlider::add-page:horizontal {
                background: #bdc3c7;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #2c3e50;
                width: 18px;
                margin: -6px 0;
                border-radius: 9px;
            }
        """)

        self.duration_label = QLabel("00:00")
        self.duration_label.setStyleSheet("color: white")
        self.duration_label.setFixedWidth(50)

        progress_layout.addWidget(self.time_label)
        progress_layout.addWidget(self.progress_slider, 1)
        progress_layout.addWidget(self.duration_label)
        control_layout.addLayout(progress_layout)

        # 控制按钮
        button_layout = QHBoxLayout()

        self.prev_btn = QPushButton("⏮")
        self.prev_btn.setFixedSize(50, 50)
        self.prev_btn.clicked.connect(self.play_previous)

        self.play_btn = QPushButton("▶")
        self.play_btn.setFixedSize(60, 60)
        self.play_btn.setStyleSheet("""
            QPushButton {
                font-size: 20px;
                font-weight: bold;
                background-color: #27ae60;
                color: white;
                border-radius: 30px;
                border: none;
            }
            QPushButton:hover {
                background-color: #219653;
            }
        """)
        self.play_btn.clicked.connect(self.toggle_play)

        self.stop_btn = QPushButton("⏹")
        self.stop_btn.setFixedSize(50, 50)
        self.stop_btn.clicked.connect(self.stop_playback)

        self.next_btn = QPushButton("⏭")
        self.next_btn.setFixedSize(50, 50)
        self.next_btn.clicked.connect(self.play_next)

        button_layout.addStretch()
        button_layout.addWidget(self.prev_btn)
        button_layout.addWidget(self.play_btn)
        button_layout.addWidget(self.stop_btn)
        button_layout.addWidget(self.next_btn)
        button_layout.addStretch()
        control_layout.addLayout(button_layout)

        # 音量控制
        volume_layout = QHBoxLayout()

        volume_label = QLabel("🔊 音量")
        volume_label.setStyleSheet("color: white")
        volume_label.setFixedWidth(60)

        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.valueChanged.connect(self.set_volume)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                height: 6px;
                background: #bdc3c7;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #2ecc71;
                border-radius: 3px;
            }
            QSlider::add-page:horizontal {
                background: #bdc3c7;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #27ae60;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
        """)

        self.volume_label = QLabel("70%")
        self.volume_label.setStyleSheet("color: white")
        self.volume_label.setFixedWidth(40)

        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider, 1)
        volume_layout.addWidget(self.volume_label)
        control_layout.addLayout(volume_layout)

        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # =========== 状态栏 ===========
        self.status_bar = QStatusBar()
        self.status_bar.showMessage("就绪")
        main_layout.addWidget(self.status_bar)

    def connect_signals(self):
        """连接信号和槽"""
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.player.stateChanged.connect(self.on_player_state_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)

        # 设置初始音量
        self.set_volume(self.volume_slider.value())

    def upload_music(self):
        """上传MP3文件"""
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("选择MP3文件")
        file_dialog.setNameFilter("MP3文件 (*.mp3)")
        file_dialog.setFileMode(QFileDialog.ExistingFiles)

        if file_dialog.exec_():
            files = file_dialog.selectedFiles()
            for file_path in files:
                if self.save_music_file(file_path):
                    self.status_bar.showMessage(f"成功上传: {os.path.basename(file_path)}", 3000)

            # 刷新列表
            self.load_saved_music()

    def save_music_file(self, source_path):
        """保存音乐文件到本地目录"""
        try:
            if not os.path.exists(source_path):
                self.show_message("错误", "文件不存在！")
                return False

            # 检查文件大小（限制100MB）
            file_size = os.path.getsize(source_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                self.show_message("错误", "文件过大！请选择小于100MB的文件")
                return False

            # 获取文件名和创建目标路径
            filename = os.path.basename(source_path)
            target_path = os.path.join(self.music_dir, filename)

            # 处理重名文件
            counter = 1
            name, ext = os.path.splitext(filename)
            while os.path.exists(target_path):
                new_filename = f"{name}_{counter}{ext}"
                target_path = os.path.join(self.music_dir, new_filename)
                counter += 1

            # 复制文件
            shutil.copy2(source_path, target_path)

            # 添加到配置
            self.add_to_config(target_path)

            # 更新上传标签
            self.upload_label.setText(f"已选择: {os.path.basename(target_path)}")

            return True

        except Exception as e:
            self.show_message("错误", f"保存文件时出错: {str(e)}")
            return False

    def add_to_config(self, file_path):
        """添加歌曲到配置文件"""
        try:
            # 读取MP3元数据
            audiofile = eyed3.load(file_path)
            song_info = {
                "path": file_path,
                "filename": os.path.basename(file_path),
                "added_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "title": audiofile.tag.title if audiofile.tag and audiofile.tag.title else os.path.basename(file_path),
                "artist": audiofile.tag.artist if audiofile.tag and audiofile.tag.artist else "未知艺术家",
                "album": audiofile.tag.album if audiofile.tag and audiofile.tag.album else "未知专辑",
                "duration": int(audiofile.info.time_secs) if audiofile.info else 0
            }

            # 加载现有配置
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {"songs": []}

            # 检查是否已存在
            existing_songs = [s for s in config["songs"] if s["path"] == file_path]
            if not existing_songs:
                config["songs"].append(song_info)

                # 保存配置
                with open(self.config_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"添加配置时出错: {e}")
            return False

    def load_saved_music(self):
        """加载保存的音乐"""
        try:
            self.music_list.clear()
            self.song_list = []

            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                for song in config["songs"]:
                    # 检查文件是否存在
                    if os.path.exists(song["path"]):
                        self.song_list.append(song)

                        # 添加到列表控件
                        item_text = f"{song['title']} - {song['artist']}"
                        if song.get('duration', 0) > 0:
                            duration_str = self.format_duration(song['duration'])
                            item_text += f" ({duration_str})"

                        item = QListWidgetItem(item_text)
                        item.setData(Qt.UserRole, len(self.song_list) - 1)  # 存储索引
                        self.music_list.addItem(item)

            # 更新状态
            count = len(self.song_list)
            self.status_bar.showMessage(f"已加载 {count} 首歌曲", 3000)

            if count == 0:
                self.music_list.addItem("🎵 音乐库为空，请上传MP3文件")

        except Exception as e:
            print(f"加载音乐时出错: {e}")
            self.music_list.addItem("⚠️ 加载音乐列表时出错")

    def on_song_selected(self):
        """歌曲被选中时触发"""
        selected_items = self.music_list.selectedItems()
        if selected_items:
            self.delete_btn.setEnabled(True)

            # 获取选中歌曲的索引
            item = selected_items[0]
            song_index = item.data(Qt.UserRole)

            if song_index is not None and 0 <= song_index < len(self.song_list):
                # 播放选中的歌曲
                self.play_song(song_index)
        else:
            self.delete_btn.setEnabled(False)

    def play_song(self, index):
        """播放指定索引的歌曲"""
        if 0 <= index < len(self.song_list):
            song = self.song_list[index]

            # 设置当前歌曲
            self.current_index = index
            self.current_song = song
            self.current_song_path = song["path"]

            # 更新播放列表
            self.playlist.clear()
            for s in self.song_list:
                media = QMediaContent(QUrl.fromLocalFile(s["path"]))
                self.playlist.addMedia(media)

            # 设置当前播放位置
            self.playlist.setCurrentIndex(index)

            # 更新UI显示
            self.update_song_info()

            # 播放
            self.player.play()

    def update_song_info(self):
        """更新歌曲信息显示"""
        if self.current_song:
            info = f"🎶 {self.current_song['title']} - {self.current_song['artist']}"
            if self.current_song.get('album'):
                info += f" | 💿 {self.current_song['album']}"
            self.song_info_label.setText(info)

    def toggle_play(self):
        """切换播放/暂停状态"""
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_btn.setText("▶")
        else:
            if self.current_song:
                self.player.play()
                self.play_btn.setText("⏸")
            else:
                # 如果没有当前歌曲，尝试播放第一首
                if self.song_list:
                    self.play_song(0)

    def stop_playback(self):
        """停止播放"""
        self.player.stop()
        self.play_btn.setText("▶")
        self.progress_slider.setValue(0)
        self.time_label.setText("00:00")

    def play_previous(self):
        """播放上一首"""
        if self.song_list:
            new_index = (self.current_index - 1) % len(self.song_list)
            self.play_song(new_index)

    def play_next(self):
        """播放下一首"""
        if self.song_list:
            new_index = (self.current_index + 1) % len(self.song_list)
            self.play_song(new_index)

    def set_volume(self, value):
        """设置音量"""
        self.player.setVolume(value)
        self.volume_label.setText(f"{value}%")

    def update_position(self, position):
        """更新播放位置"""
        if self.player.duration() > 0:
            # 更新进度条
            progress = int((position / self.player.duration()) * 100)
            self.progress_slider.setValue(progress)

            # 更新时间标签
            self.time_label.setText(self.format_milliseconds(position))

    def update_duration(self, duration):
        """更新总时长"""
        if duration > 0:
            self.duration_label.setText(self.format_milliseconds(duration))
        else:
            self.duration_label.setText("00:00")

    def seek_position(self, position):
        """跳转到指定位置"""
        if self.player.duration() > 0:
            new_position = int((position / 100) * self.player.duration())
            self.player.setPosition(new_position)

    def on_player_state_changed(self, state):
        """播放器状态改变"""
        if state == QMediaPlayer.PlayingState:
            self.play_btn.setText("⏸")
        elif state == QMediaPlayer.PausedState:
            self.play_btn.setText("▶")
        elif state == QMediaPlayer.StoppedState:
            self.play_btn.setText("▶")

    def on_media_status_changed(self, status):
        """媒体状态改变"""
        # 当一首歌播放完毕时，自动播放下一首
        if status == QMediaPlayer.EndOfMedia:
            self.play_next()

    def delete_selected_song(self):
        """删除选中的歌曲"""
        selected_items = self.music_list.selectedItems()
        if not selected_items:
            return

        item = selected_items[0]
        song_index = item.data(Qt.UserRole)

        if song_index is None or song_index >= len(self.song_list):
            return

        song = self.song_list[song_index]

        # 确认对话框
        reply = QMessageBox.question(
            self, '确认删除',
            f'确定要删除 "{song["title"]}" 吗？\n文件也会从本地删除！',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # 从文件系统中删除
                if os.path.exists(song["path"]):
                    os.remove(song["path"])

                # 从配置文件中删除
                if os.path.exists(self.config_file):
                    with open(self.config_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    # 过滤掉要删除的歌曲
                    config["songs"] = [s for s in config["songs"] if s["path"] != song["path"]]

                    with open(self.config_file, 'w', encoding='utf-8') as f:
                        json.dump(config, f, ensure_ascii=False, indent=2)

                # 停止播放（如果正在播放这首）
                if self.current_index == song_index:
                    self.stop_playback()
                    self.current_song = None
                    self.current_index = -1

                # 刷新列表
                self.load_saved_music()

                self.status_bar.showMessage(f"已删除: {song['title']}", 3000)

            except Exception as e:
                self.show_message("错误", f"删除文件时出错: {str(e)}")

    def format_milliseconds(self, ms):
        """将毫秒转换为分钟:秒格式"""
        seconds = int(ms / 1000)
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def format_duration(self, seconds):
        """将秒转换为分钟:秒格式"""
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def show_message(self, title, message):
        """显示消息对话框"""
        QMessageBox.information(self, title, message)

    def closeEvent(self, event):
        """窗口关闭事件"""
        # 停止播放
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.stop()
        event.accept()


# ==================== 主函数（用于独立测试） ====================
def main():
    """独立测试函数"""
    app = QApplication(sys.argv)

    # 设置应用样式
    app.setStyle('Fusion')

    # 检查依赖
    try:
        import eyed3
    except ImportError:
        print("请安装eyed3库: pip install eyed3")

        # 创建简单对话框
        dialog = QMessageBox()
        dialog.setWindowTitle("缺少依赖")
        dialog.setText("需要安装eyed3库来读取MP3元数据")
        dialog.setInformativeText("请在命令行中运行: pip install eyed3")
        dialog.exec_()
        return

    # 创建并显示窗口
    window = MusicPage(w=1000, h=800)
    window.setWindowTitle("🎵 个人音乐播放器")
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()