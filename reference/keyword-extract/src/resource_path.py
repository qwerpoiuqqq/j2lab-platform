"""
PyInstaller EXE 빌드 시 리소스 파일 경로 처리
- 개발 환경: 프로젝트 루트 기준 상대 경로
- EXE 환경: sys._MEIPASS 기준 경로
"""

import sys
import os


def get_base_path() -> str:
    """
    프로젝트 루트 경로 반환
    - PyInstaller EXE: sys._MEIPASS (임시 폴더)
    - 개발 환경: 스크립트 위치 기준 프로젝트 루트
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 EXE
        return sys._MEIPASS
    else:
        # 개발 환경 - src 폴더의 상위 (프로젝트 루트)
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_resource_path(relative_path: str) -> str:
    """
    리소스 파일의 절대 경로 반환

    Args:
        relative_path: 프로젝트 루트 기준 상대 경로 (예: "data/keyword_dictionary.json")

    Returns:
        절대 경로
    """
    base = get_base_path()
    return os.path.join(base, relative_path)


def get_user_data_path(filename: str) -> str:
    """
    사용자 데이터 파일 경로 반환 (쓰기 가능한 위치)
    - EXE: EXE 파일과 같은 폴더
    - 개발 환경: 프로젝트 루트

    Args:
        filename: 파일명 (예: "learning_data.json")

    Returns:
        쓰기 가능한 절대 경로
    """
    if getattr(sys, 'frozen', False):
        # EXE 파일이 위치한 폴더 (사용자가 쓸 수 있는 곳)
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        # 개발 환경 - 프로젝트 루트
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, filename)


def is_frozen() -> bool:
    """PyInstaller로 빌드된 EXE인지 확인"""
    return getattr(sys, 'frozen', False)
