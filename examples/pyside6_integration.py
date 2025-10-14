#!/usr/bin/env python3
"""
PySide6 百度网盘客户端集成示例
"""

import sys
import json
import base64
import hashlib
from typing import Optional, Dict, Any
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QProgressBar,
    QTabWidget, QTableWidget, QTableWidgetItem, QMessageBox,
    QFileDialog, QGroupBox, QGridLayout, QSpinBox
)
from PySide6.QtCore import QThread, Signal, QTimer, QUrl
from PySide6.QtGui import QPixmap, QFont
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
import requests
import qrcode
from io import BytesIO


class BaiduNetdiskClient:
    """百度网盘API客户端"""
    
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url
        self.user_jwt: Optional[str] = None
        self.baidu_token: Optional[Dict[str, Any]] = None
        self.session = requests.Session()
    
    def login(self, username: str, password: str) -> bool:
        """用户登录"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json={"username": username, "password": password}
            )
            if response.status_code == 200:
                data = response.json()
                self.user_jwt = data.get("access_token")
                return True
            return False
        except Exception as e:
            print(f"登录失败: {e}")
            return False
    
    def register(self, username: str, password: str) -> bool:
        """用户注册"""
        try:
            response = self.session.post(
                f"{self.base_url}/auth/register",
                json={"username": username, "password": password}
            )
            return response.status_code == 200
        except Exception as e:
            print(f"注册失败: {e}")
            return False
    
    def start_qr_auth(self) -> Optional[Dict[str, Any]]:
        """启动扫码授权"""
        if not self.user_jwt:
            return None
        
        try:
            response = self.session.post(
                f"{self.base_url}/oauth/device/start",
                headers={"Authorization": f"Bearer {self.user_jwt}"}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"启动授权失败: {e}")
            return None
    
    def poll_auth_status(self, device_code: str) -> Optional[Dict[str, Any]]:
        """轮询授权状态"""
        if not self.user_jwt:
            return None
        
        try:
            response = self.session.post(
                f"{self.base_url}/oauth/device/poll",
                params={"device_code": device_code},
                headers={"Authorization": f"Bearer {self.user_jwt}"}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"轮询失败: {e}")
            return None
    
    def call_api(self, operation: str, args: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """调用百度网盘API"""
        if not self.user_jwt:
            return None
        
        try:
            response = self.session.post(
                f"{self.base_url}/mcp/user/exec",
                json={"op": operation, "args": args or {}},
                headers={"Authorization": f"Bearer {self.user_jwt}"}
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"API调用失败: {e}")
            return None


class QRCodeWidget(QLabel):
    """二维码显示组件"""
    
    def __init__(self):
        super().__init__()
        self.setFixedSize(300, 300)
        self.setStyleSheet("border: 1px solid gray;")
        self.setText("等待二维码...")
        self.setAlignment(Qt.AlignCenter)
    
    def set_qr_code(self, qr_url: str):
        """设置二维码"""
        try:
            # 生成二维码
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            # 转换为QPixmap
            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            
            pixmap = QPixmap()
            pixmap.loadFromData(buffer.getvalue())
            self.setPixmap(pixmap.scaled(300, 300))
        except Exception as e:
            print(f"生成二维码失败: {e}")
            self.setText("二维码生成失败")


class AuthThread(QThread):
    """授权轮询线程"""
    
    auth_success = Signal(dict)
    auth_failed = Signal(str)
    status_update = Signal(str)
    
    def __init__(self, client: BaiduNetdiskClient, device_code: str):
        super().__init__()
        self.client = client
        self.device_code = device_code
        self.running = True
    
    def run(self):
        """轮询授权状态"""
        max_attempts = 120  # 10分钟
        attempts = 0
        
        while self.running and attempts < max_attempts:
            result = self.client.poll_auth_status(self.device_code)
            
            if result:
                if result.get("status") == "ok":
                    self.auth_success.emit(result.get("data", {}))
                    break
                elif result.get("status") == "error":
                    self.auth_failed.emit(result.get("error", "授权失败"))
                    break
                else:
                    self.status_update.emit("等待用户扫码...")
            
            self.msleep(5000)  # 5秒间隔
            attempts += 1
        
        if attempts >= max_attempts:
            self.auth_failed.emit("授权超时")
    
    def stop(self):
        """停止轮询"""
        self.running = False


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.client = BaiduNetdiskClient()
        self.auth_thread: Optional[AuthThread] = None
        
        self.setWindowTitle("百度网盘客户端")
        self.setGeometry(100, 100, 1000, 700)
        
        self.setup_ui()
        self.setup_connections()
    
    def setup_ui(self):
        """设置UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # 创建标签页
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)
        
        # 登录标签页
        login_tab = self.create_login_tab()
        tab_widget.addTab(login_tab, "登录")
        
        # 文件管理标签页
        file_tab = self.create_file_tab()
        tab_widget.addTab(file_tab, "文件管理")
        
        # 上传标签页
        upload_tab = self.create_upload_tab()
        tab_widget.addTab(upload_tab, "上传")
        
        # 状态栏
        self.status_label = QLabel("未登录")
        self.statusBar().addWidget(self.status_label)
    
    def create_login_tab(self) -> QWidget:
        """创建登录标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 登录区域
        login_group = QGroupBox("用户登录")
        login_layout = QGridLayout(login_group)
        
        login_layout.addWidget(QLabel("用户名:"), 0, 0)
        self.username_edit = QLineEdit()
        self.username_edit.setText("testuser")
        login_layout.addWidget(self.username_edit, 0, 1)
        
        login_layout.addWidget(QLabel("密码:"), 1, 0)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setText("testpass")
        login_layout.addWidget(self.password_edit, 1, 1)
        
        self.login_btn = QPushButton("登录")
        self.register_btn = QPushButton("注册")
        login_layout.addWidget(self.login_btn, 2, 0)
        login_layout.addWidget(self.register_btn, 2, 1)
        
        layout.addWidget(login_group)
        
        # 授权区域
        auth_group = QGroupBox("百度网盘授权")
        auth_layout = QVBoxLayout(auth_group)
        
        self.qr_widget = QRCodeWidget()
        auth_layout.addWidget(self.qr_widget)
        
        self.start_auth_btn = QPushButton("开始扫码授权")
        self.start_auth_btn.setEnabled(False)
        auth_layout.addWidget(self.start_auth_btn)
        
        self.auth_status_label = QLabel("请先登录")
        auth_layout.addWidget(self.auth_status_label)
        
        layout.addWidget(auth_group)
        
        return widget
    
    def create_file_tab(self) -> QWidget:
        """创建文件管理标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 操作按钮
        button_layout = QHBoxLayout()
        
        self.refresh_btn = QPushButton("刷新")
        self.mkdir_btn = QPushButton("新建文件夹")
        self.delete_btn = QPushButton("删除")
        self.download_btn = QPushButton("下载")
        
        button_layout.addWidget(self.refresh_btn)
        button_layout.addWidget(self.mkdir_btn)
        button_layout.addWidget(self.delete_btn)
        button_layout.addWidget(self.download_btn)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # 文件列表
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(4)
        self.file_table.setHorizontalHeaderLabels(["名称", "大小", "修改时间", "类型"])
        layout.addWidget(self.file_table)
        
        return widget
    
    def create_upload_tab(self) -> QWidget:
        """创建上传标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 上传区域
        upload_group = QGroupBox("文件上传")
        upload_layout = QVBoxLayout(upload_group)
        
        # 文件选择
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择要上传的文件...")
        self.browse_btn = QPushButton("浏览")
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(self.browse_btn)
        upload_layout.addLayout(file_layout)
        
        # 上传设置
        settings_layout = QGridLayout()
        settings_layout.addWidget(QLabel("远程路径:"), 0, 0)
        self.remote_path_edit = QLineEdit("/")
        settings_layout.addWidget(self.remote_path_edit, 0, 1)
        
        settings_layout.addWidget(QLabel("并发数:"), 1, 0)
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(3)
        settings_layout.addWidget(self.concurrent_spin, 1, 1)
        
        upload_layout.addLayout(settings_layout)
        
        # 上传按钮
        self.upload_btn = QPushButton("开始上传")
        upload_layout.addWidget(self.upload_btn)
        
        # 进度条
        self.progress_bar = QProgressBar()
        upload_layout.addWidget(self.progress_bar)
        
        # 日志
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)
        upload_layout.addWidget(self.log_text)
        
        layout.addWidget(upload_group)
        
        return widget
    
    def setup_connections(self):
        """设置信号连接"""
        self.login_btn.clicked.connect(self.login)
        self.register_btn.clicked.connect(self.register)
        self.start_auth_btn.clicked.connect(self.start_auth)
        self.refresh_btn.clicked.connect(self.refresh_files)
        self.browse_btn.clicked.connect(self.browse_file)
        self.upload_btn.clicked.connect(self.upload_file)
    
    def login(self):
        """用户登录"""
        username = self.username_edit.text()
        password = self.password_edit.text()
        
        if not username or not password:
            QMessageBox.warning(self, "警告", "请输入用户名和密码")
            return
        
        if self.client.login(username, password):
            self.status_label.setText(f"已登录: {username}")
            self.start_auth_btn.setEnabled(True)
            self.auth_status_label.setText("登录成功，可以开始授权")
            QMessageBox.information(self, "成功", "登录成功！")
        else:
            QMessageBox.critical(self, "错误", "登录失败，请检查用户名和密码")
    
    def register(self):
        """用户注册"""
        username = self.username_edit.text()
        password = self.password_edit.text()
        
        if not username or not password:
            QMessageBox.warning(self, "警告", "请输入用户名和密码")
            return
        
        if self.client.register(username, password):
            QMessageBox.information(self, "成功", "注册成功！")
        else:
            QMessageBox.critical(self, "错误", "注册失败，用户名可能已存在")
    
    def start_auth(self):
        """开始扫码授权"""
        auth_data = self.client.start_qr_auth()
        if not auth_data:
            QMessageBox.critical(self, "错误", "启动授权失败")
            return
        
        # 显示二维码
        self.qr_widget.set_qr_code(auth_data.get("qrcode_url", ""))
        self.auth_status_label.setText(f"用户码: {auth_data.get('user_code', '')}")
        
        # 开始轮询
        device_code = auth_data.get("device_code")
        if device_code:
            self.auth_thread = AuthThread(self.client, device_code)
            self.auth_thread.auth_success.connect(self.auth_success)
            self.auth_thread.auth_failed.connect(self.auth_failed)
            self.auth_thread.status_update.connect(self.auth_status_label.setText)
            self.auth_thread.start()
    
    def auth_success(self, token_data):
        """授权成功"""
        self.client.baidu_token = token_data
        self.auth_status_label.setText("授权成功！")
        QMessageBox.information(self, "成功", "百度网盘授权成功！")
        
        # 刷新文件列表
        self.refresh_files()
    
    def auth_failed(self, error_msg):
        """授权失败"""
        self.auth_status_label.setText(f"授权失败: {error_msg}")
        QMessageBox.critical(self, "错误", f"授权失败: {error_msg}")
    
    def refresh_files(self):
        """刷新文件列表"""
        if not self.client.user_jwt:
            QMessageBox.warning(self, "警告", "请先登录")
            return
        
        result = self.client.call_api("list_files", {"dir": "/", "limit": 100})
        if result and result.get("status") == "ok":
            data = result.get("data", {})
            files = data.get("list", [])
            
            self.file_table.setRowCount(len(files))
            for i, file_info in enumerate(files):
                self.file_table.setItem(i, 0, QTableWidgetItem(file_info.get("server_filename", "")))
                self.file_table.setItem(i, 1, QTableWidgetItem(str(file_info.get("size", 0))))
                self.file_table.setItem(i, 2, QTableWidgetItem(str(file_info.get("mtime", ""))))
                self.file_table.setItem(i, 3, QTableWidgetItem("文件夹" if file_info.get("isdir") else "文件"))
        else:
            QMessageBox.critical(self, "错误", "获取文件列表失败")
    
    def browse_file(self):
        """浏览文件"""
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "所有文件 (*)")
        if file_path:
            self.file_path_edit.setText(file_path)
    
    def upload_file(self):
        """上传文件"""
        file_path = self.file_path_edit.text()
        remote_path = self.remote_path_edit.text()
        
        if not file_path:
            QMessageBox.warning(self, "警告", "请选择要上传的文件")
            return
        
        if not self.client.user_jwt:
            QMessageBox.warning(self, "警告", "请先登录并授权")
            return
        
        # 这里可以实现文件上传逻辑
        self.log_text.append(f"开始上传: {file_path} -> {remote_path}")
        QMessageBox.information(self, "提示", "上传功能需要进一步实现")


def main():
    """主函数"""
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle('Fusion')
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
