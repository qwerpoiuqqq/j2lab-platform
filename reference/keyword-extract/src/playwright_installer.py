"""
Playwright 브라우저 자동 설치 유틸리티

사용자 PC에 Playwright 브라우저가 설치되어 있지 않으면
자동으로 설치를 안내하고 실행합니다.
"""
import subprocess
import sys
import os
from pathlib import Path


def is_playwright_installed() -> bool:
    """Playwright 브라우저가 설치되어 있는지 확인"""
    try:
        # Playwright 브라우저 경로 확인 (Windows)
        # 일반적으로 %USERPROFILE%\AppData\Local\ms-playwright 에 설치됨
        playwright_path = Path.home() / "AppData" / "Local" / "ms-playwright"

        if playwright_path.exists():
            # chromium 폴더가 있는지 확인
            chromium_dirs = list(playwright_path.glob("chromium-*"))
            if chromium_dirs:
                return True

        return False
    except Exception:
        return False


def install_playwright_browsers(progress_callback=None) -> tuple[bool, str]:
    """Playwright 브라우저 설치

    Args:
        progress_callback: 진행 상황 콜백 함수 (message: str) -> None

    Returns:
        (success: bool, message: str)
    """
    # EXE 환경 체크
    is_frozen = getattr(sys, 'frozen', False)

    try:
        if progress_callback:
            progress_callback("Playwright 브라우저 설치 중... (약 1-2분 소요)")

        if is_frozen:
            # EXE 환경: npx playwright 또는 시스템 Python 사용 시도
            # 먼저 npx 시도
            try:
                result = subprocess.run(
                    ["npx", "playwright", "install", "chromium"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                if result.returncode == 0:
                    if progress_callback:
                        progress_callback("Playwright 브라우저 설치 완료!")
                    return True, "설치 완료"
            except FileNotFoundError:
                pass

            # npx 실패 시 시스템 Python 시도
            python_paths = ["python", "python3", "py"]
            for python_cmd in python_paths:
                try:
                    result = subprocess.run(
                        [python_cmd, "-m", "playwright", "install", "chromium"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    )
                    if result.returncode == 0:
                        if progress_callback:
                            progress_callback("Playwright 브라우저 설치 완료!")
                        return True, "설치 완료"
                except FileNotFoundError:
                    continue

            return False, "Python 또는 Node.js가 설치되어 있지 않습니다.\n수동 설치: pip install playwright && playwright install chromium"
        else:
            # 개발 환경: sys.executable 사용
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )

            if result.returncode == 0:
                if progress_callback:
                    progress_callback("Playwright 브라우저 설치 완료!")
                return True, "설치 완료"
            else:
                error_msg = result.stderr or result.stdout or "알 수 없는 오류"
                return False, f"설치 실패: {error_msg[:200]}"

    except subprocess.TimeoutExpired:
        return False, "설치 시간 초과 (5분)"
    except FileNotFoundError:
        return False, "Python을 찾을 수 없습니다"
    except Exception as e:
        return False, f"설치 오류: {str(e)[:200]}"


def ensure_playwright_installed(parent_widget=None) -> bool:
    """Playwright가 설치되어 있는지 확인하고, 없으면 설치 안내

    Args:
        parent_widget: PyQt 부모 위젯 (다이얼로그 표시용)

    Returns:
        True if installed or successfully installed, False otherwise
    """
    if is_playwright_installed():
        return True

    # GUI가 있으면 다이얼로그 표시
    if parent_widget is not None:
        try:
            from PyQt6.QtWidgets import QMessageBox, QProgressDialog
            from PyQt6.QtCore import Qt

            # 설치 확인 다이얼로그
            reply = QMessageBox.question(
                parent_widget,
                "브라우저 설치 필요",
                "업체 정보 수집을 위해 브라우저를 설치해야 합니다.\n\n"
                "지금 설치하시겠습니까?\n"
                "(약 1-2분 소요, 인터넷 연결 필요)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if reply != QMessageBox.StandardButton.Yes:
                return False

            # 진행 다이얼로그
            progress = QProgressDialog(
                "브라우저 설치 중...\n잠시만 기다려주세요.",
                None,  # 취소 버튼 없음
                0, 0,  # 무한 진행
                parent_widget
            )
            progress.setWindowTitle("브라우저 설치")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.show()

            # 설치 실행 (별도 스레드에서 실행하는 것이 좋지만, 간단하게 처리)
            from PyQt6.QtWidgets import QApplication
            QApplication.processEvents()

            success, message = install_playwright_browsers()

            progress.close()

            if success:
                QMessageBox.information(
                    parent_widget,
                    "설치 완료",
                    "브라우저가 성공적으로 설치되었습니다!"
                )
                return True
            else:
                QMessageBox.critical(
                    parent_widget,
                    "설치 실패",
                    f"브라우저 설치에 실패했습니다.\n\n{message}\n\n"
                    "수동 설치: 명령 프롬프트에서\n"
                    "python -m playwright install chromium"
                )
                return False

        except ImportError:
            pass

    # GUI 없이 CLI에서 실행
    print("[알림] Playwright 브라우저가 설치되어 있지 않습니다.")
    print("[설치] python -m playwright install chromium")
    return False


# 테스트
if __name__ == "__main__":
    print(f"Playwright 설치됨: {is_playwright_installed()}")

    if not is_playwright_installed():
        print("설치 시작...")
        success, msg = install_playwright_browsers(print)
        print(f"결과: {success}, {msg}")
