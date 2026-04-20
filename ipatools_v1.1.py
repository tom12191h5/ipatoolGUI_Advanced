import sys
import json
import re
import subprocess
from pathlib import Path
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QLabel, QHeaderView, QMessageBox,
    QFileDialog, QProgressBar
)
from PyQt5.QtCore import QThread, pyqtSignal, QRunnable, QObject, QThreadPool

# ---------------- 工具函数（安全增强） ----------------
def clean_ansi(text: str) -> str:
    """移除 ANSI 转义序列"""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def is_valid_bundle_id(bundle_id: str) -> bool:
    """严格验证 Bundle ID 格式（反向域名风格）"""
    if not bundle_id or len(bundle_id) > 255:
        return False
    # 允许字母、数字、点、连字符，且必须包含至少一个点
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9.-]*\.[a-zA-Z0-9.-]+$'
    return bool(re.match(pattern, bundle_id))


def is_valid_keyword(keyword: str) -> bool:
    """搜索关键词安全验证（长度 + 字符白名单）"""
    if not keyword or len(keyword) > 100:
        return False
    # 只允许常见安全字符
    return bool(re.match(r'^[a-zA-Z0-9\u4e00-\u9fff\s\.\-\_\(\)]+$', keyword))


def is_safe_filename(name: str) -> bool:
    """文件名安全检查"""
    if not name or len(name) > 200:
        return False
    # 禁止危险字符
    dangerous = r'[\\/:*?"<>|]'
    return not re.search(dangerous, name)


def run_command(cmd_list: list, timeout: int = 180) -> tuple:
    """安全执行外部命令（列表形式，严格无 shell=True）"""
    try:
        result = subprocess.run(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timeout"
    except FileNotFoundError:
        return -1, "", "ipatool 未找到。请确保已安装 ipatool 并添加到 PATH。"
    except Exception as e:
        return -1, "", f"执行命令时发生意外错误: {str(e)[:100]}"


def safe_json_extract(pattern: str, text: str, max_length: int = 500000):
    """安全提取 JSON，防止 ReDoS 和过大输入"""
    if len(text) > max_length:
        text = text[:max_length]
    try:
        match = re.search(pattern, text, re.S | re.IGNORECASE)
        if not match:
            return None
        json_str = match.group(1)
        # 额外长度限制
        if len(json_str) > max_length:
            json_str = json_str[:max_length]
        return json.loads(json_str)
    except (json.JSONDecodeError, Exception):
        return None


# ---------------- 信号定义 ----------------
class VersionSignals(QObject):
    result = pyqtSignal(int, str, str, str)


# ---------------- 单个版本查询任务 ----------------
class VersionTask(QRunnable):
    def __init__(self, row: int, bundle_id: str, version_id: str):
        super().__init__()
        self.row = row
        self.bundle_id = bundle_id.strip()
        self.version_id = version_id.strip()
        self.signals = VersionSignals()

    def run(self):
        try:
            if not is_valid_bundle_id(self.bundle_id):
                self.signals.result.emit(self.row, "Invalid BundleID", self.version_id, "-")
                return

            cmd = [
                "ipatool", "get-version-metadata",
                "--bundle-identifier", self.bundle_id,
                "--external-version-id", self.version_id
            ]
            code, out, err = run_command(cmd)
            output = clean_ansi(out + err)

            m = re.search(
                r'displayVersion=([^\s]+)\s+externalVersionID=(\d+)\s+releaseDate=([^\s]+)',
                output
            )
            if m:
                self.signals.result.emit(self.row, m.group(1), m.group(2), m.group(3))
            else:
                self.signals.result.emit(self.row, "Unknown", self.version_id, "-")
        except Exception:
            self.signals.result.emit(self.row, "Error", self.version_id, "-")


# ---------------- 通用命令线程 ----------------
class CommandRunner(QThread):
    output = pyqtSignal(str)
    finished = pyqtSignal(int, str)

    def __init__(self, cmd_list: list):
        super().__init__()
        self.cmd_list = cmd_list  # 必须是列表

    def run(self):
        try:
            process = subprocess.Popen(
                self.cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            full_output = ""
            for line in iter(process.stdout.readline, ''):
                clean_line = clean_ansi(line)
                self.output.emit(clean_line)
                full_output += clean_line

            process.wait()
            self.finished.emit(process.returncode, full_output)
        except Exception as e:
            self.finished.emit(-1, f"Error: {str(e)[:200]}")


# ---------------- 主界面 ----------------
class IpaToolApp(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(8)
        self.threads = []  # 管理 CommandRunner 线程
        self.initUI()

    def initUI(self):
        self.setWindowTitle('IPATool GUI（安全增强版）')
        self.setGeometry(100, 100, 1100, 900)
        main_layout = QVBoxLayout()

        # ---------- 搜索 ----------
        main_layout.addWidget(QLabel("<b>搜索应用</b>"))
        h_layout1 = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入 App 名称（关键词）")
        self.search_input.setMaxLength(100)
        self.search_btn = QPushButton("搜索")
        self.search_btn.clicked.connect(self.run_search)
        h_layout1.addWidget(self.search_input)
        h_layout1.addWidget(self.search_btn)
        main_layout.addLayout(h_layout1)

        self.search_table = QTableWidget()
        self.search_table.setColumnCount(5)
        self.search_table.setHorizontalHeaderLabels(["Name", "BundleID", "ID", "Price", "Version"])
        self.search_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.search_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.search_table.itemClicked.connect(self.on_app_selected)
        main_layout.addWidget(self.search_table)

        # ---------- 版本 ----------
        main_layout.addWidget(QLabel("<b>历史版本</b>"))
        h_layout2 = QHBoxLayout()
        self.bundle_input = QLineEdit()
        self.bundle_input.setPlaceholderText("Bundle ID (e.g. com.example.app)")
        self.bundle_input.setMaxLength(255)
        self.limit_input = QLineEdit("10")
        self.limit_input.setPlaceholderText("数量 (1-50)")
        self.limit_input.setFixedWidth(120)
        self.version_btn = QPushButton("获取版本")
        self.version_btn.clicked.connect(self.run_versions)
        h_layout2.addWidget(self.bundle_input)
        h_layout2.addWidget(self.limit_input)
        h_layout2.addWidget(self.version_btn)
        main_layout.addLayout(h_layout2)

        self.version_table = QTableWidget()
        self.version_table.setColumnCount(3)
        self.version_table.setHorizontalHeaderLabels(["Version", "ExternalID", "Date"])
        self.version_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        main_layout.addWidget(self.version_table)

        # ---------- 下载 ----------
        self.download_btn = QPushButton("下载 IPA")
        self.download_btn.clicked.connect(self.run_download)
        main_layout.addWidget(self.download_btn)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        main_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("待机")
        main_layout.addWidget(self.progress_label)

        self.setLayout(main_layout)

    def on_app_selected(self, item):
        try:
            row = item.row()
            bundle_item = self.search_table.item(row, 1)
            if bundle_item and bundle_item.text():
                self.bundle_input.setText(bundle_item.text().strip())
        except Exception:
            QMessageBox.warning(self, "错误", "读取 BundleID 失败")

    def set_ui_enabled(self, enabled: bool):
        self.search_btn.setEnabled(enabled)
        self.version_btn.setEnabled(enabled)
        self.download_btn.setEnabled(enabled)

    # ---------- 搜索 ----------
    def run_search(self):
        keyword = self.search_input.text().strip()
        if not keyword or not is_valid_keyword(keyword):
            QMessageBox.warning(self, "提示", "请输入有效的搜索关键词（长度≤100，仅允许安全字符）")
            return

        self.set_ui_enabled(False)
        cmd = ["ipatool", "search", keyword, "--limit", "5"]
        thread = CommandRunner(cmd)
        self.threads.append(thread)
        thread.finished.connect(self.handle_search)
        thread.finished.connect(lambda *_: self.cleanup_thread(thread))
        thread.start()

    def handle_search(self, code: int, output: str):
        self.set_ui_enabled(True)
        self.search_table.setRowCount(0)
        clean_text = clean_ansi(output)
        apps = safe_json_extract(r'apps\s*=\s*(\[.*?\])', clean_text)
        if not apps:
            QMessageBox.warning(self, "错误", "搜索结果解析失败或无结果")
            return
        for app in apps:
            row = self.search_table.rowCount()
            self.search_table.insertRow(row)
            self.search_table.setItem(row, 0, QTableWidgetItem(str(app.get('name', ''))))
            self.search_table.setItem(row, 1, QTableWidgetItem(str(app.get('bundleID', ''))))
            self.search_table.setItem(row, 2, QTableWidgetItem(str(app.get('id', ''))))
            self.search_table.setItem(row, 3, QTableWidgetItem(str(app.get('price', ''))))
            self.search_table.setItem(row, 4, QTableWidgetItem(str(app.get('version', ''))))

    # ---------- 版本 ----------
    def run_versions(self):
        bundle_id = self.bundle_input.text().strip()
        if not bundle_id or not is_valid_bundle_id(bundle_id):
            QMessageBox.warning(self, "提示", "请输入有效的 Bundle ID")
            return

        self.set_ui_enabled(False)
        cmd = ["ipatool", "list-versions", "--bundle-identifier", bundle_id]
        thread = CommandRunner(cmd)
        self.threads.append(thread)
        thread.finished.connect(self.handle_versions)
        thread.finished.connect(lambda *_: self.cleanup_thread(thread))
        thread.start()

    def handle_versions(self, code: int, output: str):
        self.set_ui_enabled(True)
        self.version_table.setRowCount(0)
        clean_text = clean_ansi(output)
        ids = safe_json_extract(r'externalVersionIdentifiers\s*=\s*(\[.*?\])', clean_text)
        if not ids:
            QMessageBox.warning(self, "错误", "获取版本列表失败")
            return

        try:
            limit = max(1, min(50, int(self.limit_input.text().strip() or 10)))
        except ValueError:
            limit = 10

        ids = list(reversed(ids))[:limit]
        for row, vid in enumerate(ids):
            self.version_table.insertRow(row)
            self.version_table.setItem(row, 0, QTableWidgetItem("加载中..."))
            self.version_table.setItem(row, 1, QTableWidgetItem(str(vid)))
            self.version_table.setItem(row, 2, QTableWidgetItem("-"))

            task = VersionTask(row, self.bundle_input.text().strip(), str(vid))
            task.signals.result.connect(self.update_version)
            self.threadpool.start(task)

    def update_version(self, row: int, version: str, vid: str, date: str):
        self.version_table.setItem(row, 0, QTableWidgetItem(version))
        self.version_table.setItem(row, 1, QTableWidgetItem(vid))
        self.version_table.setItem(row, 2, QTableWidgetItem(date))

    # ---------- 下载 ----------
    def run_download(self):
        row = self.version_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请先在历史版本中选择一个版本")
            return

        bundle_id = self.bundle_input.text().strip()
        vid_item = self.version_table.item(row, 1)
        if not vid_item:
            return
        vid = vid_item.text().strip()

        if not is_valid_bundle_id(bundle_id):
            QMessageBox.warning(self, "错误", "Bundle ID 无效")
            return

        suggested_name = f"{bundle_id}_{vid}.ipa"
        if not is_safe_filename(suggested_name):
            QMessageBox.warning(self, "错误", "生成的默认文件名包含非法字符")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存 IPA 文件", suggested_name,
            "IPA Files (*.ipa);;All Files (*)"
        )
        if not file_path:
            return

        # 严格路径安全检查
        try:
            path_obj = Path(file_path).resolve(strict=False)
            if ".." in str(path_obj) or path_obj.is_symlink():
                raise ValueError("路径包含非法遍历或符号链接")
            # 可选：限制保存目录（例如仅允许用户主目录或桌面）
            # home = Path.home()
            # if not str(path_obj).startswith(str(home)):
            #     raise ValueError("仅允许保存到用户目录")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存路径无效: {str(e)[:100]}")
            return

        self.set_ui_enabled(False)
        cmd = [
            "ipatool", "download",
            "--bundle-identifier", bundle_id,
            "--external-version-id", vid,
            "--output", str(path_obj)
        ]
        thread = CommandRunner(cmd)
        self.threads.append(thread)
        thread.output.connect(self.update_progress)
        thread.finished.connect(self.download_done)
        thread.finished.connect(lambda *_: self.cleanup_thread(thread))
        thread.start()

    def update_progress(self, text: str):
        clean_text = clean_ansi(text)
        matches = re.findall(r'(\d{1,3})%', clean_text)
        if matches:
            percent = int(matches[-1])
            self.progress_bar.setValue(percent)
            self.progress_label.setText(f"下载中... {percent}%")

    def download_done(self, code: int, output: str):
        self.set_ui_enabled(True)
        self.progress_bar.setValue(100 if code == 0 else 0)
        self.progress_label.setText("完成" if code == 0 else "失败")
        if code != 0:
            QMessageBox.warning(self, "错误", "下载失败，请检查 ipatool 输出、网络或认证状态")

    def cleanup_thread(self, thread):
        if thread in self.threads:
            self.threads.remove(thread)


# ---------------- 启动 ----------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = IpaToolApp()
    win.show()

    QMessageBox.information(
        win, "重要提醒",
        "1. 请确保已通过 `ipatool auth` 登录有效的 Apple ID（建议使用小号）。\n"
        "2. 本工具仅用于合法用途（如备份自己购买的应用）。\n"
        "3. 下载付费应用可能违反 Apple 服务条款，请自行承担风险。\n\n"
        "安全提示：已强化输入验证与路径保护，建议在可信环境中使用。"
    )
    sys.exit(app.exec_())