"""
Naver Place 키워드 추출기 v2.0 - GUI (로직 연결)
PyQt6 기반 GUI 애플리케이션
"""

import sys
import os
from pathlib import Path

# ============================================================
# 중요: Playwright 브라우저 경로 설정 (다른 import보다 먼저!)
# EXE 환경에서 시스템에 설치된 브라우저를 사용하도록 설정
# ============================================================
if getattr(sys, 'frozen', False):
    # PyInstaller EXE 환경
    system_browsers = Path.home() / "AppData" / "Local" / "ms-playwright"
    if system_browsers.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(system_browsers)
    else:
        # 브라우저가 없으면 기본 경로 설정 (설치 안내용)
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(system_browsers)

# 프로젝트 경로 추가 (EXE/개발 환경 모두 지원)
if getattr(sys, 'frozen', False):
    # PyInstaller EXE
    script_dir = sys._MEIPASS
    exe_dir = os.path.dirname(sys.executable)  # EXE 파일 위치 (쓰기 가능)
else:
    # 개발 환경
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exe_dir = script_dir

if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QRadioButton, QButtonGroup,
    QSlider, QSpinBox, QCheckBox, QListWidget, QTextEdit, QPlainTextEdit,
    QGroupBox, QComboBox, QFileDialog, QMessageBox, QProgressBar,
    QTabWidget, QSplitter, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QFrame, QScrollArea, QSizePolicy, QLayout, QLayoutItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QRect, QSize, QPoint
from PyQt6.QtGui import QFont, QClipboard, QColor

try:
    # 키워드 생성 로직 import
    from src.place_scraper import PlaceScraper
    from src.keyword_generator import KeywordGenerator
    from src.url_parser import parse_place_url
    from src.rank_checker_graphql import RankCheckerGraphQL, ProxyConfig, RankResult
    from src.rank_checker import estimate_time
    from src.learning_manager import get_learning_manager
    from src.smart_worker import SmartWorker
    from src.playwright_installer import ensure_playwright_installed
    from src.gemini_client import get_gemini_client, ComprehensiveParseResult
    from src.keyword_parser import KeywordParser  # 사전 기반 키워드 파서
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Script dir: {script_dir}")
    print(f"Sys path: {sys.path[:3]}")
    raise


from PyQt6.QtWidgets import QDialog


# ============================================================
# 체크박스 태그 기반 키워드 선택 UI 컴포넌트
# ============================================================

class FlowLayout(QLayout):
    """자동 줄바꿈 레이아웃 - 태그들이 가로로 나열되다가 폭 초과시 자동 줄바꿈"""

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self._item_list = []
        self.setContentsMargins(margin, margin, margin, margin)
        self._spacing = spacing if spacing >= 0 else 5

    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item):
        self._item_list.append(item)

    def count(self):
        return len(self._item_list)

    def itemAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._item_list):
            return self._item_list.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._item_list:
            size = size.expandedTo(item.minimumSize())
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect, test_only):
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0

        for item in self._item_list:
            widget = item.widget()
            space_x = self._spacing
            space_y = self._spacing

            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0

            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y() + margins.bottom()

    def clear(self):
        """모든 아이템 제거"""
        while self.count():
            item = self.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class KeywordTagWidget(QWidget):
    """체크박스 태그 스타일 키워드 위젯"""

    # 시그널 정의
    toggled = pyqtSignal(str, bool)  # (키워드, 선택 상태)

    def __init__(self, text: str, checked: bool = True, category: str = "default", parent=None):
        super().__init__(parent)
        self._text = text
        self._category = category

        # 레이아웃
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 8, 2)
        layout.setSpacing(3)

        # 체크박스
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        self.checkbox.stateChanged.connect(self._on_state_changed)
        layout.addWidget(self.checkbox)

        # 라벨
        self.label = QLabel(text)
        self.label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self.label)

        # 스타일 적용
        self._update_style()

        # 전체 위젯 클릭 시 체크박스 토글
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        """위젯 클릭 시 체크박스 토글"""
        self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)

    def _on_state_changed(self, state):
        """체크 상태 변경 시"""
        self._update_style()
        # 지역 태그 토글 시 로그 출력
        if self._category == "region":
            status = "✓" if self.checkbox.isChecked() else "✗"
            print(f"[Tag][지역] {self._text} → {status}")
        self.toggled.emit(self._text, self.checkbox.isChecked())

    def _update_style(self):
        """체크 상태에 따른 스타일 업데이트"""
        # 카테고리별 색상
        colors = {
            "region": ("#e3f2fd", "#1976d2", "#bbdefb", "#0d47a1"),  # 파랑 계열
            "keyword": ("#e8f5e9", "#388e3c", "#c8e6c9", "#1b5e20"),  # 초록 계열
            "name": ("#fff3e0", "#f57c00", "#ffe0b2", "#e65100"),  # 주황 계열
            "modifier": ("#f3e5f5", "#7b1fa2", "#e1bee7", "#4a148c"),  # 보라 계열
            "decomposed": ("#fce4ec", "#c2185b", "#f8bbd9", "#880e4f"),  # 분홍 계열 (AI 분해)
            "default": ("#f5f5f5", "#616161", "#e0e0e0", "#424242"),  # 회색 계열
        }

        bg_checked, border_checked, bg_unchecked, border_unchecked = colors.get(
            self._category, colors["default"]
        )

        if self.checkbox.isChecked():
            self.setStyleSheet(f"""
                KeywordTagWidget {{
                    background-color: {bg_checked};
                    border: 1px solid {border_checked};
                    border-radius: 10px;
                    padding: 1px;
                }}
                QLabel {{
                    color: {border_checked};
                    font-weight: bold;
                }}
            """)
        else:
            self.setStyleSheet(f"""
                KeywordTagWidget {{
                    background-color: {bg_unchecked};
                    border: 1px solid {border_unchecked};
                    border-radius: 10px;
                    padding: 1px;
                    opacity: 0.6;
                }}
                QLabel {{
                    color: {border_unchecked};
                }}
            """)

    @property
    def text(self) -> str:
        return self._text

    def isChecked(self) -> bool:
        return self.checkbox.isChecked()

    def setChecked(self, checked: bool):
        self.checkbox.setChecked(checked)


class TagContainerWidget(QWidget):
    """태그들을 담는 컨테이너 (스크롤 가능, 수동 추가 가능)"""

    def __init__(self, category: str = "default", parent=None, allow_add: bool = True):
        super().__init__(parent)
        self._category = category
        self._tags = []

        # 메인 레이아웃
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2)

        # 스크롤 영역
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setMinimumHeight(50)
        self.scroll_area.setMaximumHeight(80)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: white;
            }
        """)

        # 플로우 레이아웃을 담을 위젯
        self.flow_widget = QWidget()
        self.flow_layout = FlowLayout(self.flow_widget, margin=5, spacing=5)
        self.scroll_area.setWidget(self.flow_widget)

        main_layout.addWidget(self.scroll_area)

        # 수동 추가 입력 필드 (옵션)
        if allow_add:
            add_layout = QHBoxLayout()
            add_layout.setContentsMargins(0, 2, 0, 0)
            add_layout.setSpacing(4)

            self.add_input = QLineEdit()
            self.add_input.setPlaceholderText("키워드 입력 후 Enter (쉼표로 구분 가능)")
            self.add_input.setMinimumHeight(24)
            self.add_input.setStyleSheet("""
                QLineEdit {
                    font-size: 10px;
                    padding: 2px 5px;
                    border: 1px solid #ddd;
                    border-radius: 3px;
                }
                QLineEdit:focus {
                    border: 1px solid #4CAF50;
                }
            """)
            self.add_input.returnPressed.connect(self._on_add_input)
            add_layout.addWidget(self.add_input)

            add_btn = QPushButton("+")
            add_btn.setFixedSize(24, 24)
            add_btn.setStyleSheet("""
                QPushButton {
                    font-size: 14px;
                    font-weight: bold;
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            add_btn.clicked.connect(self._on_add_input)
            add_layout.addWidget(add_btn)

            main_layout.addLayout(add_layout)

    def _on_add_input(self):
        """입력 필드에서 키워드 추가"""
        if not hasattr(self, 'add_input'):
            return
        text = self.add_input.text().strip()
        if not text:
            return

        # 쉼표로 구분된 여러 키워드 지원
        keywords = [kw.strip() for kw in text.split(',') if kw.strip()]
        added_count = 0
        for kw in keywords:
            if self.add_tag(kw, checked=True):
                added_count += 1

        self.add_input.clear()
        if added_count > 0:
            print(f"[TagContainer] {added_count}개 키워드 수동 추가: {keywords[:5]}{'...' if len(keywords) > 5 else ''}")

    def add_tag(self, text: str, checked: bool = True, is_decomposed: bool = False):
        """태그 추가"""
        # 중복 체크
        if any(tag.text == text for tag in self._tags):
            return None

        category = "decomposed" if is_decomposed else self._category
        tag = KeywordTagWidget(text, checked, category)
        self._tags.append(tag)
        self.flow_layout.addWidget(tag)
        return tag

    def add_tags(self, texts: list, checked: bool = True, is_decomposed: bool = False):
        """여러 태그 추가"""
        for text in texts:
            if text and text.strip():
                self.add_tag(text.strip(), checked, is_decomposed)

    def clear_tags(self):
        """모든 태그 제거"""
        self._tags = []
        self.flow_layout.clear()

    def get_selected(self) -> list:
        """선택된 키워드 리스트 반환"""
        selected = [tag.text for tag in self._tags if tag.isChecked()]
        # 디버그: 지역 태그일 경우 선택 상태 출력
        if self._category == "region":
            all_tags = [tag.text for tag in self._tags]
            print(f"[TagContainer][{self._category}] 전체: {all_tags}, 선택됨: {selected}")
        return selected

    def get_all(self) -> list:
        """모든 키워드 리스트 반환"""
        return [tag.text for tag in self._tags]

    def select_all(self):
        """전체 선택"""
        for tag in self._tags:
            tag.setChecked(True)

    def deselect_all(self):
        """전체 해제"""
        for tag in self._tags:
            tag.setChecked(False)

    def set_tags(self, texts: list, checked: bool = True):
        """태그 목록 설정 (기존 태그 제거 후 새로 추가)"""
        self.clear_tags()
        self.add_tags(texts, checked)


class ProxySettingsDialog(QDialog):
    """프록시 설정 다이얼로그 (별도 창)"""

    def __init__(self, proxy_data: dict, parent=None):
        super().__init__(parent)
        self.proxy_data = proxy_data.copy()
        self.proxy_data["proxies"] = list(proxy_data.get("proxies", []))
        self.setWindowTitle("프록시 설정")
        self.setMinimumSize(700, 500)
        self.resize(750, 550)
        self._setup_ui()
        self._load_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 1. 프록시 사용 체크 ===
        top_row = QHBoxLayout()
        self.use_proxy_check = QCheckBox("프록시 사용")
        self.use_proxy_check.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.use_proxy_check.toggled.connect(self._on_proxy_toggle)
        top_row.addWidget(self.use_proxy_check)

        self.use_own_ip_check = QCheckBox("내 IP도 사용")
        self.use_own_ip_check.setChecked(True)
        top_row.addWidget(self.use_own_ip_check)

        top_row.addStretch()

        self.count_label = QLabel("총 0개")
        self.count_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        top_row.addWidget(self.count_label)

        layout.addLayout(top_row)

        # === 2. Decodo 설정 ===
        decodo_group = QGroupBox("Decodo (한국 Residential IP)")
        decodo_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 13px;
                border: 2px solid #5c6bc0;
                border-radius: 8px;
                margin-top: 12px;
                padding: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 10px;
                color: #5c6bc0;
            }
        """)
        decodo_layout = QVBoxLayout()
        decodo_layout.setSpacing(12)

        # Username / Password
        auth_row = QHBoxLayout()
        auth_row.setSpacing(20)

        auth_row.addWidget(QLabel("Username:"))
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Decodo 사용자명")
        self.username_edit.setMinimumWidth(180)
        self.username_edit.setMinimumHeight(30)
        auth_row.addWidget(self.username_edit)

        auth_row.addWidget(QLabel("Password:"))
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Decodo 비밀번호")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setMinimumWidth(180)
        self.password_edit.setMinimumHeight(30)
        auth_row.addWidget(self.password_edit)

        self.show_pw_check = QCheckBox("보기")
        self.show_pw_check.toggled.connect(
            lambda c: self.password_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if c else QLineEdit.EchoMode.Password
            )
        )
        auth_row.addWidget(self.show_pw_check)

        auth_row.addStretch()
        decodo_layout.addLayout(auth_row)

        # 엔드포인트 수 + 연결 버튼
        connect_row = QHBoxLayout()
        connect_row.setSpacing(15)

        connect_row.addWidget(QLabel("엔드포인트 수:"))
        self.endpoint_spin = QSpinBox()
        self.endpoint_spin.setRange(1, 500)
        self.endpoint_spin.setValue(50)
        self.endpoint_spin.setMinimumWidth(80)
        self.endpoint_spin.setMinimumHeight(30)
        connect_row.addWidget(self.endpoint_spin)

        connect_row.addWidget(QLabel("(kr.decodo.com:10001~)"))
        connect_row.addStretch()

        self.connect_btn = QPushButton("🔗 Decodo 연결")
        self.connect_btn.setMinimumHeight(38)
        self.connect_btn.setMinimumWidth(140)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #5c6bc0;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #3f51b5; }
        """)
        self.connect_btn.clicked.connect(self._generate_decodo)
        connect_row.addWidget(self.connect_btn)

        decodo_layout.addLayout(connect_row)
        decodo_group.setLayout(decodo_layout)
        layout.addWidget(decodo_group)

        # === 3. 고정 IP (CSV) ===
        csv_row = QHBoxLayout()
        csv_row.addWidget(QLabel("고정 IP (Datacenter):"))
        csv_row.addStretch()

        self.csv_btn = QPushButton("📁 CSV 추가")
        self.csv_btn.setMinimumHeight(30)
        self.csv_btn.clicked.connect(self._load_csv)
        csv_row.addWidget(self.csv_btn)

        self.clear_btn = QPushButton("🗑️ 전체 삭제")
        self.clear_btn.setMinimumHeight(30)
        self.clear_btn.clicked.connect(self._clear_proxies)
        csv_row.addWidget(self.clear_btn)

        layout.addLayout(csv_row)

        # === 4. 프록시 테이블 ===
        self.proxy_table = QTableWidget()
        self.proxy_table.setColumnCount(3)
        self.proxy_table.setHorizontalHeaderLabels(["IP", "포트", "타입"])
        self.proxy_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.proxy_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self.proxy_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.proxy_table.setColumnWidth(1, 80)
        self.proxy_table.setColumnWidth(2, 100)
        self.proxy_table.setMinimumHeight(200)
        self.proxy_table.setStyleSheet("""
            QTableWidget {
                font-size: 12px;
                gridline-color: #ddd;
                alternate-background-color: #f8f8f8;
            }
            QTableWidget::item { padding: 5px; }
            QHeaderView::section {
                background-color: #5c6bc0;
                color: white;
                font-weight: bold;
                padding: 8px;
                border: none;
            }
        """)
        self.proxy_table.setAlternatingRowColors(True)
        self.proxy_table.verticalHeader().setVisible(False)
        self.proxy_table.verticalHeader().setDefaultSectionSize(30)
        layout.addWidget(self.proxy_table, 1)

        # === 5. 버튼 ===
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.setMinimumHeight(38)
        cancel_btn.setMinimumWidth(100)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = QPushButton("저장")
        save_btn.setMinimumHeight(38)
        save_btn.setMinimumWidth(100)
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #43A047; }
        """)
        save_btn.clicked.connect(self.accept)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _load_data(self):
        """저장된 데이터 로드"""
        self.use_proxy_check.setChecked(self.proxy_data.get("use_proxy", False))
        self.use_own_ip_check.setChecked(self.proxy_data.get("use_own_ip", True))
        self.username_edit.setText(self.proxy_data.get("decodo_username", ""))
        self.password_edit.setText(self.proxy_data.get("decodo_password", ""))
        self.endpoint_spin.setValue(self.proxy_data.get("decodo_endpoint_count", 50))
        self._refresh_table()
        self._on_proxy_toggle(self.use_proxy_check.isChecked())

    def _on_proxy_toggle(self, checked):
        """프록시 사용 토글"""
        self.use_own_ip_check.setEnabled(checked)
        self.username_edit.setEnabled(checked)
        self.password_edit.setEnabled(checked)
        self.show_pw_check.setEnabled(checked)
        self.endpoint_spin.setEnabled(checked)
        self.connect_btn.setEnabled(checked)
        self.csv_btn.setEnabled(checked)
        self.clear_btn.setEnabled(checked)
        self.proxy_table.setEnabled(checked)

    def _generate_decodo(self):
        """Decodo 엔드포인트 생성"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        if not username or not password:
            QMessageBox.warning(self, "입력 필요", "Username과 Password를 입력해주세요.")
            return

        count = self.endpoint_spin.value()

        # 기존 Decodo 제거
        self.proxy_data["proxies"] = [
            p for p in self.proxy_data["proxies"]
            if p.get("type", "").lower() != "decodo"
        ]

        # 새 Decodo 추가
        for i in range(count):
            self.proxy_data["proxies"].append({
                "host": "kr.decodo.com",
                "port": 10001 + i,
                "type": "decodo"
            })

        self._refresh_table()
        QMessageBox.information(self, "완료", f"Decodo {count}개 엔드포인트 추가됨")

    def _load_csv(self):
        """CSV 파일 로드"""
        import csv
        from datetime import datetime

        file_path, _ = QFileDialog.getOpenFileName(self, "CSV 파일 선택", "", "CSV (*.csv)")
        if not file_path:
            return

        try:
            now = datetime.now()
            added = 0

            with open(file_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ip = row.get('IP', '').strip()
                    port = row.get('Port', '').strip()
                    proxy_type = row.get('Type', '').strip().lower()
                    end_date = row.get('EndDate', '').strip()

                    if not ip or not port:
                        continue

                    try:
                        port_num = int(port)
                    except:
                        continue

                    # 타입 자동 판단
                    if not proxy_type:
                        proxy_type = 'decodo' if 'decodo' in ip.lower() else 'datacenter'

                    # 만료 체크
                    if end_date:
                        try:
                            if datetime.strptime(end_date, "%Y-%m-%d %H:%M") < now:
                                continue
                        except:
                            pass

                    self.proxy_data["proxies"].append({
                        "host": ip,
                        "port": port_num,
                        "type": proxy_type
                    })
                    added += 1

            self._refresh_table()
            QMessageBox.information(self, "완료", f"{added}개 프록시 추가됨")

        except Exception as e:
            QMessageBox.warning(self, "오류", str(e))

    def _clear_proxies(self):
        """모든 프록시 삭제"""
        self.proxy_data["proxies"] = []
        self._refresh_table()

    def _refresh_table(self):
        """테이블 새로고침"""
        self.proxy_table.setRowCount(0)
        proxies = self.proxy_data.get("proxies", [])

        for p in proxies:
            row = self.proxy_table.rowCount()
            self.proxy_table.insertRow(row)

            ip_item = QTableWidgetItem(p.get("host", ""))
            port_item = QTableWidgetItem(str(p.get("port", "")))
            type_item = QTableWidgetItem(p.get("type", "").upper())

            port_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            type_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            if p.get("type", "").lower() == "decodo":
                type_item.setForeground(Qt.GlobalColor.blue)
            else:
                type_item.setForeground(Qt.GlobalColor.darkGreen)

            self.proxy_table.setItem(row, 0, ip_item)
            self.proxy_table.setItem(row, 1, port_item)
            self.proxy_table.setItem(row, 2, type_item)

        # 개수 업데이트
        total = len(proxies)
        decodo = sum(1 for p in proxies if p.get("type", "").lower() == "decodo")
        dc = total - decodo

        text = f"총 {total}개"
        if decodo > 0:
            text += f" (Decodo: {decodo}"
            if dc > 0:
                text += f", DC: {dc}"
            text += ")"
        elif dc > 0:
            text += f" (DC: {dc})"

        self.count_label.setText(text)

    def get_data(self) -> dict:
        """설정 데이터 반환"""
        return {
            "use_proxy": self.use_proxy_check.isChecked(),
            "use_own_ip": self.use_own_ip_check.isChecked(),
            "decodo_username": self.username_edit.text(),
            "decodo_password": self.password_edit.text(),
            "decodo_endpoint_count": self.endpoint_spin.value(),
            "proxies": self.proxy_data.get("proxies", [])
        }


class GeminiSettingsDialog(QDialog):
    """Gemini API 설정 다이얼로그"""

    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.settings = settings.copy()
        self.setWindowTitle("Gemini AI 설정")
        self.setMinimumSize(500, 300)
        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # === 설명 ===
        desc_label = QLabel(
            "Gemini AI를 사용하면 상호명에서 더 정확한 키워드를 추출하고,\n"
            "연관 키워드를 자동으로 생성할 수 있습니다."
        )
        desc_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(desc_label)

        # === API 키 입력 ===
        api_group = QGroupBox("API 키 설정")
        api_layout = QVBoxLayout(api_group)

        # 사용 체크박스
        self.use_gemini_check = QCheckBox("Gemini AI 사용")
        self.use_gemini_check.setStyleSheet("font-weight: bold;")
        self.use_gemini_check.toggled.connect(self._on_toggle)
        api_layout.addWidget(self.use_gemini_check)

        # API 키 입력
        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API 키:"))
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Google AI Studio에서 발급받은 API 키 입력")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self.api_key_edit)

        # 보기/숨기기 버튼
        self.show_key_btn = QPushButton("👁")
        self.show_key_btn.setFixedWidth(30)
        self.show_key_btn.setCheckable(True)
        self.show_key_btn.toggled.connect(self._toggle_key_visibility)
        key_row.addWidget(self.show_key_btn)

        api_layout.addLayout(key_row)

        # 테스트 버튼
        test_row = QHBoxLayout()
        self.test_btn = QPushButton("🔗 연결 테스트")
        self.test_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self.test_btn)

        self.test_result_label = QLabel("")
        self.test_result_label.setStyleSheet("font-size: 11px;")
        test_row.addWidget(self.test_result_label)
        test_row.addStretch()

        api_layout.addLayout(test_row)

        # API 키 발급 안내
        link_label = QLabel(
            '<a href="https://aistudio.google.com/apikey">Google AI Studio에서 API 키 발급받기</a>'
        )
        link_label.setOpenExternalLinks(True)
        link_label.setStyleSheet("font-size: 11px;")
        api_layout.addWidget(link_label)

        layout.addWidget(api_group)

        # === 기능 설정 ===
        func_group = QGroupBox("기능 설정")
        func_layout = QVBoxLayout(func_group)

        self.name_parse_check = QCheckBox("상호명 형태소 분석 (붙어있는 단어 분리)")
        self.name_parse_check.setChecked(True)
        func_layout.addWidget(self.name_parse_check)

        self.related_kw_check = QCheckBox("연관 키워드 자동 생성")
        self.related_kw_check.setChecked(True)
        func_layout.addWidget(self.related_kw_check)

        layout.addWidget(func_group)

        layout.addStretch()

        # === 버튼 ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("취소")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        save_btn = QPushButton("저장")
        save_btn.setStyleSheet("font-weight: bold;")
        save_btn.clicked.connect(self.accept)
        btn_layout.addWidget(save_btn)

        layout.addLayout(btn_layout)

    def _load_settings(self):
        """설정 로드"""
        self.use_gemini_check.setChecked(self.settings.get("use_gemini", False))
        self.api_key_edit.setText(self.settings.get("gemini_api_key", ""))
        self.name_parse_check.setChecked(self.settings.get("gemini_name_parse", True))
        self.related_kw_check.setChecked(self.settings.get("gemini_related_kw", True))
        self._on_toggle(self.use_gemini_check.isChecked())

    def _on_toggle(self, enabled: bool):
        """Gemini 사용 토글"""
        self.api_key_edit.setEnabled(enabled)
        self.test_btn.setEnabled(enabled)
        self.name_parse_check.setEnabled(enabled)
        self.related_kw_check.setEnabled(enabled)

    def _toggle_key_visibility(self, checked: bool):
        """API 키 보기/숨기기"""
        if checked:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.show_key_btn.setText("🙈")
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.show_key_btn.setText("👁")

    def _test_connection(self):
        """API 연결 테스트"""
        api_key = self.api_key_edit.text().strip()
        if not api_key:
            self.test_result_label.setText("❌ API 키를 입력하세요")
            self.test_result_label.setStyleSheet("color: red; font-size: 11px;")
            return

        self.test_result_label.setText("⏳ 테스트 중...")
        self.test_result_label.setStyleSheet("color: gray; font-size: 11px;")
        QApplication.processEvents()

        try:
            from src.gemini_client import GeminiClient
            client = GeminiClient(api_key)
            success, message = client.test_connection()

            if success:
                self.test_result_label.setText("✅ 연결 성공!")
                self.test_result_label.setStyleSheet("color: green; font-size: 11px;")
            else:
                self.test_result_label.setText(f"❌ {message}")
                self.test_result_label.setStyleSheet("color: red; font-size: 11px;")
        except Exception as e:
            self.test_result_label.setText(f"❌ 오류: {str(e)[:30]}")
            self.test_result_label.setStyleSheet("color: red; font-size: 11px;")

    def get_settings(self) -> dict:
        """설정 반환"""
        return {
            "use_gemini": self.use_gemini_check.isChecked(),
            "gemini_api_key": self.api_key_edit.text().strip(),
            "gemini_name_parse": self.name_parse_check.isChecked(),
            "gemini_related_kw": self.related_kw_check.isChecked()
        }


class PlaceExtractWorker(QThread):
    """플레이스 정보 추출 워커 (지역, 키워드, 상호명 등)"""
    finished = pyqtSignal(dict)  # 추출된 정보 딕셔너리
    error = pyqtSignal(str)
    progress = pyqtSignal(str)

    # 단독 사용 불가 키워드
    STANDALONE_BLOCKED = {
        "24시", "아트", "샵", "전문", "추천", "잘하는", "유명한",
        "근처", "주변", "부근", "가까운"
    }
    # 지역 접미 수식어 ("앞", "인근" 제거)
    LOCATION_SUFFIXES = ["근처", "주변", "부근", "가까운"]

    # 전국에 중복으로 존재하는 동 이름 (단독 사용 시 검색 결과 부정확)
    DUPLICATE_DONG_NAMES = {
        "역삼동", "역삼", "신사동", "신사", "삼성동", "삼성", "대치동", "대치",
        "청담동", "청담", "논현동", "논현", "서초동", "서초", "방배동", "방배",
        "잠실동", "잠실", "송파동", "송파", "강동", "강서동", "강서",
        "고덕동", "고덕", "길동", "암사동", "암사", "천호동", "천호", "둔촌동", "둔촌",
        "영등포동", "영등포", "여의도동", "여의도", "마포동", "마포",
        "용산동", "용산", "성북동", "성북", "동대문", "서대문",
        "중앙동", "중앙", "신정동", "신정", "신월동", "신월",
        "목동", "등촌동", "등촌", "화곡동", "화곡", "개봉동", "개봉",
        "구로동", "구로", "금천동", "금천", "관악동", "관악",
        "동작동", "동작", "사당동", "사당", "노원동", "노원",
        "도봉동", "도봉", "수유동", "수유", "쌍문동", "쌍문",
        "창동", "월계동", "월계", "공릉동", "공릉", "하계동", "하계",
        "중계동", "중계", "상계동", "상계", "태릉", "석계동", "석계",
        "신림동", "신림", "봉천동", "봉천", "낙성대동", "낙성대",
        "신대방동", "신대방", "흑석동", "흑석",
        "신흥동", "신흥", "행정동", "행정", "행복동", "행복",
        "남산동", "남산", "북산동", "북산", "동산동", "동산", "서산동", "서산",
        "명동", "본동", "신동", "구동", "상동", "하동",
        "내동", "외동", "대동", "소동", "장동", "단동",
        "남동", "북동", "동동", "서동",
        "성내동", "성내", "성외동", "성외", "성남동", "성남",
        "신창동", "신창", "구창동", "구창",
        "도화동", "도화", "산곡동", "산곡", "부평동", "부평",
        "인천동", "수원동", "수원", "안양동", "안양",
        "부천동", "부천", "광명동", "광명", "시흥동", "시흥",
        "평촌동", "평촌", "범계동", "범계", "안산동", "안산",
        "일산동", "일산", "분당동", "분당", "판교동", "판교",
        "동탄동", "동탄", "광교동", "광교", "영통동", "영통",
        "매탄동", "매탄", "권선동", "권선", "장안동", "장안",
        "송내동", "송내", "중동", "소사동", "소사",
        "오정동", "오정", "원미동", "원미",
        "해운대", "서면", "남포동", "남포", "동래동", "동래",
        "연산동", "연산", "부전동", "부전", "범일동", "범일",
        "대연동", "대연", "용호동", "용호", "광안동", "광안",
        "수영동", "수영", "민락동", "민락", "센텀",
        "동구", "서구", "남구", "북구", "중구",
        "유성동", "유성", "둔산동", "둔산", "월평동", "월평",
        "봉명동", "봉명", "탄방동", "탄방", "관저동", "관저",
        "충무동", "충무", "동명동", "동명", "서명동", "서명",
        "북성동", "북성", "남성동", "남성",
        "구월동", "구월", "간석동", "간석", "만수동", "만수",
        "연수동", "연수", "송도동", "송도",
    }

    # 리뷰 테마 → 검색 키워드 매핑
    THEME_MAPPING = {
        "전망": ["뷰맛집", "오션뷰", "전망좋은"],
        "분위기": ["분위기좋은", "감성", "인테리어"],
        "가격": ["가성비", "저렴한", "착한가격"],
        "목적": ["데이트", "모임", "회식"],
        "주차": ["주차가능", "주차편한"],
        "사진": ["사진맛집", "포토존"],
        "친절": ["친절한"],
        "특별한": ["이색", "특별한"],
        "단체": ["단체석", "넓은"],
        "혼밥": ["혼밥", "혼술"],
        "청결": ["깨끗한", "청결한"],
        "시술": ["시술잘하는", "전문"],
        "기술": ["기술좋은", "실력좋은"],
    }

    # 검색에 부적합하여 제외할 테마
    NON_SEARCHABLE_THEMES = {
        "청결도", "음식량", "위치", "대기시간", "방역",
        "배달", "예약", "화장실", "반려동물", "서비스",
        "만족도", "시설", "규모", "편의", "약품・제품",
        "기술・시술", "공연・전시공간", "약품", "제품",
        "전시공간", "공연"
    }

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self.gemini_client = get_gemini_client()
        # 사전 기반 키워드 파서 (지역/업종/수식어 구분용)
        try:
            self.keyword_parser = KeywordParser()
        except Exception as e:
            print(f"[PlaceExtractWorker] KeywordParser 초기화 실패: {e}")
            self.keyword_parser = None

    def run(self):
        import asyncio
        try:
            self.progress.emit("플레이스 정보 추출 중...")

            parsed = parse_place_url(self.url)
            if not parsed.is_valid:
                self.error.emit(f"URL 파싱 실패: {parsed.error_message}")
                return

            place_url = f"https://m.place.naver.com/{parsed.place_type.value}/{parsed.mid}"
            place_data = asyncio.run(self._fetch_place_data(place_url))

            if not place_data:
                self.error.emit("데이터 수집 실패")
                return

            # 0. 예약 정보 조회 (GraphQL API)
            self.progress.emit("예약 정보 확인 중...")
            booking_info = asyncio.run(self._fetch_booking_info(parsed.mid))
            place_data.has_booking = booking_info.get("has_booking", False)
            place_data.booking_type = booking_info.get("booking_type")
            place_data.booking_hub_id = booking_info.get("booking_hub_id")
            place_data.booking_url = booking_info.get("booking_url")

            if place_data.has_booking:
                booking_type_str = "네이버예약" if place_data.booking_type == "realtime" else "외부예약"
                print(f"[PlaceExtractWorker] 예약 기능 감지: {booking_type_str}")
                self.progress.emit(f"예약 기능 감지: {booking_type_str}")

            # 1. 기본 지역 정보 수집 (시/도 → 시 → 구 → 동 순서)
            base_regions = []
            # 시/도 (경기, 서울 등) - 단독 사용 X, 조합에서만
            if place_data.region.city:
                base_regions.append(place_data.region.city)
            # 시 (평택시, 고양시 등)
            if place_data.region.si:
                base_regions.append(place_data.region.si)
            # 주요 지역명 (일산 from 일산동구)
            if place_data.region.major_area:
                base_regions.append(place_data.region.major_area)
            # 구 (일산동구, 강남구 등)
            if place_data.region.gu:
                base_regions.append(place_data.region.gu)
            # 동 (고덕동, 장항동 등)
            if place_data.region.dong:
                base_regions.append(place_data.region.dong)
            # 역 (정발산역 등)
            if place_data.region.station:
                base_regions.append(place_data.region.station)
            # 도로명 (중앙로 등) - 단독 사용 X
            if place_data.region.road:
                base_regions.append(place_data.region.road)
            # 발견된 지역도 추가
            if hasattr(place_data, 'discovered_regions'):
                base_regions.extend(list(place_data.discovered_regions))

            # 2. 지역 조합 자동 생성 (시+동, 역+근처 등)
            regions = self._generate_region_combinations(base_regions)
            print(f"[PlaceExtractWorker] 지역 조합 생성: {len(base_regions)}개 → {len(regions)}개")

            # 3. 키워드 수집 (대표키워드, 메뉴, 리뷰키워드) - AI 기반 분석
            keywords = []
            discovered_regions = set()  # 키워드에서 발견된 지역

            # AI 종합 파싱 시도
            ai_parse_result = None
            if self.gemini_client.is_available():
                self.progress.emit("AI로 키워드 분석 중...")
                try:
                    ai_parse_result = self.gemini_client.comprehensive_parse(
                        name=place_data.name,
                        category=place_data.category,
                        address=place_data.jibun_address or place_data.road_address,
                        keywords=place_data.keywords,
                        menus=[m for m in place_data.menus[:10]]
                    )

                    if ai_parse_result.success:
                        # AI에서 발견한 지역/랜드마크 추가
                        for region in ai_parse_result.regions:
                            discovered_regions.add(region)
                        for landmark in ai_parse_result.landmarks:
                            discovered_regions.add(landmark)

                        # AI에서 발견한 키워드 추가
                        for kw in ai_parse_result.business_types:
                            if kw not in keywords:
                                keywords.append(kw)
                        for kw in ai_parse_result.services:
                            if kw not in keywords:
                                keywords.append(kw)
                        for kw in ai_parse_result.modifiers:
                            if kw not in keywords:
                                keywords.append(kw)
                        for kw in ai_parse_result.themes:
                            if kw not in keywords:
                                keywords.append(kw)
                        for kw in ai_parse_result.name_tokens:
                            if kw not in keywords and not self._is_region_keyword(kw):
                                keywords.append(kw)

                        print(f"[PlaceExtractWorker] AI 파싱 성공: 지역 {len(discovered_regions)}개, 키워드 {len(keywords)}개")
                except Exception as e:
                    print(f"[PlaceExtractWorker] AI 파싱 실패: {e}")
                    ai_parse_result = None

            # AI 실패 시 또는 AI 미사용 시 기본 로직
            if not ai_parse_result or not ai_parse_result.success:
                print("[PlaceExtractWorker] 기본 파싱 로직 사용")
                # 대표키워드 처리 (지역+키워드 조합 분리)
                for kw in place_data.keywords:
                    if len(kw) < 2:
                        continue

                    # 지역+키워드 조합인지 확인하고 분리 (선릉역텐동 → 선릉역 + 텐동)
                    region_part, keyword_part = self._extract_region_from_keyword(kw, base_regions)

                    if region_part:
                        # 지역+키워드 조합: 지역은 discovered_regions에, 키워드는 keywords에
                        discovered_regions.add(region_part)
                        if keyword_part and keyword_part not in keywords and len(keyword_part) >= 2:
                            keywords.append(keyword_part)
                        print(f"[PlaceExtractWorker] 지역+키워드 분리: '{kw}' → 지역='{region_part}', 키워드='{keyword_part}'")
                    elif self._is_region_keyword(kw):
                        # 순수 지역 키워드
                        discovered_regions.add(kw)
                    elif kw not in keywords:
                        # 일반 키워드
                        keywords.append(kw)

            # 메뉴 (최대 10개)
            for menu in place_data.menus[:10]:
                if menu not in keywords:
                    keywords.append(menu)

            # 리뷰 키워드
            for rk in place_data.review_menu_keywords[:10]:
                if rk.label not in keywords:
                    keywords.append(rk.label)

            # 병원: 진료과목
            for subj in place_data.medical_subjects:
                if subj not in keywords:
                    keywords.append(subj)

            # 4. 단독 사용 불가 키워드 필터링
            keywords = self._filter_standalone_keywords(keywords)

            # 4.5. AI 연관 키워드 추가 (종합 파싱 결과에서) - 지역 제외
            if ai_parse_result and ai_parse_result.success and ai_parse_result.related_keywords:
                added_related = []
                for kw in ai_parse_result.related_keywords:
                    # 지역 키워드는 제외, 지역+수식어 조합은 허용 (예: 신사동맛집)
                    if self._is_region_keyword(kw):
                        discovered_regions.add(kw)
                    elif kw not in keywords:
                        keywords.append(kw)
                        added_related.append(kw)
                if added_related:
                    print(f"[PlaceExtractWorker] AI 연관 키워드: {added_related}")

            # 5. 발견된 지역을 base_regions에 추가 후 조합 재생성
            if discovered_regions:
                print(f"[PlaceExtractWorker] 키워드에서 지역 발견: {discovered_regions}")
                base_regions.extend(list(discovered_regions))
                regions = self._generate_region_combinations(base_regions)
                print(f"[PlaceExtractWorker] 지역 조합 재생성: {len(base_regions)}개 → {len(regions)}개")

            # 5. 상호명 형태소 분석 (분리 + 조합) - Gemini AI 사용 가능
            name_parts = self._parse_business_name_morphemes(place_data.name, place_data.category)
            print(f"[PlaceExtractWorker] 상호명 형태소 분석: '{place_data.name}' → {name_parts}")

            # 6. 수식어 (리뷰 테마 → 검색 키워드 변환)
            modifiers = []
            excluded_themes = []
            for rk in place_data.review_theme_keywords:
                theme = rk.label
                # 제외할 테마 체크
                if theme in self.NON_SEARCHABLE_THEMES:
                    excluded_themes.append(theme)
                    continue
                # 매핑된 검색 키워드로 변환
                if theme in self.THEME_MAPPING:
                    modifiers.extend(self.THEME_MAPPING[theme][:2])  # 상위 2개만
                else:
                    # 매핑 없으면 원본 사용 (단, 특수문자 포함시 제외)
                    if "・" not in theme and "," not in theme:
                        modifiers.append(theme)

            # 중복 제거
            modifiers = list(dict.fromkeys(modifiers))
            if excluded_themes:
                # 특수문자 제거 후 출력 (인코딩 오류 방지)
                safe_themes = [t.replace("・", "/") for t in excluded_themes]
                print(f"[PlaceExtractWorker] 제외된 테마: {safe_themes}")

            # 7. 예약 키워드 - 비활성화됨 (사용자 요청으로 OFF)
            # 실시간 예약 키워드 기능은 사용하지 않음
            booking_keywords = []
            # if place_data.has_booking:
            #     booking_keywords = self._generate_booking_keywords(keywords, regions)
            #     if booking_keywords:
            #         print(f"[PlaceExtractWorker] 예약 키워드 생성: {len(booking_keywords)}개")
            #         self.progress.emit(f"예약 키워드 {len(booking_keywords)}개 생성")

            # 8. 최종 필터링: keywords에서 지역명/상호명 제거
            #    - 순수 지역명 (압구정, 강남역) → 제외 (regions에 있음)
            #    - 지역+키워드 조합 (평택파히타, 신사동맛집) → 제외 (백엔드에서 조합)
            #    - 상호명 변형 (르글라스) → 제외 (name_parts에 있음)
            filtered_keywords = []
            removed_keywords = []
            extracted_keywords_from_combos = []  # 조합에서 추출된 순수 키워드
            name_parts_set = set(name_parts)  # 상호명 변형 집합

            # 현재까지 발견된 모든 지역명 (필터링용)
            all_known_regions = set(base_regions)

            for kw in keywords:
                # 상호명 변형과 일치하면 제외
                if kw in name_parts_set:
                    removed_keywords.append(f"{kw}(상호명)")
                    continue

                # 순수 지역 키워드면 제외하고 지역 목록에 추가
                if self._is_region_keyword(kw):
                    removed_keywords.append(f"{kw}(지역)")
                    if kw not in all_known_regions:
                        all_known_regions.add(kw)
                        base_regions.append(kw)
                    continue

                # 지역+키워드 조합 확인 (평택파히타, 비전동스테이크 등)
                region_part, keyword_part = self._extract_region_from_keyword(kw, all_known_regions)
                if region_part:
                    removed_keywords.append(f"{kw}(지역조합→{keyword_part})")
                    # 순수 키워드 부분만 추출하여 추가
                    if keyword_part not in filtered_keywords and keyword_part not in extracted_keywords_from_combos:
                        extracted_keywords_from_combos.append(keyword_part)
                    continue

                # 기존 패턴 체크 (신사동맛집 등)
                if self._has_non_region_component(kw, all_known_regions):
                    removed_keywords.append(f"{kw}(지역조합)")
                    continue

                filtered_keywords.append(kw)

            # 조합에서 추출된 키워드 추가 (중복 제거)
            for ek in extracted_keywords_from_combos:
                if ek not in filtered_keywords:
                    filtered_keywords.append(ek)

            if removed_keywords:
                print(f"[PlaceExtractWorker] 키워드에서 제외: {removed_keywords}")

            # 9. 지역 + 키워드 조합 생성 (지역+키워드 → 지역+키워드+근처/주변)
            region_keyword_combos = self._generate_region_keyword_combinations(
                base_regions, filtered_keywords
            )

            # 10. AI 키워드 분해 (복합 키워드를 단어 단위로 분해)
            decomposed_keywords = []
            if self.gemini_client and self.gemini_client.is_available():
                try:
                    self.progress.emit("AI 키워드 분해 중...")
                    # 대표키워드만 분해 대상으로 (메뉴/서비스 키워드)
                    keywords_to_decompose = list(place_data.keywords)[:15]
                    if keywords_to_decompose:
                        decomposed = self.gemini_client.decompose_keywords(
                            keywords=keywords_to_decompose,
                            category=place_data.category
                        )
                        # 기존 키워드에 없는 것 + 지역조합 제외 + 순수 지역 제외
                        existing_set = set(filtered_keywords)
                        for dk in decomposed:
                            if dk in existing_set:
                                continue
                            # 지역 조합이면 제외
                            region_part, _ = self._extract_region_from_keyword(dk, all_known_regions)
                            if region_part:
                                continue
                            # 순수 지역이면 지역 목록에 추가
                            if self._is_region_keyword(dk):
                                if dk not in all_known_regions:
                                    all_known_regions.add(dk)
                                    base_regions.append(dk)
                                continue
                            decomposed_keywords.append(dk)
                        print(f"[PlaceExtractWorker] AI 분해 키워드: {len(decomposed_keywords)}개 추가")
                except Exception as e:
                    print(f"[PlaceExtractWorker] AI 키워드 분해 실패 (무시): {e}")

            # UI에는 순수 지역명/키워드만 표시, 조합은 백엔드에서 처리
            # base_regions 중복 제거 및 정리
            unique_base_regions = list(dict.fromkeys(base_regions))

            result = {
                "place_data": place_data,
                "name": place_data.name,
                "category": place_data.category,
                "regions": unique_base_regions,  # UI용: 순수 지역명만 (평택, 소사벌, 비전동 등)
                "region_combinations": regions,  # 백엔드용: 모든 지역 조합
                "keywords": list(dict.fromkeys(filtered_keywords)),  # UI용: 개별 키워드만
                "decomposed_keywords": decomposed_keywords,  # AI 분해 키워드 (개별 단어)
                "region_keyword_combos": region_keyword_combos,  # 백엔드용: 지역+키워드 조합
                "name_parts": name_parts,
                "modifiers": modifiers,
                # 예약 정보
                "has_booking": place_data.has_booking,
                "booking_type": place_data.booking_type,
                "booking_keywords": booking_keywords,
            }

            self.progress.emit(f"✅ {place_data.name} 추출 완료")
            self.finished.emit(result)

        except Exception as e:
            import traceback
            self.error.emit(f"오류: {str(e)}\n{traceback.format_exc()}")

    def _generate_region_combinations(self, regions):
        """
        지역 조합 자동 생성 - 모든 가능한 조합 생성

        레벨별 분류:
        - L0: 시/도 (경기, 서울 등) - 단독 사용 X, 조합에서만
        - L1: 시 (평택시, 평택, 고양시, 고양 등) - 단독 사용 O
        - L2: 구 (일산동구, 일산동, 강남구, 강남 등) - 단독 사용 O
        - L3: 동 (고덕동, 고덕, 장항동, 장항 등) - 중복 동은 조합에서만
        - L4: 역 (정발산역, 정발산 등) - 단독 사용 O
        - L5: 도로명 (중앙로 등) - 단독 사용 X, 조합에서만

        조합 규칙:
        1. 모든 레벨 조합: L0+L1, L0+L2, L0+L3, L1+L2, L1+L3, L2+L3, L0+L1+L3 등
        2. 모든 조합 + 수식어: 근처, 주변, 부근, 가까운
        3. 중복 동은 단독 사용 X, 상위 레벨과 조합에서만 사용
        """
        result = set()

        # === 레벨별 분류 ===
        province_list = []      # L0: 시/도 (경기, 서울) - 단독 X
        city_list = []          # L1: 시 (평택시, 평택)
        gu_list = []            # L2: 구 (일산동구, 일산동)
        dong_list = []          # L3: 동 (고덕동, 고덕)
        unique_dong_list = []   # L3-유일: 단독 사용 가능한 동
        duplicate_dong_list = [] # L3-중복: 조합에서만 사용하는 동
        station_list = []       # L4: 역 (정발산역, 정발산)
        road_list = []          # L5: 도로명 - 단독 X

        # 알려진 시/도 목록
        PROVINCES = {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
                     "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"}

        for r in regions:
            r_stripped = r.strip()
            if not r_stripped or len(r_stripped) < 2:
                continue

            # 시/도 판별
            if r_stripped in PROVINCES or r_stripped.rstrip("도") in PROVINCES:
                province_list.append(r_stripped)
                # 접미사 제거 버전
                if r_stripped.endswith("도"):
                    base = r_stripped[:-1]
                    if base and base not in province_list:
                        province_list.append(base)
                continue

            # 시 (OO시)
            if r_stripped.endswith("시"):
                city_list.append(r_stripped)
                base = r_stripped[:-1]
                if len(base) >= 2 and base not in city_list:
                    city_list.append(base)
                continue

            # 구 (OO구)
            if r_stripped.endswith("구"):
                gu_list.append(r_stripped)
                base = r_stripped[:-1]
                if len(base) >= 2 and base not in gu_list:
                    gu_list.append(base)
                continue

            # 동 (OO동)
            if r_stripped.endswith("동"):
                base = r_stripped[:-1]
                dong_list.append(r_stripped)
                if len(base) >= 2 and base not in dong_list:
                    dong_list.append(base)
                # 중복 동 판별
                if r_stripped in self.DUPLICATE_DONG_NAMES or base in self.DUPLICATE_DONG_NAMES:
                    duplicate_dong_list.append(r_stripped)
                    if len(base) >= 2:
                        duplicate_dong_list.append(base)
                else:
                    unique_dong_list.append(r_stripped)
                    if len(base) >= 2:
                        unique_dong_list.append(base)
                continue

            # 역 (OO역)
            if r_stripped.endswith("역"):
                station_list.append(r_stripped)
                base = r_stripped[:-1]
                if len(base) >= 2 and base not in station_list:
                    station_list.append(base)
                continue

            # 도로명 (OO로, OO길)
            if r_stripped.endswith("로") or r_stripped.endswith("길"):
                road_list.append(r_stripped)
                continue

            # 기타 (접미사 없는 지역명) - 컨텍스트에 따라 시/구로 분류
            # 2글자는 보통 시급 (평택, 고양, 일산 등)
            if len(r_stripped) == 2:
                if r_stripped not in city_list:
                    city_list.append(r_stripped)
            else:
                if r_stripped not in gu_list:
                    gu_list.append(r_stripped)

        # === 1단계: 단독 사용 가능한 지역 추가 ===
        # 시/도는 단독 사용 X
        for city in city_list:
            result.add(city)
        for gu in gu_list:
            result.add(gu)
        for dong in unique_dong_list:  # 유일한 동만
            result.add(dong)
        for station in station_list:
            result.add(station)
        # 도로명, 중복동은 단독 사용 X

        # === 2단계: 2개 조합 ===
        all_combos = set()

        # 시/도 + 시 (경기 평택, 경기 평택시)
        for prov in province_list:
            for city in city_list:
                if prov != city:
                    combo = f"{prov} {city}"
                    result.add(combo)
                    all_combos.add(combo)

        # 시/도 + 구 (경기 일산동구)
        for prov in province_list:
            for gu in gu_list:
                combo = f"{prov} {gu}"
                result.add(combo)
                all_combos.add(combo)

        # 시/도 + 동 (경기 고덕동) - 모든 동
        for prov in province_list:
            for dong in dong_list:
                combo = f"{prov} {dong}"
                result.add(combo)
                all_combos.add(combo)

        # 시 + 구 (고양 일산동구, 고양시 일산동)
        for city in city_list:
            for gu in gu_list:
                if city != gu and city not in gu:
                    combo = f"{city} {gu}"
                    result.add(combo)
                    all_combos.add(combo)

        # 시 + 동 (평택 고덕, 평택시 고덕동) - 모든 동
        for city in city_list:
            for dong in dong_list:
                if city != dong:
                    combo = f"{city} {dong}"
                    result.add(combo)
                    all_combos.add(combo)

        # 구 + 동 (일산동구 장항, 일산 장항동)
        for gu in gu_list:
            for dong in dong_list:
                if gu != dong and dong not in gu:
                    combo = f"{gu} {dong}"
                    result.add(combo)
                    all_combos.add(combo)

        # 시 + 역 (고양 정발산역)
        for city in city_list:
            for station in station_list:
                combo = f"{city} {station}"
                result.add(combo)
                all_combos.add(combo)

        # 구 + 역 (일산 정발산역)
        for gu in gu_list:
            for station in station_list:
                combo = f"{gu} {station}"
                result.add(combo)
                all_combos.add(combo)

        # 시/도 + 역 (경기 정발산역)
        for prov in province_list:
            for station in station_list:
                combo = f"{prov} {station}"
                result.add(combo)
                all_combos.add(combo)

        # 시 + 도로명 (고양 중앙로)
        for city in city_list:
            for road in road_list:
                combo = f"{city} {road}"
                result.add(combo)
                all_combos.add(combo)

        # === 3단계: 3개 조합 (주요 조합만) ===
        # 시/도 + 시 + 동 (경기 평택 고덕)
        for prov in province_list[:2]:  # 상위 2개
            for city in city_list[:3]:  # 상위 3개
                for dong in dong_list[:4]:  # 상위 4개
                    if prov != city and city != dong:
                        combo = f"{prov} {city} {dong}"
                        result.add(combo)
                        all_combos.add(combo)

        # 시 + 구 + 동 (고양 일산 장항)
        for city in city_list[:3]:
            for gu in gu_list[:3]:
                for dong in dong_list[:4]:
                    if city != gu and gu != dong and city != dong:
                        combo = f"{city} {gu} {dong}"
                        result.add(combo)
                        all_combos.add(combo)

        # === 4단계: 모든 조합 + 수식어 ===
        # 단독 지역 + 수식어
        for city in city_list:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{city} {suffix}")

        for gu in gu_list:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{gu} {suffix}")

        for dong in unique_dong_list:  # 유일한 동만
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{dong} {suffix}")

        for station in station_list:
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{station} {suffix}")
                if station.endswith("역"):
                    result.add(f"{station}{suffix}")  # 붙여쓰기

        # 2개 조합 + 수식어 (주요 조합만)
        combo_list = list(all_combos)
        for combo in combo_list[:50]:  # 상위 50개 조합
            for suffix in self.LOCATION_SUFFIXES:
                result.add(f"{combo} {suffix}")

        return list(result)

    def _generate_region_keyword_combinations(self, base_regions: list, keywords: list) -> list:
        """
        지역 + 키워드 조합 생성

        순서:
        1. 지역 + 키워드 조합 (강남 삼겹살, 압구정 와인바)
        2. 지역 + 키워드 + 근처/주변 (강남 삼겹살 근처, 압구정 와인바 주변)

        Args:
            base_regions: 기본 지역명 리스트 (강남, 압구정역, 신사동 등)
            keywords: 키워드 리스트 (삼겹살, 와인바, 카페 등)

        Returns:
            지역+키워드 조합 리스트
        """
        result = []

        # 지역 필터링 - 단독 사용 가능한 지역만 (시/도 제외)
        PROVINCES = {"서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
                     "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"}

        usable_regions = []
        for r in base_regions:
            r_stripped = r.strip()
            if not r_stripped or len(r_stripped) < 2:
                continue
            # 시/도 단독은 제외
            if r_stripped in PROVINCES or r_stripped.rstrip("도") in PROVINCES:
                continue
            usable_regions.append(r_stripped)

        # 중복 제거
        usable_regions = list(dict.fromkeys(usable_regions))

        # 키워드 필터링 - 상위 키워드만 사용 (너무 많으면 조합 폭발)
        top_keywords = keywords[:15]  # 상위 15개

        # 1단계: 지역 + 키워드 조합
        region_kw_combos = []
        for region in usable_regions[:10]:  # 상위 10개 지역
            for kw in top_keywords:
                combo = f"{region} {kw}"
                if combo not in region_kw_combos:
                    region_kw_combos.append(combo)

        result.extend(region_kw_combos)

        # 2단계: 지역 + 근처/주변 + 키워드 (수식어가 지역 바로 뒤에 위치)
        # 예: "강남 근처 삼겹살", "압구정 가까운 와인바"
        suffix_combos_count = 0
        for region in usable_regions[:10]:
            for kw in top_keywords[:8]:  # 상위 8개 키워드 (조합 수 조절)
                for suffix in self.LOCATION_SUFFIXES:
                    combo = f"{region} {suffix} {kw}"
                    if combo not in result:
                        result.append(combo)
                        suffix_combos_count += 1

        print(f"[PlaceExtractWorker] 지역+키워드 조합: {len(region_kw_combos)}개, +수식어: {len(result) - len(region_kw_combos)}개")
        return result

    def _parse_business_name_morphemes(self, name, category: str = ""):
        """
        상호명 형태소 분석 및 조합 생성 (브랜드명 변형만)
        예: "르글라스 압구정점" → ["르글라스", "르글", "르글라스압구정", "르글라스압구정점"]

        Gemini AI가 활성화된 경우 AI 분석 결과만 사용 (업종/지역 키워드 제외)
        AI 실패 시에만 규칙 기반 fallback 사용
        """
        # Gemini AI 사용 시도 (상호명 변형 전용)
        try:
            if self.gemini_client.is_available():
                ai_variations = self.gemini_client.parse_business_name_variations(name, category)
                if ai_variations:
                    print(f"[PlaceExtractWorker] AI 상호명 변형: {ai_variations}")
                    return ai_variations
        except Exception as e:
            print(f"[PlaceExtractWorker] AI 상호명 변형 생성 실패: {e}")

        # AI 실패 시 규칙 기반 fallback
        print(f"[PlaceExtractWorker] 규칙 기반 상호명 파싱 fallback")
        result = set()
        name_no_space = name.replace(" ", "")

        # 1. 띄어쓰기로 분리된 부분들
        space_parts = [p.strip() for p in name.split() if len(p.strip()) >= 2]

        # 2. 전체 상호명 (띄어쓰기 제거)
        if len(name_no_space) >= 2:
            result.add(name_no_space)

        # 3. 첫번째 부분 (보통 브랜드명)
        if space_parts:
            brand = space_parts[0]
            result.add(brand)
            # 브랜드명 약칭 (2~3글자)
            for length in [2, 3]:
                if len(brand) > length:
                    result.add(brand[:length])

        # 4. 브랜드명 + 지점명 조합 (띄어쓰기 없이)
        if len(space_parts) >= 2:
            for i in range(1, len(space_parts) + 1):
                combo = "".join(space_parts[:i])
                if len(combo) >= 2:
                    result.add(combo)

        # 5. 지점 접미사 제거 버전
        branch_suffixes = ["본점", "지점", "분점", "점"]
        for suffix in branch_suffixes:
            if name_no_space.endswith(suffix) and len(name_no_space) > len(suffix):
                base = name_no_space[:-len(suffix)]
                if len(base) >= 2:
                    result.add(base)

        return list(result)

    def _filter_standalone_keywords(self, keywords):
        """단독 사용 불가 키워드 필터링"""
        filtered = []
        for kw in keywords:
            kw_stripped = kw.strip()
            # 단독 사용 불가 목록에 있고, 다른 단어와 조합되지 않은 경우 제외
            if kw_stripped in self.STANDALONE_BLOCKED:
                continue
            # 공백으로 분리했을 때 마지막 단어만 단독불가인 경우도 체크
            parts = kw_stripped.split()
            if len(parts) >= 2:
                # 조합된 키워드는 OK
                filtered.append(kw_stripped)
            elif kw_stripped not in self.STANDALONE_BLOCKED:
                # 단독 키워드인데 차단 목록에 없으면 OK
                filtered.append(kw_stripped)
        return filtered

    def _is_region_keyword(self, keyword):
        """
        키워드가 지역 키워드인지 판별 (사전 기반 + 패턴 기반)
        - 1순위: 사전의 카테고리 확인 (지역이면 True, 업종/수식어면 False)
        - 2순위: 역, 동, 구, 시 등 지역 접미사 패턴 확인
        """
        kw = keyword.strip()
        if not kw or len(kw) < 2:
            return False

        # 0. 사전 기반 판별 (가장 정확)
        if self.keyword_parser:
            category = self.keyword_parser.word_to_category.get(kw, "")
            if category:
                if category.startswith("지역"):
                    # 지역/역명, 지역/구, 지역/동_역 등
                    return True
                else:
                    # 업종/음식, 수식어/... 등 → 지역 아님
                    return False

        # 1. 지역이 아닌 단어 제외 (오탐 방지 - 사전에 없는 경우)
        non_region_words = {
            # ~리로 끝나지만 지역 아닌 것
            "관리", "피부관리", "체형관리", "두피관리", "모발관리", "처리", "정리", "수리",
            # ~동으로 끝나지만 지역 아닌 것
            "운동", "활동", "이동", "작동", "행동", "감동", "충동", "진동", "변동",
            # ~구로 끝나지만 지역 아닌 것
            "도구", "기구", "연구", "탐구", "추구",
            # ~시로 끝나지만 지역 아닌 것
            "표시", "검시", "진시", "24시",
            # ~면으로 끝나지만 지역 아닌 것 (음식)
            "냉면", "비빔냉면", "물냉면", "평양냉면", "함흥냉면", "밀면", "막국수면", "쫄면",
            "라면", "짜장면", "짬뽕면", "우동면", "소바면", "국수면", "칼국수면", "수제비면",
            "볶음면", "비빔면", "잔치국수면", "메밀면",
            # 기타
            "단지", "디지털단지", "산업단지"
        }
        if kw in non_region_words:
            return False

        # 2. 알려진 지역명 약칭 (사전에 없을 수 있는 것들)
        known_region_abbr = {
            "구디", "홍대", "잠실", "신촌", "이태원", "명동", "을지로", "성수",
            "건대", "왕십리", "합정", "망원", "연남", "상수", "판교", "분당",
            "수지", "동탄", "광교", "위례", "마곡", "청라", "송도", "검단",
            "미사", "일산", "가산", "가산디지털단지", "구로디지털단지",
            "강남", "서초", "송파", "강동", "구로", "금천", "하남"
        }
        if kw in known_region_abbr:
            return True

        # 3. 지역 접미사 패턴 확인 (리 제외 - 오탐 많음)
        region_suffixes = ["역", "동", "구", "시", "군", "읍", "면"]
        for suffix in region_suffixes:
            if kw.endswith(suffix) and len(kw) > len(suffix):
                # 추가 검증: 앞부분이 한글인지
                prefix = kw[:-len(suffix)]
                if len(prefix) >= 1:
                    return True

            # 지역 접미사가 중간에 있는 경우 (선릉역텐동 = 선릉역 + 텐동)
            # 이 경우는 지역+키워드 조합이므로 False
            idx = kw.find(suffix)
            if idx > 0 and idx < len(kw) - len(suffix):
                # 접미사 뒤에 글자가 더 있음 (예: 선릉역텐동, 강남역맛집)
                after_suffix = kw[idx + len(suffix):]
                if len(after_suffix) >= 2:
                    # 뒤에 의미있는 단어가 붙어있음 → 지역+키워드 조합 → 지역 아님
                    return False

        return False

    def _has_non_region_component(self, keyword, known_regions=None):
        """
        키워드가 지역+비지역 조합인지 확인
        예: "신사동맛집" → True (신사동 + 맛집)
            "평택파히타" → True (평택 + 파히타)
            "압구정" → False (순수 지역명)
        """
        kw = keyword.strip()
        if not kw or len(kw) < 3:
            return False

        # 1. 알려진 지역명으로 시작하는지 확인 (평택파히타, 비전동스테이크 등)
        if known_regions:
            for region in known_regions:
                if kw.startswith(region) and len(kw) > len(region):
                    after = kw[len(region):]
                    if len(after) >= 2:  # 지역명 뒤에 2글자 이상 있으면 조합
                        return True

        # 2. 지역 접미사 패턴으로 분리 시도 (신사동맛집 등)
        region_suffixes = ["역", "동", "구"]
        for suffix in region_suffixes:
            idx = kw.find(suffix)
            if idx > 0 and idx < len(kw) - 1:  # 중간에 접미사가 있으면
                after = kw[idx + len(suffix):]
                if len(after) >= 2:
                    # 접미사 뒤에 의미있는 문자열이 있음 (예: 신사동맛집의 "맛집")
                    return True

        # 3. 알려진 수식어가 포함되어 있는지 확인
        modifiers = ["맛집", "맛집추천", "추천", "카페", "술집", "음식점", "병원", "치과", "데이트"]
        for mod in modifiers:
            if mod in kw:
                return True

        return False

    def _extract_region_from_keyword(self, keyword, known_regions=None):
        """
        키워드에서 지역명 추출 (지역+키워드 조합 분리)
        예: "평택파히타" → ("평택", "파히타")
            "비전동스테이크" → ("비전동", "스테이크")
            "선릉역텐동" → ("선릉역", "텐동")
            "강남역맛집" → ("강남역", "맛집")
            "타코" → (None, "타코")
        """
        kw = keyword.strip()
        if not kw:
            return None, kw

        # 1. 알려진 지역명으로 시작하는 경우 (긴 지역명부터 매칭)
        if known_regions:
            sorted_regions = sorted(known_regions, key=len, reverse=True)
            for region in sorted_regions:
                if kw.startswith(region) and len(kw) > len(region):
                    after = kw[len(region):]
                    if len(after) >= 2:
                        return region, after

        # 2. 지역 접미사 패턴으로 분리 (선릉역텐동 → 선릉역 + 텐동)
        region_suffixes = ["역", "동", "구"]
        for suffix in region_suffixes:
            idx = kw.find(suffix)
            if idx > 0 and idx < len(kw) - len(suffix):
                # 접미사 뒤에 글자가 더 있음
                region_part = kw[:idx + len(suffix)]  # 선릉역
                keyword_part = kw[idx + len(suffix):]  # 텐동
                if len(keyword_part) >= 2 and len(region_part) >= 2:
                    return region_part, keyword_part

        return None, kw

    async def _fetch_place_data(self, url: str):
        async with PlaceScraper(headless=True) as scraper:
            return await scraper.get_place_data_by_url(url)

    async def _fetch_booking_info(self, place_id: str) -> dict:
        """GraphQL API로 예약 정보 조회"""
        import httpx

        GRAPHQL_URL = "https://nx-api.place.naver.com/graphql"
        query = """
        query getPlaceDetail($input: PlaceDetailInput) {
            placeDetail(input: $input) {
                naverBooking {
                    naverBookingUrl
                    bookingBusinessId
                }
            }
        }
        """

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    GRAPHQL_URL,
                    json={
                        "operationName": "getPlaceDetail",
                        "query": query,
                        "variables": {"input": {"id": place_id, "deviceType": "mobile"}}
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Referer": "https://m.place.naver.com/",
                        "Origin": "https://m.place.naver.com",
                        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)",
                    }
                )

                if resp.status_code == 200:
                    data = resp.json()
                    detail = data.get("data", {}).get("placeDetail", {})
                    if detail:
                        naver_booking = detail.get("naverBooking") or {}
                        booking_url = naver_booking.get("naverBookingUrl")
                        booking_business_id = naver_booking.get("bookingBusinessId")
                        has_booking = bool(booking_url or booking_business_id)
                        return {
                            "has_booking": has_booking,
                            "booking_type": "realtime" if has_booking else None,
                            "booking_hub_id": booking_business_id,
                            "booking_url": booking_url,
                        }
        except Exception as e:
            print(f"[PlaceExtractWorker] 예약 정보 조회 실패: {e}")

        return {"has_booking": False, "booking_type": None, "booking_hub_id": None, "booking_url": None}

    def _generate_booking_keywords(self, keywords: list, regions: list) -> list:
        """
        신지도 리스트 키워드에 '실시간 예약' 접미사를 붙여 예약 키워드 생성

        예: "강남 맛집" -> "강남 맛집 실시간 예약"
        """
        booking_keywords = []

        # 지역 + 키워드 조합에 '실시간 예약' 추가
        for region in regions[:8]:  # 상위 8개 지역만
            for kw in keywords[:10]:  # 상위 10개 키워드만
                # 이미 예약 관련 단어가 있으면 스킵
                if "예약" in kw:
                    continue
                booking_kw = f"{region} {kw} 실시간 예약"
                if booking_kw not in booking_keywords:
                    booking_keywords.append(booking_kw)

        return booking_keywords[:20]  # 최대 20개


class KeywordWorker(QThread):
    """키워드 생성 작업을 백그라운드에서 실행"""
    finished = pyqtSignal(list)  # 생성된 키워드 목록
    error = pyqtSignal(str)  # 에러 메시지
    progress = pyqtSignal(str)  # 진행 상태

    def __init__(self, url: str, max_keywords: int = 0):
        super().__init__()
        self.url = url
        self.max_keywords = max_keywords  # 0 = 무제한
        
    def run(self):
        import asyncio
        
        try:
            self.progress.emit("URL 파싱 중...")
            
            # 1. URL 파싱
            parsed = parse_place_url(self.url)
            
            if not parsed.is_valid:
                self.error.emit(f"URL 파싱 실패: {parsed.error_message}")
                return
            
            self.progress.emit("플레이스 데이터 수집 중...")
            
            # 2. 플레이스 데이터 수집 (async 함수 실행)
            place_url = f"https://m.place.naver.com/{parsed.place_type.value}/{parsed.mid}"
            place_data = asyncio.run(self._fetch_place_data(place_url))
            
            if not place_data:
                self.error.emit("데이터 수집 실패. 페이지에 접근할 수 없습니다.")
                return
            
            self.progress.emit("키워드 생성 중...")
            
            # 3. 키워드 생성
            generator = KeywordGenerator()
            keywords = generator.generate(place_data)
            
            # 4. 키워드 수 제한 적용
            if self.max_keywords > 0 and len(keywords) > self.max_keywords:
                keywords = keywords[:self.max_keywords]
            
            self.finished.emit(keywords)
            
        except Exception as e:
            import traceback
            self.error.emit(f"오류 발생: {str(e)}\n{traceback.format_exc()}")
    
    async def _fetch_place_data(self, url: str):
        """플레이스 데이터를 비동기로 가져오기"""
        async with PlaceScraper(headless=True) as scraper:
            return await scraper.get_place_data_by_url(url)


class RankWorker(QThread):
    """순위 체크 작업을 백그라운드에서 실행 (2단계 모드)"""
    finished = pyqtSignal(list)  # RankResult 리스트
    error = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)  # current, total, message

    def __init__(self, keywords: list, place_id: str, max_rank: int, target_rank: int = 10, proxies: list = None, user_slot: int = 0, proxy_type: str = "decodo"):
        super().__init__()
        self.keywords = keywords
        self.place_id = place_id
        self.max_rank = max_rank
        self.target_rank = target_rank  # 형태 확인할 순위 기준
        self.proxies = proxies or []
        self.user_slot = user_slot  # 사용자 슬롯 (0=자동분산, 1~4=고정할당)
        self.proxy_type = proxy_type  # 프록시 타입 ("decodo" 또는 "datacenter")

    def run(self):
        try:
            results = self._check_ranks()
            self.finished.emit(results)
        except Exception as e:
            import traceback
            self.error.emit(f"순위 체크 오류: {str(e)}\n{traceback.format_exc()}")

    def _check_ranks(self):
        """순위 체크 실행 (GraphQL API 기반)"""
        proxy_configs = []
        for p in self.proxies:
            proxy_configs.append(ProxyConfig(
                host=p.get("host", ""),
                port=p.get("port", 8080),
                username=p.get("username", ""),
                password=p.get("password", ""),
                proxy_type=p.get("type", "datacenter")  # 프록시 타입 전달 (decodo/datacenter)
            ))

        # settings.json에서 use_own_ip, proxy_type 로드
        use_own_ip = True
        proxy_type = self.proxy_type  # 기본값: 생성자에서 받은 값
        try:
            import json
            settings_path = os.path.join(exe_dir, 'settings.json')
            if os.path.exists(settings_path):
                with open(settings_path, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    use_own_ip = settings.get('use_own_ip', True)
                    proxy_type = settings.get('proxy_type', self.proxy_type)
        except:
            pass

        with RankCheckerGraphQL(
            proxies=proxy_configs if proxy_configs else None,
            use_own_ip=use_own_ip,
            user_slot=self.user_slot,
            proxy_type=proxy_type,
            debug=False
        ) as checker:
            # 진행 상황 콜백 설정
            def progress_callback(current, total, msg):
                self.progress.emit(current, total, msg)

            checker.set_progress_callback(progress_callback)

            # 2단계 모드: 1단계 순위 체크 → 2단계 형태 확인 (순위 이내만)
            return checker.check_keywords_two_phase(
                self.keywords,
                self.place_id,
                self.max_rank,
                self.target_rank
            )


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Naver Place 키워드 추출기 v2.0")
        self.setMinimumSize(750, 600)  # 최소 크기 축소
        self.resize(900, 800)  # 기본 크기
        self.current_category = None
        self.keywords = []
        self.worker = None  # 키워드 생성 백그라운드 작업
        self.rank_worker = None  # 순위 체크 백그라운드 작업
        self.extract_worker = None  # 플레이스 정보 추출 워커
        self.extracted_place_data = None  # 추출된 플레이스 데이터
        self.extracted_region_keyword_combos = []  # 지역+키워드 조합
        self.place_id = ""  # 플레이스 ID

        # 목표 개수 달성형 로직용 변수
        self.target_count = 0  # 목표 순위권 키워드 개수
        self.all_generated_keywords = set()  # 이미 생성된 키워드 (중복 방지)
        self.verified_keywords = set()  # 이미 검증된 키워드
        self.ranked_results = []  # 순위권 내 결과 누적
        self.round_count = 0  # 검증 라운드 수
        self.max_rounds = 3  # 최대 반복 횟수

        # 자동 실행 모드 (런처에서 --auto 옵션으로 실행 시)
        self.auto_mode = False

        self.setup_ui()
        self._load_settings()  # 저장된 설정 로드
        
    def setup_ui(self):
        """UI 구성 - 전체 스크롤 가능"""
        # 메인 스크롤 영역 생성
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f5f5f5;
            }
        """)
        self.setCentralWidget(scroll_area)

        # 스크롤 내부 컨텐츠 위젯
        central_widget = QWidget()
        scroll_area.setWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # === 1. 입력 섹션 ===
        input_group = QGroupBox("입력")
        input_group.setStyleSheet("QGroupBox { font-size: 12px; padding-top: 10px; }")
        input_layout = QVBoxLayout()
        input_layout.setSpacing(5)
        input_layout.setContentsMargins(8, 10, 8, 8)

        # URL 입력 + 추출 버튼
        url_layout = QHBoxLayout()
        url_label = QLabel("URL:")
        url_label.setStyleSheet("font-size: 11px; font-weight: bold;")
        url_layout.addWidget(url_label)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://m.place.naver.com/...")
        self.url_input.setStyleSheet("font-size: 11px;")
        self.url_input.textChanged.connect(self.on_url_changed)
        url_layout.addWidget(self.url_input)

        self.extract_btn = QPushButton("📥 정보 추출")
        self.extract_btn.setMinimumHeight(28)
        self.extract_btn.clicked.connect(self.on_extract_clicked)
        url_layout.addWidget(self.extract_btn)
        input_layout.addLayout(url_layout)

        # 감지된 업종 표시
        category_layout = QHBoxLayout()
        cat_label = QLabel("감지된 업종:")
        cat_label.setStyleSheet("font-size: 11px;")
        category_layout.addWidget(cat_label)
        self.category_label = QLabel("(URL 입력 후 자동 감지)")
        self.category_label.setStyleSheet("font-weight: bold; color: #0066cc; font-size: 11px;")
        category_layout.addWidget(self.category_label)
        category_layout.addStretch()
        input_layout.addLayout(category_layout)

        input_group.setLayout(input_layout)
        main_layout.addWidget(input_group)

        # === 3. 추출된 정보 편집 섹션 (처음엔 숨김) ===
        self.extracted_group = QGroupBox("추출된 정보 (수정 가능)")
        self.extracted_group.setVisible(False)
        self.extracted_group.setStyleSheet("""
            QGroupBox {
                font-size: 12px;
                font-weight: bold;
                padding-top: 12px;
                margin-top: 3px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 3px;
            }
        """)

        extracted_layout = QVBoxLayout()
        extracted_layout.setSpacing(6)
        extracted_layout.setContentsMargins(8, 10, 8, 8)

        # 공통 스타일 (컴팩트)
        label_style = "font-weight: bold; font-size: 11px; min-width: 45px;"

        # === 체크박스 태그 기반 UI ===
        # 전체 선택/해제 버튼
        select_btn_layout = QHBoxLayout()
        select_btn_layout.addStretch()

        self.tag_select_all_btn = QPushButton("전체 선택")
        self.tag_select_all_btn.setMinimumHeight(24)
        self.tag_select_all_btn.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        self.tag_select_all_btn.clicked.connect(self._on_tag_select_all)
        select_btn_layout.addWidget(self.tag_select_all_btn)

        self.tag_deselect_all_btn = QPushButton("전체 해제")
        self.tag_deselect_all_btn.setMinimumHeight(24)
        self.tag_deselect_all_btn.setStyleSheet("font-size: 10px; padding: 2px 8px;")
        self.tag_deselect_all_btn.clicked.connect(self._on_tag_deselect_all)
        select_btn_layout.addWidget(self.tag_deselect_all_btn)

        extracted_layout.addLayout(select_btn_layout)

        # 지역 (태그 컨테이너)
        region_layout = QHBoxLayout()
        region_label = QLabel("지역:")
        region_label.setStyleSheet(label_style)
        region_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        region_layout.addWidget(region_label)
        self.region_tags = TagContainerWidget(category="region")
        region_layout.addWidget(self.region_tags)
        extracted_layout.addLayout(region_layout)

        # 키워드 (태그 컨테이너)
        keyword_layout = QHBoxLayout()
        keyword_label = QLabel("키워드:")
        keyword_label.setStyleSheet(label_style)
        keyword_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        keyword_layout.addWidget(keyword_label)
        self.keyword_tags = TagContainerWidget(category="keyword")
        keyword_layout.addWidget(self.keyword_tags)
        extracted_layout.addLayout(keyword_layout)

        # 상호명 (태그 컨테이너)
        name_layout = QHBoxLayout()
        name_label = QLabel("상호명:")
        name_label.setStyleSheet(label_style)
        name_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        name_layout.addWidget(name_label)
        self.name_tags = TagContainerWidget(category="name")
        name_layout.addWidget(self.name_tags)
        extracted_layout.addLayout(name_layout)

        # 수식어 (태그 컨테이너)
        modifier_layout = QHBoxLayout()
        modifier_label = QLabel("수식어:")
        modifier_label.setStyleSheet(label_style)
        modifier_label.setAlignment(Qt.AlignmentFlag.AlignTop)
        modifier_layout.addWidget(modifier_label)
        self.modifier_tags = TagContainerWidget(category="modifier")
        modifier_layout.addWidget(self.modifier_tags)
        extracted_layout.addLayout(modifier_layout)

        # 하위 호환성을 위해 기존 속성 유지 (deprecated, 태그 위젯 사용 권장)
        self.region_edit = None  # deprecated
        self.keyword_edit = None  # deprecated
        self.name_edit = None  # deprecated
        self.user_modifier_edit = None  # deprecated

        # 예약 (예약 가능 업체만 표시)
        booking_layout = QHBoxLayout()
        self.booking_label = QLabel("🎫 예약:")
        self.booking_label.setStyleSheet(label_style + " color: #d32f2f;")
        booking_layout.addWidget(self.booking_label)

        self.booking_use_check = QCheckBox("")
        self.booking_use_check.setChecked(True)
        self.booking_use_check.setToolTip("신지도 리스트 키워드에 예약 수식어 추가")
        self.booking_use_check.setFixedWidth(20)
        booking_layout.addWidget(self.booking_use_check)

        self.booking_modifier_edit = QLineEdit()
        self.booking_modifier_edit.setText("실시간예약")
        self.booking_modifier_edit.setPlaceholderText("예약 수식어")
        self.booking_modifier_edit.setMinimumHeight(26)
        self.booking_modifier_edit.setStyleSheet("""
            QLineEdit {
                font-size: 11px;
                padding: 3px;
                background-color: #fff8e1;
                border: 1px solid #ffc107;
                border-radius: 3px;
            }
            QLineEdit:focus {
                border: 1px solid #ff9800;
            }
        """)
        booking_layout.addWidget(self.booking_modifier_edit)

        self.booking_layout_widget = QWidget()
        self.booking_layout_widget.setLayout(booking_layout)
        self.booking_layout_widget.setVisible(False)
        extracted_layout.addWidget(self.booking_layout_widget)

        self.extracted_group.setLayout(extracted_layout)
        main_layout.addWidget(self.extracted_group)

        # === 4. 가이드 문구 ===
        self.guide_label = QLabel("💡 URL 입력 → 정보 추출 → 수정 → 키워드 생성 순서로 진행하세요.")
        self.guide_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        main_layout.addWidget(self.guide_label)
        
        # === 4. 순위 필터 & 수식어 설정 (탭 위젯) ===
        self.advanced_tabs = QTabWidget()
        self.advanced_tabs.setStyleSheet("QTabWidget { font-size: 11px; }")

        # 순위 필터 탭
        self.rank_widget = self._create_rank_settings_widget()
        self.advanced_tabs.addTab(self.rank_widget, "📊 순위 필터")

        # 수식어 탭
        self.modifier_widget = self._create_modifier_settings_widget()
        self.advanced_tabs.addTab(self.modifier_widget, "✏️ 수식어")

        main_layout.addWidget(self.advanced_tabs)

        # === 프록시 설정 (한 줄에 배치) ===
        proxy_row = QHBoxLayout()
        self.proxy_status_label = QLabel("프록시: 미사용")
        self.proxy_status_label.setStyleSheet("color: gray; font-size: 11px;")
        proxy_row.addWidget(self.proxy_status_label)

        # 슬롯 선택 (다중 인스턴스 지원)
        slot_label = QLabel("슬롯:")
        slot_label.setStyleSheet("font-size: 11px; margin-left: 15px;")
        proxy_row.addWidget(slot_label)
        self.slot_spin = QSpinBox()
        self.slot_spin.setRange(0, 10)
        self.slot_spin.setValue(0)
        self.slot_spin.setToolTip(
            "다중 인스턴스 실행 시 슬롯 번호 지정\n"
            "0: 전체 프록시 사용 (단독 실행)\n"
            "1~10: 프록시를 10등분하여 해당 슬롯만 사용\n"
            "예) 50개 프록시, 슬롯 3 → 프록시 11~15번만 사용"
        )
        self.slot_spin.setFixedWidth(50)
        proxy_row.addWidget(self.slot_spin)

        proxy_row.addStretch()

        self.proxy_settings_btn = QPushButton("⚙️ 프록시 설정")
        self.proxy_settings_btn.setMinimumHeight(28)
        self.proxy_settings_btn.clicked.connect(self._open_proxy_settings)
        proxy_row.addWidget(self.proxy_settings_btn)

        # Gemini AI 설정 버튼
        self.gemini_settings_btn = QPushButton("🤖 AI 설정")
        self.gemini_settings_btn.setMinimumHeight(28)
        self.gemini_settings_btn.clicked.connect(self._open_gemini_settings)
        proxy_row.addWidget(self.gemini_settings_btn)

        main_layout.addLayout(proxy_row)

        # 프록시 관련 변수 초기화
        self._init_proxy_variables()
        
        # === 5. 액션 버튼 ===
        action_layout = QHBoxLayout()

        self.generate_btn = QPushButton("🚀 키워드 생성 + 순위 체크")
        self.generate_btn.setMinimumHeight(36)
        self.generate_btn.setStyleSheet("font-size: 12px; font-weight: bold;")
        self.generate_btn.clicked.connect(self.on_generate_clicked)
        action_layout.addWidget(self.generate_btn)

        # 실시간 예약 키워드만 생성 버튼
        self.booking_only_btn = QPushButton("🎫 실시간 예약 키워드만")
        self.booking_only_btn.setMinimumHeight(36)
        self.booking_only_btn.setStyleSheet("font-size: 11px; font-weight: bold; background-color: #FF9800; color: white;")
        self.booking_only_btn.clicked.connect(self.on_booking_only_clicked)
        self.booking_only_btn.setToolTip("순위 체크 없이 실시간 예약 키워드만 생성")
        action_layout.addWidget(self.booking_only_btn)

        # 계속 버튼 (Phase 1 후 편집 완료 시 표시)
        self.continue_btn = QPushButton("▶️ 계속 진행")
        self.continue_btn.setMinimumHeight(36)
        self.continue_btn.setStyleSheet("font-size: 12px; font-weight: bold; background-color: #4CAF50; color: white;")
        self.continue_btn.clicked.connect(self.on_continue_clicked)
        self.continue_btn.setVisible(False)
        action_layout.addWidget(self.continue_btn)

        # 중단 버튼
        self.stop_btn = QPushButton("⏹️ 중단")
        self.stop_btn.setMinimumHeight(36)
        self.stop_btn.setStyleSheet("font-size: 12px; font-weight: bold; background-color: #f44336; color: white;")
        self.stop_btn.clicked.connect(self.on_stop_clicked)
        self.stop_btn.setVisible(False)
        action_layout.addWidget(self.stop_btn)

        main_layout.addLayout(action_layout)
        
        # 진행바
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setRange(0, 0)  # 무한 진행바
        main_layout.addWidget(self.progress_bar)
        
        # === 6. 결과 테이블 ===
        result_group = QGroupBox("결과 키워드")
        result_layout = QVBoxLayout()
        
        # 상단 정보 + 버튼
        result_top_layout = QHBoxLayout()
        self.result_count_label = QLabel("총 0개")
        self.result_count_label.setStyleSheet("font-weight: bold;")
        result_top_layout.addWidget(self.result_count_label)
        result_top_layout.addStretch()
        
        self.select_all_btn = QPushButton("전체 선택")
        self.select_all_btn.clicked.connect(self.on_select_all)
        result_top_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("전체 해제")
        self.deselect_all_btn.clicked.connect(self.on_deselect_all)
        result_top_layout.addWidget(self.deselect_all_btn)
        
        result_layout.addLayout(result_top_layout)
        
        # 테이블 (4열: 포함, 키워드, 순위, 지도형태)
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(4)
        self.result_table.setHorizontalHeaderLabels(["포함", "키워드", "순위", "형태"])
        self.result_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.result_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.result_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self.result_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.result_table.setColumnWidth(0, 40)
        self.result_table.setColumnWidth(2, 50)
        self.result_table.setColumnWidth(3, 55)
        self.result_table.setMinimumHeight(150)
        self.result_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # 테이블 스타일링
        self.result_table.setStyleSheet("""
            QTableWidget {
                font-size: 12px;
                gridline-color: #ddd;
                alternate-background-color: #f9f9f9;
            }
            QTableWidget::item {
                padding: 6px;
            }
            QHeaderView::section {
                background-color: #4a90d9;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 8px;
                border: none;
            }
            QTableWidget::item:selected {
                background-color: #e3f2fd;
                color: black;
            }
        """)
        self.result_table.setAlternatingRowColors(True)
        self.result_table.verticalHeader().setDefaultSectionSize(32)  # 행 높이
        result_layout.addWidget(self.result_table)
        
        result_group.setLayout(result_layout)
        main_layout.addWidget(result_group)
        
        # === 7. 하단 영역: 복사 형식 + 버튼 ===
        bottom_layout = QVBoxLayout()
        bottom_layout.setSpacing(5)

        # 복사 형식 라디오 버튼
        format_layout = QHBoxLayout()
        format_label = QLabel("복사 형식:")
        format_label.setStyleSheet("font-size: 11px;")
        format_layout.addWidget(format_label)

        self.radio_comma = QRadioButton("쉼표 구분")
        self.radio_newline = QRadioButton("줄바꿈")
        self.radio_tab_rank = QRadioButton("탭+순위")
        self.radio_comma.setStyleSheet("font-size: 11px;")
        self.radio_newline.setStyleSheet("font-size: 11px;")
        self.radio_tab_rank.setStyleSheet("font-size: 11px;")
        self.radio_newline.setChecked(True)

        format_layout.addWidget(self.radio_comma)
        format_layout.addWidget(self.radio_newline)
        format_layout.addWidget(self.radio_tab_rank)
        format_layout.addStretch()

        bottom_layout.addLayout(format_layout)

        # 버튼 레이아웃 (컴팩트)
        btn_layout = QHBoxLayout()

        self.copy_btn = QPushButton("📋 복사")
        self.copy_btn.setMinimumHeight(30)
        self.copy_btn.clicked.connect(self.on_copy_clicked)
        btn_layout.addWidget(self.copy_btn)

        # 분할 복사
        split_label = QLabel("분할:")
        split_label.setStyleSheet("font-size: 11px;")
        btn_layout.addWidget(split_label)
        self.split_copy_combo = QComboBox()
        self.split_copy_combo.addItem("전체", 0)
        self.split_copy_combo.setMinimumWidth(80)
        self.split_copy_combo.setMinimumHeight(30)
        btn_layout.addWidget(self.split_copy_combo)

        self.split_copy_btn = QPushButton("📋 분할 복사")
        self.split_copy_btn.setMinimumHeight(30)
        self.split_copy_btn.clicked.connect(self.on_split_copy_clicked)
        self.split_copy_btn.setToolTip("200개 단위로 나눠서 복사")
        btn_layout.addWidget(self.split_copy_btn)

        self.save_btn = QPushButton("💾 저장")
        self.save_btn.setMinimumHeight(30)
        self.save_btn.clicked.connect(self.on_save_clicked)
        btn_layout.addWidget(self.save_btn)

        bottom_layout.addLayout(btn_layout)

        main_layout.addLayout(bottom_layout)
        
        # === 상태바 ===
        self.statusBar().showMessage("준비됨 - 플레이스 URL을 입력하세요")
        
    def _create_rank_settings_widget(self):
        """순위 필터 설정 (탭용 위젯)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # 순위 범위 설정 (최소~최대)
        rank_range_layout = QHBoxLayout()
        rank_range_layout.addWidget(QLabel("순위 범위:"))
        self.min_rank_combo = QComboBox()
        self.min_rank_combo.addItems([str(i) + "위" for i in range(1, 51)])
        self.min_rank_combo.setCurrentIndex(0)  # 기본 1위
        self.min_rank_combo.setToolTip("최소 순위 (이 순위 이상만 포함)")
        rank_range_layout.addWidget(self.min_rank_combo)
        rank_range_layout.addWidget(QLabel("~"))
        self.max_rank_combo = QComboBox()
        self.max_rank_combo.addItems([str(i) + "위" for i in range(1, 51)])
        self.max_rank_combo.setCurrentIndex(19)  # 기본 20위
        self.max_rank_combo.setToolTip("최대 순위 (이 순위 이하만 포함)")
        rank_range_layout.addWidget(self.max_rank_combo)
        rank_range_layout.addStretch()
        layout.addLayout(rank_range_layout)
        
        # 키워드 개수 설정
        keyword_count_layout = QHBoxLayout()
        keyword_count_layout.addWidget(QLabel("목표 키워드 수:"))
        self.target_count_spin = QSpinBox()
        self.target_count_spin.setRange(5, 500)
        self.target_count_spin.setValue(30)
        self.target_count_spin.setToolTip("이 개수만큼 순위권 키워드를 찾을 때까지 계속 탐색합니다.")
        keyword_count_layout.addWidget(self.target_count_spin)
        keyword_count_layout.addStretch()
        layout.addLayout(keyword_count_layout)
        
        self.exclude_no_rank_check = QCheckBox("미노출 키워드 제외")
        self.exclude_no_rank_check.setChecked(True)
        layout.addWidget(self.exclude_no_rank_check)

        # 기본 조합만 생성 옵션 (R1-R2만, 확장 조합 제외)
        self.basic_only_check = QCheckBox("기본 조합만 생성 (빠른 모드)")
        self.basic_only_check.setChecked(False)
        self.basic_only_check.setToolTip(
            "체크 시: 지역+키워드, 지역+키워드+수식어 조합만 생성 (빠름)\n"
            "해제 시: 다중 키워드 조합, 상호명 조합 등 모든 조합 생성"
        )
        layout.addWidget(self.basic_only_check)

        layout.addStretch()
        return widget

    def _init_proxy_variables(self):
        """프록시 관련 변수 초기화"""
        # 프록시 데이터 저장용
        self.proxy_data = {
            "use_proxy": False,
            "use_own_ip": True,
            "decodo_username": "",
            "decodo_password": "",
            "decodo_endpoint_count": 50,
            "proxies": []  # [{"host": "...", "port": ..., "type": "decodo/datacenter"}, ...]
        }
        self.proxy_csv_path = ""

        # Gemini AI 설정
        self.gemini_settings = {
            "use_gemini": False,
            "gemini_api_key": "",
            "gemini_name_parse": True,
            "gemini_related_kw": True
        }

    def _open_proxy_settings(self):
        """프록시 설정 다이얼로그 열기"""
        dialog = ProxySettingsDialog(self.proxy_data, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.proxy_data = dialog.get_data()
            self._update_proxy_status()
            self._save_settings()

    def _open_gemini_settings(self):
        """Gemini AI 설정 다이얼로그 열기"""
        dialog = GeminiSettingsDialog(self.gemini_settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.gemini_settings = dialog.get_settings()
            self._init_gemini_client()
            self._save_settings()

    def _init_gemini_client(self):
        """Gemini 클라이언트 초기화"""
        if self.gemini_settings.get("use_gemini") and self.gemini_settings.get("gemini_api_key"):
            try:
                from src.gemini_client import init_gemini
                success = init_gemini(self.gemini_settings["gemini_api_key"])
                if success:
                    print("[MainWindow] Gemini AI 활성화됨")
                else:
                    print("[MainWindow] Gemini AI 초기화 실패")
            except Exception as e:
                print(f"[MainWindow] Gemini 초기화 오류: {e}")

    def _update_proxy_status(self):
        """프록시 상태 라벨 업데이트"""
        if not self.proxy_data["use_proxy"]:
            self.proxy_status_label.setText("프록시: 미사용")
            self.proxy_status_label.setStyleSheet("color: gray; font-size: 12px;")
        else:
            proxy_count = len(self.proxy_data["proxies"])
            decodo_count = sum(1 for p in self.proxy_data["proxies"] if p.get("type", "").lower() == "decodo")
            dc_count = proxy_count - decodo_count

            parts = [f"프록시: {proxy_count}개"]
            if decodo_count > 0:
                parts.append(f"Decodo:{decodo_count}")
            if dc_count > 0:
                parts.append(f"DC:{dc_count}")

            self.proxy_status_label.setText(" | ".join(parts))
            self.proxy_status_label.setStyleSheet("color: #1976d2; font-weight: bold; font-size: 12px;")

    def _get_proxies(self):
        """프록시 목록 반환"""
        proxies = []
        decodo_username = self.proxy_data.get("decodo_username", "")
        decodo_password = self.proxy_data.get("decodo_password", "")

        for p in self.proxy_data.get("proxies", []):
            proxy_type = p.get("type", "datacenter").lower()
            proxies.append({
                "host": p.get("host", ""),
                "port": p.get("port", 0),
                "type": proxy_type,
                "username": decodo_username if proxy_type == "decodo" else "",
                "password": decodo_password if proxy_type == "decodo" else "",
            })
        return proxies

    def _create_modifier_settings_widget(self):
        """수식어 설정 (탭용 위젯)"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # 기본 수식어 정의 (키 이름은 SmartWorker와 일치해야 함)
        self.default_modifiers = {
            "맛집": ["맛집", "음식점", "식당"],            # 업종 대표 키워드 (restaurant)
            "병원": ["병원", "의원", "병의원"],            # 업종 대표 키워드 (hospital)
            "추천": ["잘하는곳", "유명한곳", "잘하는"],    # GUI 수식어
            "특징": ["주차", "예약", "24시", "야간", "주말"]  # GUI 수식어 (특징)
        }
        # 카테고리 드롭다운 표시용 매핑
        self._modifier_display_names = {
            "맛집": "맛집 (업종 대표 키워드)",
            "병원": "병원 (업종 대표 키워드)",
            "추천": "추천 (GUI 수식어)",
            "특징": "특징 (GUI 수식어)",
        }

        # 현재 수식어 (편집 가능)
        self.current_modifiers = {k: list(v) for k, v in self.default_modifiers.items()}

        # 카테고리 선택 (표시명은 보기 좋게, 내부 키는 SmartWorker 호환)
        cat_layout = QHBoxLayout()
        cat_layout.addWidget(QLabel("카테고리:"))
        self.modifier_category_combo = QComboBox()
        self._modifier_keys = list(self.default_modifiers.keys())  # 내부 키 순서 보존
        for key in self._modifier_keys:
            display = self._modifier_display_names.get(key, key)
            self.modifier_category_combo.addItem(display, key)  # data = 내부 키
        self.modifier_category_combo.currentIndexChanged.connect(self._on_modifier_category_index_changed)
        cat_layout.addWidget(self.modifier_category_combo)
        cat_layout.addStretch()

        # 초기화 버튼
        reset_btn = QPushButton("🔄 초기화")
        reset_btn.setMaximumWidth(80)
        reset_btn.clicked.connect(self._reset_modifiers)
        cat_layout.addWidget(reset_btn)
        layout.addLayout(cat_layout)

        # 수식어 입력 영역
        self.modifier_edit = QLineEdit()
        self.modifier_edit.setPlaceholderText("쉼표로 구분하여 입력 (예: 추천, 잘하는곳, 유명한)")
        self.modifier_edit.textChanged.connect(self._on_modifier_text_changed)
        layout.addWidget(self.modifier_edit)

        # 안내 라벨
        hint_label = QLabel("💡 '지도', '추천'은 자동 포함됩니다. 수식어 수정 후 자동 저장됩니다.")
        hint_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(hint_label)

        layout.addStretch()

        # 초기값 표시
        self._on_modifier_category_index_changed(0)

        return widget

    def _on_modifier_category_index_changed(self, index: int):
        """수식어 카테고리 변경 시 (인덱스 기반)"""
        category = self.modifier_category_combo.currentData()  # 내부 키
        if category and category in self.current_modifiers:
            modifiers = self.current_modifiers[category]
            self.modifier_edit.blockSignals(True)
            self.modifier_edit.setText(",".join(modifiers))
            self.modifier_edit.blockSignals(False)

    def _on_modifier_text_changed(self, text: str):
        """수식어 텍스트 변경 시"""
        category = self.modifier_category_combo.currentData()  # 내부 키
        if category:
            # 쉼표로 분리하고 공백 제거
            modifiers = [m.strip() for m in text.split(",") if m.strip()]
            self.current_modifiers[category] = modifiers
            self._save_settings()

    def _reset_modifiers(self):
        """수식어 초기화"""
        self.current_modifiers = {k: list(v) for k, v in self.default_modifiers.items()}
        self._on_modifier_category_index_changed(self.modifier_category_combo.currentIndex())
        self._save_settings()

    def _get_modifiers(self) -> dict:
        """현재 수식어 반환"""
        return self.current_modifiers

    def _get_proxies(self):
        """proxy_data에서 프록시 목록 추출 (타입별 인증 정보 포함)"""
        proxies = []

        # Decodo 인증 정보 가져오기
        decodo_username = self.proxy_data.get("decodo_username", "").strip()
        decodo_password = self.proxy_data.get("decodo_password", "").strip()

        for p in self.proxy_data.get("proxies", []):
            host = p.get("host", "")
            port = p.get("port", 0)
            proxy_type = p.get("type", "datacenter").lower()

            if not host or not port:
                continue

            # Decodo 타입만 인증 정보 포함
            if proxy_type == "decodo":
                username = decodo_username
                password = decodo_password
            else:
                username = ""
                password = ""

            proxies.append({
                "host": host,
                "port": int(port),
                "type": proxy_type,
                "username": username,
                "password": password,
                "session_type": p.get("session_type", "rotating"),  # rotating 또는 sticky
            })

        return proxies
    
    def _save_settings(self):
        """설정을 JSON 파일로 저장"""
        import json

        # proxy_data에서 직접 읽기
        settings = {
            "proxy_csv_path": getattr(self, 'proxy_csv_path', ''),
            "use_proxy": self.proxy_data.get("use_proxy", False),
            "use_own_ip": self.proxy_data.get("use_own_ip", True),
            "modifiers": getattr(self, 'current_modifiers', None),
            "modifier_version": 2,  # v2: 업종대표키워드 체계 (맛집/음식점/식당)
            # Decodo 설정
            "decodo_username": self.proxy_data.get("decodo_username", ""),
            "decodo_password": self.proxy_data.get("decodo_password", ""),
            "decodo_endpoint_count": self.proxy_data.get("decodo_endpoint_count", 50),
            # 프록시 리스트 (proxy_data에서 직접)
            "proxy_list": self.proxy_data.get("proxies", []),
            # Gemini AI 설정
            "use_gemini": self.gemini_settings.get("use_gemini", False),
            "gemini_api_key": self.gemini_settings.get("gemini_api_key", ""),
            "gemini_name_parse": self.gemini_settings.get("gemini_name_parse", True),
            "gemini_related_kw": self.gemini_settings.get("gemini_related_kw", True),
        }
        try:
            settings_path = os.path.join(exe_dir, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"설정 저장 실패: {e}")
    
    def _load_settings(self):
        """JSON 파일에서 설정 로드"""
        import json
        settings_path = os.path.join(exe_dir, "settings.json")

        if not os.path.exists(settings_path):
            return

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)

            # proxy_data에 직접 로드
            self.proxy_data["use_proxy"] = settings.get("use_proxy", False)
            self.proxy_data["use_own_ip"] = settings.get("use_own_ip", True)
            self.proxy_data["decodo_username"] = settings.get("decodo_username", "")
            self.proxy_data["decodo_password"] = settings.get("decodo_password", "")
            self.proxy_data["decodo_endpoint_count"] = settings.get("decodo_endpoint_count", 50)

            # 저장된 프록시 목록 로드
            saved_proxies = settings.get("proxy_list", [])
            self.proxy_data["proxies"] = []
            for proxy in saved_proxies:
                ip = proxy.get("host", "")
                port = proxy.get("port", "")
                proxy_type = proxy.get("type", "datacenter")
                session_type = proxy.get("session_type", "rotating")

                if not ip or not port:
                    continue

                self.proxy_data["proxies"].append({
                    "host": ip,
                    "port": int(port),
                    "type": proxy_type.lower(),
                    "session_type": session_type  # Sticky/Rotating 구분
                })

            if saved_proxies:
                first_session_type = saved_proxies[0].get("session_type", "rotating")
                print(f"[Settings] 프록시 로드: {len(self.proxy_data['proxies'])}개 ({first_session_type} 모드)")

            # CSV 경로 (참고용)
            csv_path = settings.get("proxy_csv_path", "")
            if csv_path:
                self.proxy_csv_path = csv_path

            # 프록시 상태 라벨 업데이트
            self._update_proxy_status()

            # 수식어 로드 (버전 마이그레이션 포함)
            saved_modifiers = settings.get("modifiers")
            modifier_version = settings.get("modifier_version", 0)
            if saved_modifiers and hasattr(self, 'current_modifiers'):
                if modifier_version >= 2:
                    # v2 이상: 새 형식 (업종대표키워드 체계) → 그대로 로드
                    self.current_modifiers.update(saved_modifiers)
                else:
                    # v0/v1 (이전 형식): 기본값 유지, 저장 시 새 버전으로 덮어씀
                    print(f"[Settings] 수식어 v{modifier_version} → v2 마이그레이션: 기본값으로 초기화")
                # UI 업데이트
                if hasattr(self, 'modifier_category_combo'):
                    self._on_modifier_category_index_changed(self.modifier_category_combo.currentIndex())

            # Gemini AI 설정 로드
            self.gemini_settings["use_gemini"] = settings.get("use_gemini", False)
            self.gemini_settings["gemini_api_key"] = settings.get("gemini_api_key", "")
            self.gemini_settings["gemini_name_parse"] = settings.get("gemini_name_parse", True)
            self.gemini_settings["gemini_related_kw"] = settings.get("gemini_related_kw", True)

            # Gemini 클라이언트 초기화
            if self.gemini_settings.get("use_gemini"):
                self._init_gemini_client()

        except Exception as e:
            print(f"설정 로드 실패: {e}")

    # === 이벤트 핸들러 ===
    
    def on_url_changed(self, url):
        """URL 입력 시 자동 업종 감지"""
        url = url.strip().lower()

        if not url:
            self.category_label.setText("(URL 입력 후 자동 감지)")
            self.current_category = None
            return

        if "/restaurant/" in url:
            self.current_category = "restaurant"
            self.category_label.setText("🍽️ 맛집")
        elif "/hospital/" in url or "/pet/" in url:
            self.current_category = "hospital"
            self.category_label.setText("🏥 병의원")
        elif "/place/" in url:
            self.current_category = "general"
            self.category_label.setText("🏢 일반")
        else:
            self.current_category = "general"
            self.category_label.setText("🏢 일반 (자동 감지)")

        self.statusBar().showMessage(f"업종 감지됨: {self.category_label.text()}")

        # URL 변경 시 추출된 데이터 초기화
        self.extracted_place_data = None
        self.extracted_region_keyword_combos = []
        self.extracted_group.setVisible(False)

    def on_extract_clicked(self):
        """정보 추출 버튼 클릭"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "경고", "플레이스 URL을 입력해주세요.")
            return

        # Playwright 설치 확인
        if not ensure_playwright_installed(self):
            return

        self.extract_btn.setEnabled(False)
        self.extract_btn.setText("⏳ 추출 중...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # 무한 진행바
        self.statusBar().showMessage("플레이스 정보 추출 중... (10~20초 소요)")

        self.extract_worker = PlaceExtractWorker(url)
        self.extract_worker.finished.connect(self.on_extract_finished)
        self.extract_worker.error.connect(self.on_extract_error)
        self.extract_worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        self.extract_worker.start()

    def on_extract_finished(self, result: dict):
        """정보 추출 완료"""
        # UI 리셋
        self.extract_btn.setEnabled(True)
        self.extract_btn.setText("📥 정보 추출")
        self.progress_bar.setVisible(False)

        # 추출된 데이터 저장
        self.extracted_place_data = result.get("place_data")
        self.extracted_region_keyword_combos = result.get("region_keyword_combos", [])
        self.extracted_region_combinations = result.get("region_combinations", [])  # 백엔드용 지역 조합

        # UI에 데이터 채우기
        regions = result.get("regions", [])
        keywords = result.get("keywords", [])
        name_parts = result.get("name_parts", [])
        modifiers = result.get("modifiers", [])

        # 태그 컨테이너에 데이터 설정
        self.region_tags.set_tags(regions, checked=True)
        self.keyword_tags.set_tags(keywords, checked=True)
        self.name_tags.set_tags(name_parts, checked=True)
        self.modifier_tags.set_tags(modifiers, checked=False)  # 수식어 기본 해제 (지도/추천은 자동 포함)

        # AI 키워드 분해 결과 추가 (분해된 키워드는 다른 색상으로 표시)
        decomposed_keywords = result.get("decomposed_keywords", [])
        if decomposed_keywords:
            # 기존 키워드에 없는 분해 키워드만 추가
            existing_keywords = set(keywords)
            for dk in decomposed_keywords:
                if dk not in existing_keywords:
                    self.keyword_tags.add_tag(dk, checked=True, is_decomposed=True)

        # 예약 수식어 설정 표시 (예약 기능이 있을 때만)
        has_booking = result.get("has_booking", False)
        if has_booking:
            booking_type = result.get("booking_type", "")
            booking_type_str = "네이버예약" if booking_type == "realtime" else "외부예약"
            self.booking_label.setText(f"🎫 예약({booking_type_str}):")
            self.booking_layout_widget.setVisible(True)
            # 레이아웃 강제 업데이트
            self.booking_layout_widget.updateGeometry()
        else:
            self.booking_layout_widget.setVisible(False)

        # 업종 표시
        category = result.get("category", "")
        name = result.get("name", "")
        self.category_label.setText(f"{category} - {name}")

        # 편집 영역 표시
        self.extracted_group.setVisible(True)

        # 상태 메시지 (예약 기능 표시)
        status_msg = f"✅ {name} 정보 추출 완료"
        if has_booking:
            status_msg += f" (예약 가능)"
        status_msg += " - 수정 후 키워드 생성 버튼을 클릭하세요"
        self.statusBar().showMessage(status_msg)

        # 자동 모드: 정보 추출만 완료, 버튼 클릭 대기
        if getattr(self, 'auto_mode', False):
            self.statusBar().showMessage(f"✅ {name} 정보 추출 완료 - '키워드 생성 및 순위 체크' 버튼을 클릭하세요")
            # 자동 진행 안함 - 사용자가 버튼 클릭해야 함

    def on_extract_error(self, error_msg: str):
        """정보 추출 오류"""
        self.extract_btn.setEnabled(True)
        self.extract_btn.setText("📥 정보 추출")
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage(f"❌ 추출 오류")
        QMessageBox.critical(self, "추출 오류", error_msg)

    def on_booking_only_clicked(self):
        """실시간 예약 키워드 생성 (지역+키워드 조합 → 실시간 예약 → 신지도만 필터)"""
        is_auto = getattr(self, 'auto_mode', False) and getattr(self, 'booking_only_mode', False)

        # 추출된 데이터 확인
        if not self.extracted_place_data:
            if is_auto:
                print("[AutoMode] 실시간 예약 스킵: 추출된 데이터 없음")
                self.statusBar().showMessage("✅ 완료 (예약 키워드 생성 조건 불충족)")
                return
            QMessageBox.warning(self, "경고", "먼저 '정보 추출' 버튼을 클릭하여 업체 정보를 추출해주세요.")
            return

        # URL에서 place_id 추출
        url = self.url_input.text().strip()
        parsed = parse_place_url(url)
        if not parsed.is_valid:
            if is_auto:
                print("[AutoMode] 실시간 예약 스킵: 유효하지 않은 URL")
                self.statusBar().showMessage("✅ 완료 (예약 키워드 생성 조건 불충족)")
                return
            QMessageBox.warning(self, "경고", "올바른 네이버 플레이스 URL이 아닙니다.")
            return
        self.place_id = parsed.mid

        # 지역 정보 (선택된 태그만)
        regions = self.region_tags.get_selected()
        if not regions:
            if is_auto:
                print("[AutoMode] 실시간 예약 스킵: 지역 정보 없음")
                self.statusBar().showMessage("✅ 완료 (예약 키워드 생성 조건 불충족)")
                return
            QMessageBox.warning(self, "경고", "지역 정보가 없습니다. 지역 태그를 선택해주세요.")
            return

        # 키워드 정보 (선택된 태그만)
        keywords = self.keyword_tags.get_selected()
        if not keywords:
            if is_auto:
                print("[AutoMode] 실시간 예약 스킵: 키워드 정보 없음")
                self.statusBar().showMessage("✅ 완료 (예약 키워드 생성 조건 불충족)")
                return
            QMessageBox.warning(self, "경고", "키워드 정보가 없습니다. 키워드 태그를 선택해주세요.")
            return

        # 상호명 정보 (선택된 태그만, 제외용)
        name_parts = [n.lower() for n in self.name_tags.get_selected()]

        # 목표 개수
        target_count = self.target_count_spin.value()

        # 1단계: 지역 + 키워드 + "실시간 예약" 조합 생성 (상호명 제외)
        booking_candidates = []
        for region in regions:
            for kw in keywords:
                kw_lower = kw.lower()
                # 상호명 키워드 제외
                is_name_keyword = any(name in kw_lower or kw_lower in name for name in name_parts if name)
                if is_name_keyword:
                    continue
                # 예약 포함 키워드 제외
                if "예약" in kw:
                    continue

                base_kw = f"{region} {kw}"
                booking_kw = f"{base_kw} 실시간 예약"
                booking_candidates.append({
                    "keyword": booking_kw,
                    "base_keyword": base_kw
                })

        if not booking_candidates:
            if is_auto:
                print("[AutoMode] 실시간 예약 스킵: 생성된 후보 키워드 없음")
                self.statusBar().showMessage("✅ 완료 (예약 키워드 후보 없음)")
                return
            QMessageBox.warning(self, "경고", "생성된 키워드가 없습니다.")
            return

        print(f"[실시간예약] {len(booking_candidates)}개 후보 생성 → 순위 체크 시작 (목표: {target_count}개)")
        print(f"[실시간예약] 샘플 키워드: {[c['keyword'] for c in booking_candidates[:5]]}")

        # 프록시 설정
        proxies = self._get_proxies() if self.proxy_data.get("use_proxy", False) else []

        # 최대 순위
        max_rank = self.max_rank_combo.currentIndex() + 1 if hasattr(self, 'max_rank_combo') else 50

        # 버튼 비활성화
        self.generate_btn.setEnabled(False)
        self.booking_only_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, target_count)
        self.statusBar().showMessage(f"🎫 실시간 예약 키워드 순위 체크 중... (목표: {target_count}개)")

        # 플래그 및 데이터 저장
        self.booking_only_mode = True
        self.booking_only_target = target_count
        self.booking_candidates = booking_candidates
        self.booking_results = []
        self.booking_check_index = 0
        self.booking_proxies = proxies
        self.booking_max_rank = max_rank

        # 순차적으로 순위 체크 시작 (목표 개수 도달 시 중단)
        self._check_next_booking_batch()

    def _check_next_booking_batch(self):
        """다음 실시간 예약 키워드 배치 순위 체크 (목표 도달 시 중단)"""
        target_count = self.booking_only_target
        candidates = self.booking_candidates

        # 목표 개수 도달 시 완료
        if len(self.booking_results) >= target_count:
            print(f"[실시간예약] ✅ 목표 {target_count}개 도달! 완료")
            self._finish_booking_check()
            return

        # 후보 소진 시 완료
        if self.booking_check_index >= len(candidates):
            print(f"[실시간예약] 후보 소진. 결과: {len(self.booking_results)}개")
            self._finish_booking_check()
            return

        # 배치 크기 결정 (남은 목표 개수의 2배 정도, 최대 20개)
        remaining = target_count - len(self.booking_results)
        batch_size = min(remaining * 2, 20, len(candidates) - self.booking_check_index)

        batch_keywords = []
        for i in range(batch_size):
            idx = self.booking_check_index + i
            if idx < len(candidates):
                batch_keywords.append(candidates[idx]["keyword"])

        self.booking_check_index += batch_size

        print(f"[실시간예약] 배치 체크: {len(batch_keywords)}개 (진행: {self.booking_check_index}/{len(candidates)}, 결과: {len(self.booking_results)}/{target_count}, max_rank: {self.booking_max_rank})")
        print(f"[실시간예약] 배치 키워드: {batch_keywords[:3]}...")
        self.progress_bar.setValue(len(self.booking_results))
        self.statusBar().showMessage(f"🎫 실시간 예약 순위 체크 중... ({len(self.booking_results)}/{target_count}개 발견)")

        # RankWorker로 배치 순위 체크
        self.booking_rank_worker = RankWorker(
            keywords=batch_keywords,
            place_id=self.place_id,
            max_rank=self.booking_max_rank,
            proxies=self.booking_proxies,
            user_slot=0,
            proxy_type="decodo"
        )
        self.booking_rank_worker.finished.connect(self._on_booking_batch_finished)
        self.booking_rank_worker.error.connect(self._on_booking_batch_error)
        self.booking_rank_worker.start()

    def _on_booking_batch_finished(self, results):
        """실시간 예약 배치 순위 체크 완료"""
        target_count = self.booking_only_target

        # 순위권 + 신지도 + 2위 이하인 키워드만 결과에 추가 (1위는 제외)
        for result in results:
            # 순위 있고 + 2위 이하 + 신지도인 경우만 (1위 제외)
            if result.rank is not None and result.rank > 1 and result.map_type == "신지도":
                self.booking_results.append({
                    "keyword": result.keyword,
                    "rank": result.rank,
                    "map_type": "예약"
                })
                print(f"[실시간예약] ✓ '{result.keyword}' → {result.rank}위 신지도 ({len(self.booking_results)}/{target_count})")
            elif result.rank == 1 and result.map_type == "신지도":
                print(f"[실시간예약] ✗ '{result.keyword}' → 1위 신지도 (1위 제외)")

                # 목표 도달 시 즉시 중단
                if len(self.booking_results) >= target_count:
                    print(f"[실시간예약] ✅ 목표 {target_count}개 도달! 즉시 중단")
                    self._finish_booking_check()
                    return
            elif result.rank is not None:
                print(f"[실시간예약] ✗ '{result.keyword}' → {result.rank}위 but {result.map_type} (스킵)")

        # 다음 배치 체크
        self._check_next_booking_batch()

    def _on_booking_batch_error(self, error_msg):
        """실시간 예약 배치 에러 처리"""
        print(f"[실시간예약] 배치 에러: {error_msg}")
        # 에러 발생해도 현재까지 결과로 완료
        self._finish_booking_check()

    def _finish_booking_check(self):
        """실시간 예약 체크 완료 → 결과 표시"""
        self.generate_btn.setEnabled(True)
        self.booking_only_btn.setEnabled(True)
        self.progress_bar.setVisible(False)

        is_auto = getattr(self, 'auto_mode', False)

        final_keywords = self.booking_results

        if not final_keywords:
            if is_auto:
                print("[AutoMode] 실시간 예약 완료: 순위권 키워드 없음")
                self.statusBar().showMessage("✅ 완료 (예약 키워드 없음)")
            else:
                QMessageBox.information(self, "결과", "순위권 내 실시간 예약 키워드가 없습니다.")
            return

        # 순위순 정렬
        final_keywords.sort(key=lambda x: x["rank"])

        # 결과 테이블에 표시
        self.result_table.setRowCount(len(final_keywords))

        for i, kw_info in enumerate(final_keywords):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            w = QWidget()
            l = QHBoxLayout(w)
            l.addWidget(checkbox)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setContentsMargins(0, 0, 0, 0)
            self.result_table.setCellWidget(i, 0, w)

            self.result_table.setItem(i, 1, QTableWidgetItem(kw_info["keyword"]))

            rank_item = QTableWidgetItem(f"{kw_info['rank']}위")
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(i, 2, rank_item)

            map_item = QTableWidgetItem("예약")
            map_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            map_item.setBackground(Qt.GlobalColor.yellow)
            self.result_table.setItem(i, 3, map_item)

        checked_count = self.booking_check_index
        self.result_count_label.setText(f"총 {len(final_keywords)}개 (실시간 예약)")
        self.statusBar().showMessage(f"✅ 실시간 예약 키워드 {len(final_keywords)}개 ({checked_count}개 체크)")

        self._update_split_copy_combo()

    def on_generate_clicked(self):
        """키워드 생성 버튼 클릭"""
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "경고", "플레이스 URL을 입력해주세요.")
            return

        # URL에서 place_id 추출
        parsed = parse_place_url(url)
        if parsed.is_valid:
            self.place_id = parsed.mid
        else:
            QMessageBox.warning(self, "경고", "올바른 네이버 플레이스 URL이 아닙니다.")
            return

        # Playwright 브라우저 설치 확인 (추출된 데이터 없을 때만)
        if not self.extracted_place_data:
            if not ensure_playwright_installed(self):
                QMessageBox.warning(
                    self,
                    "브라우저 필요",
                    "업체 정보 수집을 위해 브라우저 설치가 필요합니다.\n"
                    "'정보 추출' 버튼을 먼저 클릭해주세요."
                )
                return

        # 이전 작업 정리
        if self.worker and self.worker.isRunning():
            return
        
        # 목표 개수 달성형 로직 초기화
        self.target_count = self.target_count_spin.value()
        
        # UI 상태 변경
        self.generate_btn.setEnabled(False)
        self.stop_btn.setVisible(True)  # 중단 버튼 표시
        self.progress_bar.setVisible(True)
        self.result_table.setRowCount(0)
        self.statusBar().showMessage(f"스마트 모드 시작: 목표 {self.target_count}개... (계층적 탐색)")
        
        # 프록시 및 설정 수집
        use_proxy = self.proxy_data.get("use_proxy", False)
        proxies = self._get_proxies() if use_proxy else []
        max_rank = self.max_rank_combo.currentIndex() + 1

        # 2단계 모드 사용 (기본값)
        self.statusBar().showMessage(f"시작: 목표 {self.target_count}개...")

        # 내 IP 사용 여부
        use_own_ip = self.proxy_data.get("use_own_ip", True) if use_proxy else True

        # 사용자가 선택한 데이터 수집 (태그 컨테이너에서 선택된 것만)
        # None = 자동 생성, [] = 사용자가 모두 해제
        user_regions = None  # 기본값: 자동 생성
        user_keywords = []
        user_name_parts = []
        user_modifiers = []
        selected_base_regions = []  # 선택된 기본 지역 (필터링용)

        if self.extracted_group.isVisible():
            # 태그 컨테이너에서 선택된 항목만 가져오기
            selected_base_regions = self.region_tags.get_selected()
            user_keywords = self.keyword_tags.get_selected()
            user_name_parts = self.name_tags.get_selected()
            user_modifiers = self.modifier_tags.get_selected()

            # 선택된 기본 지역에 해당하는 조합만 필터링
            all_region_combos = getattr(self, 'extracted_region_combinations', [])
            if selected_base_regions and all_region_combos:
                # 선택된 지역을 포함하는 조합만 필터
                user_regions = []
                for combo in all_region_combos:
                    for base in selected_base_regions:
                        if base in combo:
                            user_regions.append(combo)
                            break
                # 중복 제거
                user_regions = list(dict.fromkeys(user_regions))
                print(f"[GUI] 지역 필터: {len(selected_base_regions)}개 선택 → {len(user_regions)}개 조합")
            else:
                # 사용자가 모두 해제했거나, 조합이 없음 → 빈 리스트 명시 전달
                user_regions = list(selected_base_regions) if selected_base_regions else []
                if not user_regions:
                    print(f"[GUI] 지역 필터: 사용자가 모든 지역 해제")

        # SmartWorker 시작 (2단계 모드)
        # 지역+키워드 조합 가져오기 (선택된 지역 기준 필터링)
        all_region_keyword_combos = getattr(self, 'extracted_region_keyword_combos', [])

        # 지역+키워드 조합도 선택된 지역 기준으로 필터링
        if self.extracted_group.isVisible() and all_region_keyword_combos:
            if selected_base_regions:
                # 선택된 지역을 포함하는 조합만 필터
                region_keyword_combos = []
                for combo in all_region_keyword_combos:
                    for base in selected_base_regions:
                        if base in combo:
                            region_keyword_combos.append(combo)
                            break
                region_keyword_combos = list(dict.fromkeys(region_keyword_combos))
                print(f"[GUI] 지역+키워드 조합 필터: {len(all_region_keyword_combos)}개 → {len(region_keyword_combos)}개")
            else:
                # 지역 전체 해제 시 → 조합도 비움
                region_keyword_combos = []
                print(f"[GUI] 지역+키워드 조합: 지역 해제됨 → 0개")
        else:
            region_keyword_combos = all_region_keyword_combos

        user_slot = self.slot_spin.value()
        min_rank = self.min_rank_combo.currentIndex() + 1 if hasattr(self, 'min_rank_combo') else 1
        total_instances = getattr(self, 'total_instances', 1)
        self.worker = SmartWorker(
            url=url,
            target_count=self.target_count,
            max_rank=max_rank,
            min_rank=min_rank,
            proxies=proxies,
            new_map_ratio=60,  # 신지도:구지도 = 6:4 고정
            use_api_mode=True,  # 항상 API 모드 사용
            use_own_ip=use_own_ip,
            user_slot=user_slot,  # 사용자 슬롯 (0=전체, 1~10=분할)
            total_instances=total_instances,  # 총 인스턴스 수 (프록시 분배용)
            modifiers=self._get_modifiers(),
            # 사용자 편집 데이터 전달
            user_regions=user_regions,
            user_keywords=user_keywords,
            user_name_parts=user_name_parts,
            user_modifiers=user_modifiers,
            user_region_keyword_combos=region_keyword_combos,  # 지역+키워드 조합 (필터됨)
            place_data=self.extracted_place_data,
            basic_only=self.basic_only_check.isChecked()  # 기본 조합만 (R1-R2)
        )
        self.worker.finished.connect(self.on_smart_worker_finished)
        self.worker.error.connect(self.on_generate_error)
        self.worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        self.worker.sub_progress.connect(self.on_rank_check_progress)
        self.worker.preview_ready.connect(self.on_preview_ready)
        self.worker.phase1_data_ready.connect(self.on_phase1_data_ready)  # Phase 1 완료 후 편집
        self.worker.start()
    
    def on_preview_ready(self, keywords: list, count: int):
        """키워드 생성 완료 - 팝업 없이 바로 순위 체크 진행"""
        # 팝업 없이 상태바에만 표시
        self.statusBar().showMessage(f"📋 {count}개 키워드 생성됨 → 순위 체크 진행 중...")

    def on_phase1_data_ready(self, result: dict):
        """Phase 1 완료 - 사용자 편집 UI 표시"""
        # 진행바 일시 숨기기
        self.progress_bar.setVisible(False)

        # 추출된 데이터 저장
        self.extracted_place_data = result.get("place_data")

        # UI에 데이터 채우기
        regions = result.get("regions", [])
        keywords = result.get("keywords", [])
        name_parts = result.get("name_parts", [])
        modifiers = result.get("modifiers", [])

        # 태그 컨테이너에 데이터 설정
        self.region_tags.set_tags(regions, checked=True)
        self.keyword_tags.set_tags(keywords, checked=True)
        self.name_tags.set_tags(name_parts, checked=True)
        self.modifier_tags.set_tags(modifiers, checked=False)  # 수식어 기본 해제 (지도/추천은 자동 포함)

        # AI 키워드 분해 결과 추가
        decomposed_keywords = result.get("decomposed_keywords", [])
        if decomposed_keywords:
            existing_keywords = set(keywords)
            for dk in decomposed_keywords:
                if dk not in existing_keywords:
                    self.keyword_tags.add_tag(dk, checked=True, is_decomposed=True)

        # 업종 표시
        category = result.get("category", "")
        name = result.get("name", "")
        self.category_label.setText(f"{category} - {name}")

        # 편집 영역 표시 + 계속 버튼 표시
        self.extracted_group.setVisible(True)
        self.continue_btn.setVisible(True)
        self.stop_btn.setVisible(True)

        self.statusBar().showMessage(f"✅ {name} 정보 추출 완료 - 수정 후 [계속] 버튼을 클릭하세요")

    def on_continue_clicked(self):
        """계속 버튼 클릭 - 편집 완료 후 Phase 2 진행"""
        if not self.worker or not self.worker.isRunning():
            return

        # 사용자가 선택한 데이터 수집 (태그 컨테이너에서 선택된 것만)
        edited_data = {
            "regions": self.region_tags.get_selected(),
            "keywords": self.keyword_tags.get_selected(),
            "name_parts": self.name_tags.get_selected(),
            "modifiers": self.modifier_tags.get_selected(),
        }

        # 편집 UI 숨기기
        self.extracted_group.setVisible(False)
        self.continue_btn.setVisible(False)
        self.progress_bar.setVisible(True)

        self.statusBar().showMessage("편집 완료 → Phase 2 키워드 생성 진행 중...")

        # SmartWorker에 편집 데이터 전달하고 계속 진행
        self.worker.confirm_and_proceed(edited_data)

    def _confirm_preview(self, dialog, confirmed: bool):
        """미리보기 확인/취소 처리 (레거시 - 사용 안함)"""
        pass
        
    def on_generate_finished(self, keywords):
        """키워드 생성 완료 - 자동으로 순위 체크 시작"""
        # 기존에 생성된 키워드 추적 (중복 방지)
        new_keywords = [kw for kw in keywords if kw not in self.verified_keywords]
        self.all_generated_keywords.update(keywords)
        
        self._populate_table(new_keywords)
        self.round_count += 1
        
        self.statusBar().showMessage(
            f"[라운드 {self.round_count}] 키워드 {len(new_keywords)}개 생성 → 순위 체크 시작..."
        )
        
        # 자동으로 순위 체크 시작
        self._start_auto_rank_check(new_keywords)
    def on_stop_clicked(self):
        """중단 버튼 클릭"""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.statusBar().showMessage("작업 중단 요청됨... 현재까지 결과 저장 중")

    def on_smart_worker_finished(self, results):
        """스마트 워커 작업 완료"""
        self.generate_btn.setEnabled(True)
        self.stop_btn.setVisible(False)  # 중단 버튼 숨기기
        self.continue_btn.setVisible(False)  # 계속 버튼 숨기기
        self.extracted_group.setVisible(False)  # 편집 영역 숨기기
        self.progress_bar.setVisible(False)

        # 순위 범위 설정 가져오기
        min_rank = self.min_rank_combo.currentIndex() + 1 if hasattr(self, 'min_rank_combo') else 1
        max_rank = self.max_rank_combo.currentIndex() + 1 if hasattr(self, 'max_rank_combo') else 50

        # 결과 통계 출력 (디버깅용)
        total = len(results)
        found = sum(1 for r in results if r.status == "found")
        in_range = sum(1 for r in results if r.rank is not None and min_rank <= r.rank <= max_rank)
        not_found = sum(1 for r in results if r.status == "not_found")
        errors = sum(1 for r in results if r.status == "error")
        cancelled = sum(1 for r in results if r.status == "cancelled")
        print(f"[결과] 전체: {total}개 | 발견: {found}개 | 범위내({min_rank}~{max_rank}위): {in_range}개 | 순위외: {not_found}개 | 에러: {errors}개 | 취소: {cancelled}개")

        # 에러 상세 출력 (처음 5개만)
        error_results = [r for r in results if r.status == "error"]
        if error_results:
            print(f"[에러 상세] 처음 5개:")
            for r in error_results[:5]:
                print(f"  - {r.keyword}: {r.error_message}")

        ranked_keywords = []
        for result in results:
            if result.rank is not None and min_rank <= result.rank <= max_rank:
                ranked_keywords.append({
                    "keyword": result.keyword,
                    "rank": result.rank,
                    "map_type": result.map_type
                })

        # 신지도 리스트 키워드 별도 저장 (실시간 예약 버튼용) - 1위 제외, 순위 범위 내만
        self.newmap_keywords_cache = []
        for result in results:
            # 2위 이상 ~ max_rank 이하 신지도만 저장 (1위는 실시간 예약 대상 아님)
            if result.rank is not None and result.rank > 1 and result.rank <= max_rank and result.rank >= min_rank and result.map_type == "신지도":
                self.newmap_keywords_cache.append({
                    "keyword": result.keyword,
                    "rank": result.rank
                })
            elif result.rank == 1 and result.map_type == "신지도":
                print(f"[SmartWorker] 신지도 1위 '{result.keyword}' → 실시간 예약 대상에서 제외")
        # 순위순 정렬
        self.newmap_keywords_cache.sort(key=lambda x: x["rank"])
        print(f"[SmartWorker] 신지도 리스트 키워드 {len(self.newmap_keywords_cache)}개 캐시됨")

        # 순위오름차순 정렬
        ranked_keywords.sort(key=lambda x: x["rank"])

        # 목표 개수만큼만 자르기
        ranked_keywords = ranked_keywords[:self.target_count]

        # 예약 수식어 키워드 REPLACE 적용 (신지도 형태에만, 총 개수 유지)
        booking_replaced_count = 0

        # 예약 기능 확인 (extracted_place_data에서 확인)
        has_booking = False
        if hasattr(self, 'extracted_place_data') and self.extracted_place_data:
            has_booking = getattr(self.extracted_place_data, 'has_booking', False)

        # 지도 타입 분포 확인
        map_type_counts = {}
        for kw_info in ranked_keywords:
            mt = kw_info.get("map_type", "없음")
            map_type_counts[mt] = map_type_counts.get(mt, 0) + 1
        print(f"[예약DEBUG] has_booking: {has_booking}, map_type 분포: {map_type_counts}")

        # 예약 기능이 있고, 체크박스 체크했고, 신지도 키워드가 있으면 REPLACE 적용
        if has_booking and self.booking_use_check.isChecked() and map_type_counts.get("신지도", 0) > 0:
            booking_modifier = "실시간 예약"  # 고정 수식어
            # 예약 키워드 비율 (10%)
            booking_ratio = 0.1
            target_booking_count = max(1, int(len(ranked_keywords) * booking_ratio))
            print(f"[예약DEBUG] target_booking_count: {target_booking_count}")

            # 신지도 형태 키워드의 인덱스 찾기 (1위 제외)
            eligible_indices = []
            for idx, kw_info in enumerate(ranked_keywords):
                map_type = kw_info.get("map_type", "")
                keyword = kw_info.get("keyword", "")
                rank = kw_info.get("rank", 0)
                # 신지도 형태이고, 2위 이하이고, 이미 예약 관련 단어가 없는 경우에만
                if map_type == "신지도" and rank > 1 and "예약" not in keyword:
                    eligible_indices.append(idx)
                elif map_type == "신지도" and rank == 1:
                    print(f"[예약DEBUG] 1위 제외: '{keyword}'")

            print(f"[예약DEBUG] eligible_indices 개수: {len(eligible_indices)}")

            # REPLACE: 신지도 키워드를 예약 버전으로 교체 (ADD가 아닌 REPLACE)
            replace_count = min(target_booking_count, len(eligible_indices))
            for i in range(replace_count):
                idx = eligible_indices[i]
                original_keyword = ranked_keywords[idx]["keyword"]
                booking_kw = f"{original_keyword} {booking_modifier}"
                ranked_keywords[idx] = {
                    "keyword": booking_kw,
                    "rank": ranked_keywords[idx]["rank"],  # 원본 순위 유지
                    "map_type": "예약"  # 예약 키워드로 표시
                }
                booking_replaced_count += 1
                print(f"[예약DEBUG] 교체: {original_keyword} -> {booking_kw}")
        
        # 테이블 표시
        self.result_table.setRowCount(len(ranked_keywords))
        
        for i, kw_info in enumerate(ranked_keywords):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            w = QWidget()
            l = QHBoxLayout(w)
            l.addWidget(checkbox)
            l.setAlignment(Qt.AlignmentFlag.AlignCenter)
            l.setContentsMargins(0,0,0,0)
            self.result_table.setCellWidget(i, 0, w)
            
            self.result_table.setItem(i, 1, QTableWidgetItem(kw_info["keyword"]))
            
            rank_item = QTableWidgetItem(f"{kw_info['rank']}위")
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(i, 2, rank_item)
            
            # 지도형태 표시 (RankChecker returns 신지도/구지도/알수없음)
            # 예약 키워드는 "예약" 형태로 표시
            keyword = kw_info.get("keyword", "")
            map_type = kw_info.get("map_type", "")
            if "실시간 예약" in keyword or keyword.endswith("예약"):
                map_display = "예약"
            elif map_type:
                map_display = map_type
            else:
                map_display = "-"
            map_item = QTableWidgetItem(map_display)
            map_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # 예약 키워드는 배경색 다르게
            if map_display == "예약":
                map_item.setBackground(Qt.GlobalColor.yellow)
            self.result_table.setItem(i, 3, map_item)
            
        count_text = f"총 {len(ranked_keywords)}개"
        if booking_replaced_count > 0:
            count_text += f" (예약 교체 {booking_replaced_count}개 포함)"
        if len(ranked_keywords) >= self.target_count:
            count_text += " 🎉"

        self.result_count_label.setText(count_text)
        status_msg = f"✅ 완료: {len(ranked_keywords)}개"
        if booking_replaced_count > 0:
            status_msg += f" (예약 교체 {booking_replaced_count}개)"
        status_msg += f" (전체 {len(results)}개 검증)"
        self.statusBar().showMessage(status_msg)

        # 실시간 예약 모드: 자동으로 실시간 예약 키워드만 생성
        if getattr(self, 'booking_only_mode', False) and getattr(self, 'auto_mode', False):
            from PyQt6.QtCore import QTimer
            print(f"[AutoMode] 실시간 예약 모드 → 예약 키워드만 생성 시작")
            self.statusBar().showMessage("🎫 실시간 예약 키워드 생성 중...")
            QTimer.singleShot(500, self.on_booking_only_clicked)

    def on_generate_finished(self, keywords):
        if self.proxy_data.get("use_proxy", False):
            proxies = self._get_proxies()

        # 사용자 슬롯 가져오기
        user_slot = 0

        # 최대 순위 설정
        max_rank = self.max_rank_combo.currentIndex() + 1

        # 예상 시간 계산 및 표시
        proxy_count = len(proxies) if proxies else 1
        estimated = estimate_time(len(keywords), proxy_count, max_rank)
        self.statusBar().showMessage(f"순위 체크 중... (예상: {estimated['formatted']})")

        # 진행바 업데이트
        self.progress_bar.setRange(0, len(keywords))
        self.progress_bar.setValue(0)

        # RankWorker 시작
        user_slot = self.slot_spin.value()
        self.rank_worker = RankWorker(
            keywords=keywords,
            place_id=self.place_id,
            max_rank=max_rank,
            proxies=proxies,
            user_slot=user_slot,
            proxy_type="mixed"
        )
        self.rank_worker.finished.connect(self._on_auto_rank_finished)
        self.rank_worker.error.connect(self.on_rank_check_error)
        self.rank_worker.progress.connect(self.on_rank_check_progress)
        self.rank_worker.start()
    
    def _on_auto_rank_finished(self, results):
        """자동 순위 체크 완료 - 목표 달성 여부 확인 후 추가 생성 또는 완료"""
        # 순위 범위 설정 가져오기
        min_rank = self.min_rank_combo.currentIndex() + 1 if hasattr(self, 'min_rank_combo') else 1
        max_rank = self.max_rank_combo.currentIndex() + 1 if hasattr(self, 'max_rank_combo') else 50

        # 검증된 키워드 추적 + 미노출 키워드 수집
        not_found_keywords = []
        error_keywords = []
        for result in results:
            self.verified_keywords.add(result.keyword)
            if result.rank is not None and min_rank <= result.rank <= max_rank:
                self.ranked_results.append({
                    "keyword": result.keyword,
                    "rank": result.rank,
                    "map_type": result.map_type
                })
            elif result.status == "error":
                # 요청 실패 (429 등) - 학습하지 않음
                error_keywords.append(result.keyword)
            else:
                # 진짜 미노출 (not_found)
                not_found_keywords.append(result.keyword)

        if error_keywords:
            print(f"[경고] {len(error_keywords)}개 키워드 조회 실패 (재시도 필요): {error_keywords[:5]}...")
        
        # 미노출 키워드 자동 학습
        if not_found_keywords and self.current_category:
            try:
                learning_manager = get_learning_manager(script_dir)
                learning_manager.add_blocked_keywords(not_found_keywords, self.current_category)
                print(f"[학습] {len(not_found_keywords)}개 미노출 키워드 학습 완료 ({self.current_category})")
            except Exception as e:
                print(f"[학습] 오류: {e}")
        
        current_ranked_count = len(self.ranked_results)
        
        # 목표 달성 여부 확인
        if current_ranked_count >= self.target_count:
            # 목표 달성! 결과 표시
            self._display_final_results()
        elif self.round_count >= self.max_rounds:
            # 최대 라운드 도달 - 현재까지 결과로 완료
            self.statusBar().showMessage(
                f"⚠️ 최대 {self.max_rounds}회 검증 완료. "
                f"목표 {self.target_count}개 중 {current_ranked_count}개 확보"
            )
            self._display_final_results()
        else:
            # 목표 미달 - 추가 키워드 생성
            remaining = self.target_count - current_ranked_count
            additional_count = remaining * 3  # 부족분의 3배 추가 생성
            
            self.statusBar().showMessage(
                f"현재 {current_ranked_count}/{self.target_count}개 → "
                f"추가 {additional_count}개 키워드 생성 중..."
            )
            
            # 추가 키워드 생성 (기존 키워드 제외)
            url = self.url_input.text().strip()
            self.worker = KeywordWorker(url, additional_count)
            self.worker.finished.connect(self.on_generate_finished)
            self.worker.error.connect(self.on_generate_error)
            self.worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
            self.worker.start()
    
    def _display_final_results(self):
        """최종 결과 표시 (목표 개수만큼, 순위순 정렬)"""
        self.generate_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.progress_bar.setVisible(False)

        # 순위순으로 정렬
        self.ranked_results.sort(key=lambda x: x["rank"])

        # 목표 개수만큼만 자르기
        display_results = self.ranked_results[:self.target_count]

        # 예약 수식어 키워드 REPLACE 적용 (신지도 형태에만, 총 개수 유지)
        booking_replaced_count = 0
        if (self.booking_layout_widget.isVisible() and
            self.booking_use_check.isChecked()):
            booking_modifier = self.booking_modifier_edit.text().strip()
            if booking_modifier:
                # 예약 키워드 비율 (10%)
                booking_ratio = 0.1
                target_booking_count = max(1, int(len(display_results) * booking_ratio))

                # 신지도 형태 키워드의 인덱스 찾기
                eligible_indices = []
                for idx, kw_info in enumerate(display_results):
                    map_type = kw_info.get("map_type", "")
                    keyword = kw_info.get("keyword", "")
                    # 신지도 형태이고, 이미 예약 관련 단어가 없는 경우에만
                    if map_type == "신지도" and "예약" not in keyword:
                        eligible_indices.append(idx)

                # REPLACE: 신지도 키워드를 예약 버전으로 교체 (ADD가 아닌 REPLACE)
                replace_count = min(target_booking_count, len(eligible_indices))
                for i in range(replace_count):
                    idx = eligible_indices[i]
                    original_keyword = display_results[idx]["keyword"]
                    booking_kw = f"{original_keyword} {booking_modifier}"
                    display_results[idx] = {
                        "keyword": booking_kw,
                        "rank": display_results[idx]["rank"],  # 원본 순위 유지
                        "map_type": "예약"  # 예약 키워드로 표시
                    }
                    booking_replaced_count += 1

        # 전체 결과 (REPLACE 방식이므로 display_results 그대로 사용, 총 개수 유지)
        all_results = display_results

        # 테이블 채우기
        self.result_table.setRowCount(len(all_results))
        self.keywords = [kw["keyword"] for kw in all_results]

        for i, kw_info in enumerate(all_results):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.result_table.setCellWidget(i, 0, checkbox_widget)

            self.result_table.setItem(i, 1, QTableWidgetItem(kw_info["keyword"]))

            rank_item = QTableWidgetItem(f"{kw_info['rank']}위")
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(i, 2, rank_item)

            # 지도 형태 표시
            map_type = kw_info.get("map_type", "-")
            map_item = QTableWidgetItem(map_type if map_type else "-")
            map_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            # 예약 키워드는 배경색 다르게
            if map_type == "예약":
                map_item.setBackground(Qt.GlobalColor.yellow)
            self.result_table.setItem(i, 3, map_item)

        # 결과 카운트 메시지
        count_msg = f"총 {len(all_results)}개"
        if booking_replaced_count > 0:
            count_msg += f" (순위권 {len(all_results) - booking_replaced_count}개 + 예약 교체 {booking_replaced_count}개)"
        else:
            count_msg += " (순위권 내)"

        self.result_count_label.setText(count_msg)
        self.statusBar().showMessage(
            f"✅ 완료: {len(all_results)}개 (예약 교체 {booking_replaced_count}개 포함) "
            f"(총 {len(self.verified_keywords)}개 검증, {self.round_count}라운드)"
        )

        # 분할 복사 콤보박스 업데이트
        self._update_split_copy_combo()

    def on_generate_error(self, error_msg):
        """키워드 생성 오류"""
        self.generate_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.continue_btn.setVisible(False)
        self.extracted_group.setVisible(False)
        self.progress_bar.setVisible(False)

        self.statusBar().showMessage(f"❌ 오류: {error_msg}")
        QMessageBox.critical(self, "오류", error_msg)
        
    def _populate_table(self, keywords):
        """테이블에 키워드 채우기"""
        self.keywords = keywords
        self.result_table.setRowCount(len(keywords))
        
        for i, kw in enumerate(keywords):
            checkbox = QCheckBox()
            checkbox.setChecked(True)
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.result_table.setCellWidget(i, 0, checkbox_widget)
            
            self.result_table.setItem(i, 1, QTableWidgetItem(kw))
            
            rank_item = QTableWidgetItem("-")
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.result_table.setItem(i, 2, rank_item)
        
        self.result_count_label.setText(f"총 {len(keywords)}개")

    # === 태그 전체 선택/해제 메서드 ===
    def _on_tag_select_all(self):
        """태그 컨테이너 전체 선택"""
        self.region_tags.select_all()
        self.keyword_tags.select_all()
        self.name_tags.select_all()
        self.modifier_tags.select_all()

    def _on_tag_deselect_all(self):
        """태그 컨테이너 전체 해제"""
        print("[GUI] 전체 해제 버튼 클릭")
        self.region_tags.deselect_all()
        self.keyword_tags.deselect_all()
        self.name_tags.deselect_all()
        self.modifier_tags.deselect_all()
        print(f"[GUI] 해제 후 지역: {self.region_tags.get_selected()}")

    def on_select_all(self):
        """전체 선택"""
        for i in range(self.result_table.rowCount()):
            widget = self.result_table.cellWidget(i, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(True)
                    
    def on_deselect_all(self):
        """전체 해제"""
        for i in range(self.result_table.rowCount()):
            widget = self.result_table.cellWidget(i, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox:
                    checkbox.setChecked(False)
        
    def on_check_rank_clicked(self):
        """순위 체크 버튼 클릭"""
        selected_keywords = self._get_selected_keywords()
        if not selected_keywords:
            QMessageBox.warning(self, "경고", "선택된 키워드가 없습니다.")
            return
        
        # 플레이스 ID 확인
        if not self.place_id:
            QMessageBox.warning(self, "경고", "먼저 키워드를 생성해주세요. (플레이스 ID 필요)")
            return
        
        # 이전 작업 확인
        if self.rank_worker and self.rank_worker.isRunning():
            QMessageBox.warning(self, "경고", "순위 체크가 이미 진행 중입니다.")
            return
        
        # 프록시 설정 수집 (CSV에서 로드된 목록)
        proxies = []
        if self.proxy_data.get("use_proxy", False):
            proxies = self._get_proxies()

        # 사용자 슬롯 가져오기
        user_slot = 0

        # 프록시 타입 (혼합 모드)
        proxy_type = "mixed"

        # 최대 순위 설정
        max_rank = self.max_rank_combo.currentIndex() + 1

        # 예상 시간 계산
        proxy_count = len(proxies) if proxies else 1
        estimated = estimate_time(len(selected_keywords), proxy_count, max_rank)

        # 확인 메시지
        proxy_type_label = "Decodo(빠름)" if proxy_type == "decodo" else "Datacenter(고정IP)"
        slot_label = "A (IP 1~50)" if user_slot == 0 else "B (IP 51~100)"
        msg = f"선택된 키워드: {len(selected_keywords)}개\n"
        msg += f"프록시: {proxy_count}개 [{proxy_type_label}]\n"
        msg += f"예상 시간: {estimated['formatted']}\n\n"
        msg += "순위 체크를 시작할까요?"

        reply = QMessageBox.question(
            self, "순위 체크 시작", msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        # UI 상태 변경
        self.check_rank_btn.setEnabled(False)
        self.generate_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(selected_keywords))
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("순위 체크 시작...")

        # RankWorker 시작
        self.rank_worker = RankWorker(
            keywords=selected_keywords,
            place_id=self.place_id,
            max_rank=max_rank,
            proxies=proxies,
            user_slot=user_slot,
            proxy_type=proxy_type
        )
        self.rank_worker.finished.connect(self.on_rank_check_finished)
        self.rank_worker.error.connect(self.on_rank_check_error)
        self.rank_worker.progress.connect(self.on_rank_check_progress)
        self.rank_worker.start()
    
    def on_rank_check_progress(self, current, total, message):
        """순위 체크 진행 상황 업데이트"""
        self.progress_bar.setValue(current)
        self.statusBar().showMessage(f"[{current}/{total}] {message}")
    
    def on_rank_check_finished(self, results):
        """순위 체크 완료"""
        self.check_rank_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        
        # 결과 테이블 업데이트
        found_count = 0
        for result in results:
            # 해당 키워드 찾기
            for i in range(self.result_table.rowCount()):
                item = self.result_table.item(i, 1)
                if item and item.text() == result.keyword:
                    rank_item = self.result_table.item(i, 2)
                    if result.rank:
                        rank_item.setText(f"{result.rank}위")
                        found_count += 1
                    else:
                        rank_item.setText("순위권 외")
                    break
        
        self.statusBar().showMessage(f"순위 체크 완료: {found_count}/{len(results)}개 순위권 내")
        
        # 미노출 키워드 제외 옵션 적용
        if self.exclude_no_rank_check.isChecked():
            for i in range(self.result_table.rowCount()):
                rank_item = self.result_table.item(i, 2)
                if rank_item and rank_item.text() == "순위권 외":
                    widget = self.result_table.cellWidget(i, 0)
                    if widget:
                        checkbox = widget.findChild(QCheckBox)
                        if checkbox:
                            checkbox.setChecked(False)

        # 분할 복사 콤보박스 업데이트
        self._update_split_copy_combo()

    def on_rank_check_error(self, error_msg):
        """순위 체크 오류"""
        self.check_rank_btn.setEnabled(True)
        self.generate_btn.setEnabled(True)
        self.stop_btn.setVisible(False)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("순위 체크 오류 발생")
        QMessageBox.critical(self, "순위 체크 오류", error_msg)
        
    def _get_selected_keywords(self):
        """선택된 키워드 목록 반환"""
        selected = []
        for i in range(self.result_table.rowCount()):
            widget = self.result_table.cellWidget(i, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    item = self.result_table.item(i, 1)
                    if item:
                        selected.append(item.text())
        return selected
        
    def on_copy_clicked(self):
        """클립보드 복사 (형식 선택에 따라)"""
        # 선택된 키워드와 순위 수집
        selected_items = []
        for i in range(self.result_table.rowCount()):
            widget = self.result_table.cellWidget(i, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    keyword_item = self.result_table.item(i, 1)
                    rank_item = self.result_table.item(i, 2)
                    if keyword_item:
                        keyword = keyword_item.text()
                        rank = rank_item.text() if rank_item else ""
                        selected_items.append((keyword, rank))

        if not selected_items:
            QMessageBox.warning(self, "경고", "복사할 키워드가 없습니다.")
            return
        
        # 형식에 따라 텍스트 생성
        if self.radio_comma.isChecked():
            # 쉼표 구분 (키워드만)
            content = ",".join(item[0] for item in selected_items)
            format_name = "쉼표 구분"
        elif self.radio_tab_rank.isChecked():
            # 탭+순위 (엑셀용)
            content = "\n".join(f"{item[0]}\t{item[1]}" for item in selected_items)
            format_name = "탭+순위"
        else:
            # 줄바꿈 (키워드만) - 기본값
            content = "\n".join(item[0] for item in selected_items)
            format_name = "줄바꿈"
        
        clipboard = QApplication.clipboard()
        clipboard.setText(content)
        
        self.statusBar().showMessage(f"클립보드 복사 완료: {len(selected_items)}개 ({format_name})")

    def _update_split_copy_combo(self):
        """분할 복사 콤보박스 업데이트 (200개 단위)"""
        # 선택된 키워드 수 계산
        selected_count = 0
        for i in range(self.result_table.rowCount()):
            widget = self.result_table.cellWidget(i, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    selected_count += 1

        # 콤보박스 업데이트
        self.split_copy_combo.clear()
        self.split_copy_combo.addItem("전체", 0)

        if selected_count > 200:
            num_parts = (selected_count + 199) // 200  # 올림 나눗셈
            for i in range(num_parts):
                start = i * 200 + 1
                end = min((i + 1) * 200, selected_count)
                self.split_copy_combo.addItem(f"{start}~{end}번", i + 1)

    def on_split_copy_clicked(self):
        """분할 복사 버튼 클릭"""
        # 선택된 키워드와 순위 수집
        selected_items = []
        for i in range(self.result_table.rowCount()):
            widget = self.result_table.cellWidget(i, 0)
            if widget:
                checkbox = widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    keyword_item = self.result_table.item(i, 1)
                    rank_item = self.result_table.item(i, 2)
                    if keyword_item:
                        keyword = keyword_item.text()
                        rank = rank_item.text() if rank_item else ""
                        selected_items.append((keyword, rank))

        if not selected_items:
            QMessageBox.warning(self, "경고", "복사할 키워드가 없습니다.")
            return

        # 분할 선택 확인
        split_index = self.split_copy_combo.currentData()

        if split_index == 0:
            # 전체 복사
            items_to_copy = selected_items
            part_info = "전체"
        else:
            # 분할 복사 (200개 단위)
            start_idx = (split_index - 1) * 200
            end_idx = min(split_index * 200, len(selected_items))
            items_to_copy = selected_items[start_idx:end_idx]
            part_info = f"{start_idx + 1}~{end_idx}번"

        # 형식에 따라 텍스트 생성
        if self.radio_comma.isChecked():
            content = ",".join(item[0] for item in items_to_copy)
            format_name = "쉼표 구분"
        elif self.radio_tab_rank.isChecked():
            content = "\n".join(f"{item[0]}\t{item[1]}" for item in items_to_copy)
            format_name = "탭+순위"
        else:
            content = "\n".join(item[0] for item in items_to_copy)
            format_name = "줄바꿈"

        clipboard = QApplication.clipboard()
        clipboard.setText(content)

        self.statusBar().showMessage(f"분할 복사 완료: {len(items_to_copy)}개 ({part_info}, {format_name})")

    def on_save_clicked(self):
        """TXT 저장 버튼 클릭"""
        selected = self._get_selected_keywords()
        if not selected:
            QMessageBox.warning(self, "경고", "저장할 키워드가 없습니다.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "키워드 저장", "", "Text Files (*.txt)"
        )
        
        if file_path:
            if self.radio_comma.isChecked():
                content = ",".join(selected)
            else:
                content = "\n".join(selected)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            QMessageBox.information(self, "완료", f"저장 완료: {file_path}")
            self.statusBar().showMessage(f"저장됨: {file_path}")


def main():
    import argparse
    from PyQt6.QtCore import QTimer

    # 명령줄 인자 파싱
    parser = argparse.ArgumentParser(description='Naver Place 키워드 추출기')
    parser.add_argument('--url', type=str, help='네이버 플레이스 URL')
    parser.add_argument('--slot', type=int, default=0, help='슬롯 번호 (1-10, 0=전체)')
    parser.add_argument('--target', type=int, default=50, help='목표 키워드 건수')
    parser.add_argument('--rank', type=int, default=10, help='목표 순위 (최대)')
    parser.add_argument('--min-rank', type=int, default=1, help='최소 순위')
    parser.add_argument('--total-instances', type=int, default=1, help='총 실행 인스턴스 수 (프록시 분배용)')
    parser.add_argument('--auto', action='store_true', help='자동 실행 모드')
    parser.add_argument('--booking-only', action='store_true', help='실시간 예약 키워드만 생성 모드')
    args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = MainWindow()

    # 명령줄 인자로 URL과 슬롯이 지정된 경우 자동 설정
    if args.url:
        window.url_input.setText(args.url)
        window.setWindowTitle(f"키워드 추출기 [슬롯 {args.slot}]")

    if args.slot > 0:
        window.slot_spin.setValue(args.slot)

    # 목표 건수 설정
    if args.target:
        window.target_count_spin.setValue(args.target)

    # 목표 순위 설정 (ComboBox index = rank - 1)
    if args.rank:
        rank_index = min(args.rank - 1, 49)  # 최대 50위
        window.max_rank_combo.setCurrentIndex(rank_index)

    # 최소 순위 설정
    min_rank = getattr(args, 'min_rank', 1)
    if min_rank and hasattr(window, 'min_rank_combo'):
        min_rank_index = min(min_rank - 1, 49)  # 최대 50위
        window.min_rank_combo.setCurrentIndex(min_rank_index)

    # 총 인스턴스 수 (프록시 분배용)
    window.total_instances = getattr(args, 'total_instances', 1)

    # 자동 실행 모드
    if args.auto and args.url:
        window.auto_mode = True
        # 창이 표시된 후 자동으로 정보 추출 시작
        QTimer.singleShot(500, window.on_extract_clicked)
    else:
        window.auto_mode = False

    # 실시간 예약 키워드만 생성 모드
    window.booking_only_mode = getattr(args, 'booking_only', False)

    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
