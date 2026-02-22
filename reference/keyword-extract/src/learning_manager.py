"""
키워드 학습 관리자
- 미노출 키워드 패턴 자동 학습
- 학습 데이터 저장/로드
- 키워드 생성 시 학습 데이터 기반 필터링
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Set, Optional
from dataclasses import dataclass, field, asdict

# EXE 빌드용 리소스 경로 헬퍼
try:
    from src.resource_path import get_user_data_path
except ImportError:
    from resource_path import get_user_data_path


@dataclass
class BlockedKeyword:
    """차단된 키워드 정보"""
    keyword: str
    category: str  # restaurant, hospital, general
    added_date: str
    hit_count: int = 1  # 몇 번 미노출되었는지


class LearningManager:
    """학습 데이터 관리자"""
    
    LEARNING_FILE = "learning_data.json"
    EXPIRE_DAYS = 30  # 30일 후 자동 삭제
    
    def __init__(self, base_dir: str = None):
        """
        Args:
            base_dir: 학습 데이터 저장 디렉토리 (기본: EXE 폴더 또는 프로젝트 루트)
        """
        if base_dir:
            self.file_path = os.path.join(base_dir, self.LEARNING_FILE)
        else:
            # EXE/개발 환경 모두 지원하는 쓰기 가능한 경로
            self.file_path = get_user_data_path(self.LEARNING_FILE)
        self.base_dir = os.path.dirname(self.file_path)
        self.data: Dict = self._load()
    
    def _load(self) -> Dict:
        """학습 데이터 로드"""
        if not os.path.exists(self.file_path):
            return self._get_default_data()
        
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 만료된 데이터 정리
                self._cleanup_expired(data)
                return data
        except Exception as e:
            print(f"[LearningManager] 로드 실패: {e}")
            return self._get_default_data()
    
    def _get_default_data(self) -> Dict:
        """기본 데이터 구조"""
        return {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "categories": {
                "restaurant": {"blocked_keywords": []},
                "hospital": {"blocked_keywords": []},
                "general": {"blocked_keywords": []}
            }
        }
    
    def _cleanup_expired(self, data: Dict):
        """만료된 키워드 제거"""
        now = datetime.now()
        for category in data.get("categories", {}).values():
            blocked = category.get("blocked_keywords", [])
            valid = []
            for item in blocked:
                try:
                    added = datetime.fromisoformat(item.get("added_date", ""))
                    if (now - added).days < self.EXPIRE_DAYS:
                        valid.append(item)
                except:
                    valid.append(item)  # 파싱 실패 시 유지
            category["blocked_keywords"] = valid
    
    def save(self):
        """학습 데이터 저장"""
        self.data["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[LearningManager] 저장 실패: {e}")
    
    def add_blocked_keywords(self, keywords: List[str], category: str):
        """
        미노출 키워드 학습
        
        Args:
            keywords: 미노출 키워드 리스트
            category: 업종 (restaurant, hospital, general)
        """
        if category not in self.data["categories"]:
            category = "general"
        
        blocked_list = self.data["categories"][category]["blocked_keywords"]
        existing_keywords = {item["keyword"] for item in blocked_list}
        
        for kw in keywords:
            if kw in existing_keywords:
                # 이미 있으면 hit_count 증가
                for item in blocked_list:
                    if item["keyword"] == kw:
                        item["hit_count"] = item.get("hit_count", 1) + 1
                        break
            else:
                # 새로 추가
                blocked_list.append({
                    "keyword": kw,
                    "added_date": datetime.now().isoformat(),
                    "hit_count": 1
                })
                existing_keywords.add(kw)
        
        self.save()
    
    def get_blocked_keywords(self, category: str) -> Set[str]:
        """
        차단된 키워드 목록 반환
        
        Args:
            category: 업종
            
        Returns:
            차단된 키워드 Set
        """
        if category not in self.data["categories"]:
            category = "general"
        
        blocked_list = self.data["categories"][category]["blocked_keywords"]
        return {item["keyword"] for item in blocked_list}
    
    def filter_keywords(self, keywords: List[str], category: str) -> List[str]:
        """
        학습된 차단 키워드 제외
        
        Args:
            keywords: 원본 키워드 리스트
            category: 업종
            
        Returns:
            필터링된 키워드 리스트
        """
        blocked = self.get_blocked_keywords(category)
        return [kw for kw in keywords if kw not in blocked]
    
    def get_stats(self) -> Dict:
        """학습 통계 반환"""
        stats = {}
        for cat_name, cat_data in self.data["categories"].items():
            blocked = cat_data.get("blocked_keywords", [])
            stats[cat_name] = {
                "total_blocked": len(blocked),
                "top_blocked": sorted(
                    blocked, 
                    key=lambda x: x.get("hit_count", 1), 
                    reverse=True
                )[:5]
            }
        return stats


# 싱글톤 인스턴스
_learning_manager: Optional[LearningManager] = None


def get_learning_manager(base_dir: str = None) -> LearningManager:
    """학습 관리자 싱글톤 반환"""
    global _learning_manager
    if _learning_manager is None:
        _learning_manager = LearningManager(base_dir)
    return _learning_manager


# 테스트
if __name__ == "__main__":
    manager = get_learning_manager()
    
    # 미노출 키워드 학습
    manager.add_blocked_keywords(
        ["홍대 맛집 추천", "강남 피부과 잘하는곳"],
        "restaurant"
    )
    
    # 필터링 테스트
    keywords = ["홍대 맛집", "홍대 맛집 추천", "홍대 파스타"]
    filtered = manager.filter_keywords(keywords, "restaurant")
    
    print("원본:", keywords)
    print("필터링:", filtered)
    print("통계:", manager.get_stats())
