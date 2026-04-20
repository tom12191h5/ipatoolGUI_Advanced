import sys
import json
import re
import subprocess
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
                             QLabel, QHeaderView, QMessageBox, QFileDialog,
                             QProgressBar)
from PyQt5.QtCore import QThread, pyqtSignal, QRunnable, QObject, QThreadPool


# ---------------- 工具函数 ----------------
def clean_ansi(text):
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def run_command(cmd_list, timeout=60):
    try:
        result = subprocess.run(
            cmd_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def safe_json_extract(pattern, text):
    try:
        match = re.search(pattern, text, re.S)
        if not match:
            return None
        return json.loads(match.group(1))
    except Exception:
        return None


# ---------------- 信号定义 ----------------
class VersionSignals(QObject):
    result = pyqtSignal(int, str, str, str)


# ---------------- 单个版本查询任务 ----------------
class VersionTask(QRunnable):
    def __init__(self, row, bundle_id, version_id):
        super().__init__()
        self.row = row
        self.bundle_id = bundle_id
        self.version_id = version_id
        self.signals = VersionSignals()

    def run(self):
        try:
            cmd = [
                "ipatool", "get-version-metadata",
                "--bundle-identifier", self.bundle_id,
                "--external-version-id", str(self.version_id)
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
                self.signals.result.emit(self.row, "Unknown", str(self.version_id), "-")
        except Exception:
            self.signals.result.emit(self.row, "Error", str(self.version_id), "-")


# ---------------- 通用命令线程 ----------------
class CommandRunner(QThread):
    output = pyqtSignal(str)
    finished = pyqtSignal(int, str)

    def __init__(self, cmd_list):
        super().__init__()
        self.cmd_list = cmd_list

    def run(self):
        try:
            process = subprocess.Popen(
                self.cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )

            full_output = ""

            for line in iter(process.stdout.readline, ''):
                full_output += line
                self.output.emit(line)

            process.wait()
            self.finished.emit(process.returncode, full_output)

        except Exception as e:
            self.finished.emit(-1, str(e))


# ---------------- 主界面 ----------------
class IpaToolApp(QWidget):
    def __init__(self):
        super().__init__()
        self.threadpool = QThreadPool()
        self.threadpool.setMaxThreadCount(8)
        self.threads = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle('IPATool GUI（增强鲁棒版）')
        self.setGeometry(100, 100, 1000, 900)

        main_layout = QVBoxLayout()

        # ---------- 搜索 ----------
        main_layout.addWidget(QLabel("<b>搜索应用</b>"))

        h_layout1 = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入 App 名称")
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
        self.bundle_input.setPlaceholderText("Bundle ID")

        self.limit_input = QLineEdit()
        self.limit_input.setPlaceholderText("数量(默认10)")
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
        main_layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("待机")
        main_layout.addWidget(self.progress_label)

        self.setLayout(main_layout)

    def on_app_selected(self, item):
        try:
            row = item.row()
            bundle_item = self.search_table.item(row, 1)

            if bundle_item and bundle_item.text():
                self.bundle_input.setText(bundle_item.text())
        except Exception as e:
            QMessageBox.warning(self, "错误", f"读取 BundleID 失败: {e}")

    # ---------- UI 控制 ----------
    def set_ui_enabled(self, enabled):
        self.search_btn.setEnabled(enabled)
        self.version_btn.setEnabled(enabled)
        self.download_btn.setEnabled(enabled)

    # ---------- 搜索 ----------
    def run_search(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            QMessageBox.warning(self, "提示", "请输入关键词")
            return

        self.set_ui_enabled(False)

        cmd = ["ipatool", "search", keyword, "--limit", "5"]
        thread = CommandRunner(cmd)

        self.threads.append(thread)
        thread.finished.connect(self.handle_search)
        thread.finished.connect(lambda *_: self.cleanup_thread(thread))

        thread.start()

    def handle_search(self, code, output):
        self.set_ui_enabled(True)
        self.search_table.setRowCount(0)

        clean_text = clean_ansi(output)
        apps = safe_json_extract(r'apps\s*=\s*(\[.*?\])', clean_text)

        if not apps:
            QMessageBox.warning(self, "错误", "解析失败")
            return

        for app in apps:
            row = self.search_table.rowCount()
            self.search_table.insertRow(row)

            self.search_table.setItem(row, 0, QTableWidgetItem(str(app.get('name'))))
            self.search_table.setItem(row, 1, QTableWidgetItem(str(app.get('bundleID'))))
            self.search_table.setItem(row, 2, QTableWidgetItem(str(app.get('id'))))
            self.search_table.setItem(row, 3, QTableWidgetItem(str(app.get('price'))))
            self.search_table.setItem(row, 4, QTableWidgetItem(str(app.get('version'))))

    # ---------- 版本 ----------
    def run_versions(self):
        bundle_id = self.bundle_input.text().strip()
        if not bundle_id:
            return

        self.set_ui_enabled(False)

        cmd = ["ipatool", "list-versions", "--bundle-identifier", bundle_id]
        thread = CommandRunner(cmd)

        self.threads.append(thread)
        thread.finished.connect(self.handle_versions)
        thread.finished.connect(lambda *_: self.cleanup_thread(thread))

        thread.start()

    def handle_versions(self, code, output):
        self.set_ui_enabled(True)
        self.version_table.setRowCount(0)

        clean_text = clean_ansi(output)
        ids = safe_json_extract(r'externalVersionIdentifiers\s*=\s*(\[.*?\])', clean_text)

        if not ids:
            QMessageBox.warning(self, "错误", "获取版本失败")
            return

        try:
            limit = int(self.limit_input.text())
        except:
            limit = 10

        ids = list(reversed(ids))[:limit]

        for row, vid in enumerate(ids):
            self.version_table.insertRow(row)
            self.version_table.setItem(row, 0, QTableWidgetItem("加载中"))
            self.version_table.setItem(row, 1, QTableWidgetItem(str(vid)))
            self.version_table.setItem(row, 2, QTableWidgetItem("-"))

            task = VersionTask(row, str(self.bundle_input.text()), str(vid))
            task.signals.result.connect(self.update_version)
            self.threadpool.start(task)

    def update_version(self, row, version, vid, date):
        self.version_table.setItem(row, 0, QTableWidgetItem(version))
        self.version_table.setItem(row, 1, QTableWidgetItem(vid))
        self.version_table.setItem(row, 2, QTableWidgetItem(date))

    # ---------- 下载 ----------
    def run_download(self):
        row = self.version_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "提示", "请选择版本")
            return

        bundle_id = self.bundle_input.text()
        vid = self.version_table.item(row, 1).text()

        file_path, _ = QFileDialog.getSaveFileName(self, "保存", f"{bundle_id}.ipa")

        if not file_path:
            return

        self.set_ui_enabled(False)

        cmd = [
            "ipatool", "download",
            "--bundle-identifier", bundle_id,
            "--external-version-id", vid,
            "--output", file_path
        ]

        thread = CommandRunner(cmd)

        self.threads.append(thread)
        thread.output.connect(self.update_progress)
        thread.finished.connect(self.download_done)
        thread.finished.connect(lambda *_: self.cleanup_thread(thread))

        thread.start()

    def update_progress(self, text):
        clean_text = clean_ansi(text)
        matches = re.findall(r'(\d{1,3})%', clean_text)
        if matches:
            percent = int(matches[-1])
            self.progress_bar.setValue(percent)
            self.progress_label.setText(f"{percent}%")

    def download_done(self, code, output):
        self.set_ui_enabled(True)
        self.progress_bar.setValue(100)
        self.progress_label.setText("完成")

        if code != 0:
            QMessageBox.warning(self, "错误", "下载失败")

    def cleanup_thread(self, thread):
        if thread in self.threads:
            self.threads.remove(thread)


# ---------------- 启动 ----------------
if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = IpaToolApp()
    win.show()
    sys.exit(app.exec_())