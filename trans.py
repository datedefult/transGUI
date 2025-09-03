"""
GUI 翻译工具
"""
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QFileDialog, QRadioButton,
                             QButtonGroup, QCheckBox, QGroupBox, QTextEdit, QProgressBar)
from dotenv import load_dotenv

# 常量配置
DEFAULT_TIMEOUT = 30

REQUEST_INTERVAL = 0.1

TARGET_LANGUAGES = {
    "EN": "英语",
    "JA": "日语",
    "DE": "德语",
    "ES": "西班牙语",
    "FR": "法语",
    "IT": "意大利语",
    "PT": "葡萄牙语",
    "NL": "荷兰语",
    "RU": "俄语",
    "PL": "波兰语",
    "UK": "乌克兰语",
    "RO": "罗马尼亚语",
    "CS": "捷克语",
    "HU": "匈牙利语",
    "EL": "希腊语",
    "SV": "瑞典语",
    "DA": "丹麦语",
    "FI": "芬兰语",
    "TR": "土耳其语",
    "KO": "韩语",
    "ID": "印度尼西亚语",
    "HI": "印地语"
}




class APIConfig:
    """API配置加载器"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """从.env文件加载配置"""
        env_path = self.get_resource_path(".env")
        load_dotenv(env_path)
        self.API_KEY = os.getenv("TRANSLATION_API_KEY")
        self.API_URL = os.getenv("TRANSLATION_API_URL")
        self.MAX_CONCURRENT_REQUESTS = os.getenv("MAX_CONCURRENT_REQUESTS")

        if not self.API_KEY or not self.API_URL:
            raise ValueError("未找到API配置，请检查.env文件")
    @classmethod
    def get_resource_path(cls, relative_path):
        """ 获取资源文件的绝对路径（兼容开发环境和打包环境） """
        base_path = os.path.dirname(os.path.abspath(__file__))

        # 尝试多个可能位置
        search_paths = [
            Path(base_path) / relative_path,  # 直接路径
            Path(base_path) / "_internal" / relative_path  # _internal子目录
        ]

        for path in search_paths:
            if path.exists():
                return str(path)

        raise FileNotFoundError(f"找不到资源文件: {relative_path}")

    @property
    def key(self) -> str:
        return self.API_KEY

    @property
    def url(self) -> str:
        return self.API_URL

    @property
    def workers(self) -> str:
        return self.MAX_CONCURRENT_REQUESTS

def get_api_config() -> APIConfig:
    """获取API配置单例"""
    return APIConfig()


import asyncio
import time
import aiohttp
import pandas as pd
from PyQt5.QtCore import QThread, pyqtSignal


# 定义提取括号内容的函数
def extract_bracket_text(col_name):
    match = re.search(r'\((.*?)\)', col_name)  # 正则匹配括号内容
    return match.group(1) if match else ""     # 返回括号内文本（若无括号则返回空字符串）


class TranslationThread(QThread):
    """异步翻译线程（支持真正并发）"""
    progress_updated = pyqtSignal(int, str)  # (进度百分比, 日志消息)
    finished = pyqtSignal(bool, str)  # (是否成功, 结果消息)

    def __init__(self, params):
        super().__init__()
        self.api_config = get_api_config()  # 加载配置
        self.API_KEY = self.api_config.key
        self.API_URL = self.api_config.url
        self.MAX_CONCURRENT_REQUESTS = int(self.api_config.workers)

        self.params = params
        self._is_running = True
        self.semaphore = asyncio.Semaphore(self.MAX_CONCURRENT_REQUESTS)  # 并发控制
        self.request_interval = REQUEST_INTERVAL
        self.last_request_time = 0
        self.completed_tasks = 0  # 将计数器移到类成员变量

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._run_translation())
        except Exception as e:
            self.progress_updated.emit(0, f"严重错误: {str(e)}")
            self.finished.emit(False, str(e))
        finally:
            if 'loop' in locals():
                loop.close()

    async def _run_translation(self):
        """执行翻译的核心异步函数"""
        input_path = self.params['input_path']
        output_path = self.params['output_path']
        text_column = self.params['text_column']
        source_lang = self.params['source_lang']
        target_langs = self.params['target_langs']

        # 1. 读取输入文件
        try:
            df = pd.read_excel(input_path)
            self.progress_updated.emit(5, f"成功读取文件: {os.path.basename(input_path)}")
        except Exception as e:
            self.progress_updated.emit(0, f"文件读取失败: {str(e)}")
            self.finished.emit(False, f"文件错误: {str(e)}")
            return

        # 2. 准备结果DataFrame
        result_df = df.copy()
        total_tasks = len(df) * len(target_langs)
        self.completed_tasks = 0  # 重置计数器

        # 3. 创建HTTP会话并执行并发任务
        async with aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.API_KEY}"},
                timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT)
        ) as session:
            # 准备所有任务
            tasks = []
            for row_idx, row in df.iterrows():
                text = row[text_column]
                for lang_code in target_langs:
                    task = self._create_translation_task(
                        session, result_df, row_idx, text,
                        source_lang, lang_code, total_tasks
                    )
                    tasks.append(task)
                    if not self._is_running:
                        raise Exception("用户取消操作")

            # 并发执行所有任务
            await asyncio.gather(*tasks, return_exceptions=True)

        # 4. 保存结果
        try:
            first_col = result_df.columns[0]
            other_cols = sorted(result_df.columns[1:], key = lambda x: extract_bracket_text(x))
            
            result_df = result_df[[first_col] + other_cols]
            result_df.to_excel(output_path, index=False)
            self.progress_updated.emit(100, f"翻译完成! 结果已保存到: {os.path.basename(output_path)}")
            self.finished.emit(True, output_path)
        except Exception as e:
            self.finished.emit(False, f"文件保存失败: {str(e)}")

    def _create_translation_task(self, session, result_df, row_idx, text, source_lang, lang_code, total_tasks):
        """创建单个翻译任务"""

        async def task():
            lang_name = TARGET_LANGUAGES[lang_code]
            try:
                # 执行翻译
                translated = await self._call_translation_api(
                    session, text, source_lang, lang_code
                )

                # 更新结果
                result_df.at[row_idx, f"{lang_name}({lang_code})"] = translated

                # 更新进度（使用类成员变量）
                self.completed_tasks += 1
                progress = int((self.completed_tasks / total_tasks) * 100)
                self.progress_updated.emit(
                    progress,
                    f"进度: {row_idx + 1}/{len(result_df)}行 | {lang_name} | 已完成: {progress}%"
                )
            except Exception as e:
                result_df.at[row_idx, f"{lang_name}({lang_code})"] = f"[ERROR]"
                self.progress_updated.emit(
                    int((self.completed_tasks / total_tasks) * 100),
                    f"错误: 行{row_idx + 1} {lang_name}: {str(e)[:100]}"
                )

        return task()

    async def _call_translation_api(self, session, text, source_lang, target_lang):
        """调用翻译API（带并发控制和速率限制）"""
        async with self.semaphore:  # 并发控制
            # 速率限制
            elapsed = time.time() - self.last_request_time
            if elapsed < self.request_interval:
                await asyncio.sleep(self.request_interval - elapsed)

            self.last_request_time = time.time()
            
            if target_lang == 'UK':
                target_lang = "乌克兰语"
            
            payload = {
                "inputs": {
                    "source_lang": source_lang,
                    "target_lang": target_lang,
                    "query": text
                },
                "response_mode": "blocking",
                "user": "pyqt_translation_tool_thread"
            }

            try:
                async with session.post(self.API_URL, json=payload) as resp:
                    if resp.status != 200:
                        error = await resp.json()
                        raise ValueError(f"API错误({resp.status}): {error.get('message', '未知错误')}")
                    return await self._parse_response(resp)
            except Exception as e:
                raise ValueError(f"请求失败: {str(e)}")

    async def _parse_response(self, resp):
        """解析API响应"""
        data = await resp.json()
        return data.get("data", {}).get("outputs", {}).get("text", "")

    def stop(self):
        """停止翻译任务"""
        self._is_running = False

class TranslationApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("多语言文档翻译工具")
        self.setGeometry(100, 100, 800, 600)
        self.thread = None
        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()

        # 文件选择区域
        file_group = QGroupBox("文件设置")
        file_layout = QVBoxLayout()

        # 输入文件选择
        input_layout = QHBoxLayout()
        self.input_label = QLabel("输入文件路径:")
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("请选择Excel文件...")
        input_btn = QPushButton("浏览...")
        input_btn.clicked.connect(self.select_input_file)
        input_layout.addWidget(self.input_label)
        input_layout.addWidget(self.input_path)
        input_layout.addWidget(input_btn)
        file_layout.addLayout(input_layout)

        # 输出文件选择
        output_layout = QHBoxLayout()
        self.output_label = QLabel("输出文件路径:")
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("默认: 当前目录/ai_translations_时间戳.xlsx")
        output_btn = QPushButton("浏览...")
        output_btn.clicked.connect(self.select_output_file)
        output_layout.addWidget(self.output_label)
        output_layout.addWidget(self.output_path)
        output_layout.addWidget(output_btn)
        file_layout.addLayout(output_layout)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # 翻译设置区域
        settings_group = QGroupBox("翻译设置")
        settings_layout = QVBoxLayout()

        # 源语言选择
        lang_layout = QHBoxLayout()
        self.source_label = QLabel("源语言:")
        self.zh_radio = QRadioButton("中文 (zh)")
        self.en_radio = QRadioButton("英文 (en)")
        self.zh_radio.setChecked(True)
        self.lang_group = QButtonGroup()
        self.lang_group.addButton(self.zh_radio)
        self.lang_group.addButton(self.en_radio)
        self.lang_group.buttonClicked.connect(self.update_text_column)
        lang_layout.addWidget(self.source_label)
        lang_layout.addWidget(self.zh_radio)
        lang_layout.addWidget(self.en_radio)
        settings_layout.addLayout(lang_layout)

        # 文本列设置
        column_layout = QHBoxLayout()
        self.column_label = QLabel("文本列名:")
        self.text_column = QLineEdit("中文")
        column_layout.addWidget(self.column_label)
        column_layout.addWidget(self.text_column)
        settings_layout.addLayout(column_layout)

        # 目标语言选择
        lang_group = QGroupBox("目标语言 (默认全选)")
        lang_grid = QVBoxLayout()

        # 全选/取消全选按钮
        select_buttons = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.clicked.connect(self.select_all_languages)
        deselect_all_btn = QPushButton("取消全选")
        deselect_all_btn.clicked.connect(self.deselect_all_languages)
        select_buttons.addWidget(select_all_btn)
        select_buttons.addWidget(deselect_all_btn)
        lang_grid.addLayout(select_buttons)

        # 语言复选框（两列布局）
        lang_cols = QHBoxLayout()
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        languages = list(TARGET_LANGUAGES.items())
        half = len(languages) // 2

        self.lang_checkboxes = {}
        for code, name in languages[:half]:
            cb = QCheckBox(name)
            cb.setChecked(True)  # 默认全选
            self.lang_checkboxes[code] = cb
            left_col.addWidget(cb)

        for code, name in languages[half:]:
            cb = QCheckBox(name)
            cb.setChecked(True)  # 默认全选
            self.lang_checkboxes[code] = cb
            right_col.addWidget(cb)

        lang_cols.addLayout(left_col)
        lang_cols.addLayout(right_col)
        lang_grid.addLayout(lang_cols)
        lang_group.setLayout(lang_grid)
        settings_layout.addWidget(lang_group)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # 进度显示区域
        progress_group = QGroupBox("进度信息")
        progress_layout = QVBoxLayout()

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setPlaceholderText("翻译日志将显示在这里...")

        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.log_display)
        progress_group.setLayout(progress_layout)
        layout.addWidget(progress_group)

        # 操作按钮
        btn_layout = QHBoxLayout()
        self.translate_btn = QPushButton("开始翻译")
        self.translate_btn.clicked.connect(self.start_translation)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.cancel_translation)
        self.cancel_btn.setEnabled(False)
        btn_layout.addWidget(self.translate_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)

    def select_input_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "选择Excel文件", "", "Excel文件 (*.xlsx *.xls)"
        )
        if path:
            self.input_path.setText(path)

    def select_output_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存翻译结果", "", "Excel文件 (*.xlsx)"
        )
        if path:
            self.output_path.setText(path)

    def update_text_column(self):
        """根据源语言自动设置默认列名"""
        if self.zh_radio.isChecked():
            self.text_column.setText("中文")
        else:
            self.text_column.setText("英文")

    def select_all_languages(self):
        """全选所有目标语言"""
        for checkbox in self.lang_checkboxes.values():
            checkbox.setChecked(True)
        self.log_message("已选择全部目标语言")

    def deselect_all_languages(self):
        """取消全选所有目标语言"""
        for checkbox in self.lang_checkboxes.values():
            checkbox.setChecked(False)
        self.log_message("已取消所有目标语言选择")

    def log_message(self, message):
        """在日志区域添加带时间戳的消息"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {message}")
        self.log_display.ensureCursorVisible()

    def update_progress(self, value, message):
        """更新进度条和日志"""
        self.progress_bar.setValue(value)
        if message:
            self.log_message(message)

    def start_translation(self):
        """开始翻译任务"""
        # 1. 验证输入
        input_path = self.input_path.text()
        if not input_path or not os.path.exists(input_path):
            self.log_message("错误: 请选择有效的输入文件路径")
            return

        # 2. 获取输出路径
        if self.output_path.text():
            output_path = self.output_path.text()
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"ai_translations_{timestamp}.xlsx"

        # 3. 获取翻译设置
        source_lang = "zh" if self.zh_radio.isChecked() else "en"
        text_column = self.text_column.text()
        target_langs = [code for code, cb in self.lang_checkboxes.items() if cb.isChecked()]

        if not target_langs:
            self.log_message("错误: 请至少选择一种目标语言")
            return

        # 4. 准备参数
        params = {
            'input_path': input_path,
            'output_path': output_path,
            'source_lang': source_lang,
            'text_column': text_column,
            'target_langs': target_langs
        }

        # 5. 禁用UI控件
        self.set_ui_enabled(False)
        self.progress_bar.setValue(0)
        self.log_message("=== 开始翻译任务 ===")
        self.log_message(f"源文件: {os.path.basename(input_path)}")
        self.log_message(f"源语言: {source_lang}")
        self.log_message(f"目标语言: {', '.join([TARGET_LANGUAGES[code] for code in target_langs])}")
        self.log_message(f"文本列: {text_column}")
        self.log_message(f"输出文件: {os.path.basename(output_path)}")

        # 6. 启动翻译线程
        self.thread = TranslationThread(params)
        self.thread.progress_updated.connect(self.update_progress)
        self.thread.finished.connect(self.translation_finished)
        self.thread.start()

    def set_ui_enabled(self, enabled):
        """设置UI控件的启用状态"""
        self.input_path.setEnabled(enabled)
        self.output_path.setEnabled(enabled)
        self.zh_radio.setEnabled(enabled)
        self.en_radio.setEnabled(enabled)
        self.text_column.setEnabled(enabled)
        for cb in self.lang_checkboxes.values():
            cb.setEnabled(enabled)
        self.translate_btn.setEnabled(enabled)
        self.cancel_btn.setEnabled(not enabled)

    def cancel_translation(self):
        """取消当前翻译任务"""
        if self.thread and self.thread.isRunning():
            self.thread.stop()
            self.log_message("警告: 用户请求取消翻译...")
            self.thread.terminate()  # 强制终止线程
            self.thread.wait()
            self.translation_finished(False, "用户取消")

    def translation_finished(self, success, message):
        """翻译完成后的处理"""
        self.set_ui_enabled(True)
        if success:
            self.log_message(f"✔ 翻译成功: {message}")
        else:
            self.log_message(f"✖ 翻译失败: {message}")
        self.log_message("=== 翻译任务结束 ===")
        self.thread = None


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon('favicon.ico'))
    window = TranslationApp()
    window.show()
    sys.exit(app.exec_())
    