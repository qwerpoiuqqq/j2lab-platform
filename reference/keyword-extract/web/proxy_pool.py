"""
프록시 슬롯 분배 모듈

settings.json의 프록시를 5개 슬롯으로 균등 분배:
- Slot 1: ports 10001~10100
- Slot 2: ports 10101~10200
- Slot 3: ports 10201~10300
- Slot 4: ports 10301~10400
- Slot 5: ports 10401~10500
"""

import json
import os
from typing import List, Dict, Optional


class ProxyPool:
    """프록시 슬롯 분배기"""

    MAX_SLOTS = 5
    PORTS_PER_SLOT = 100
    BASE_PORT = 10001

    def __init__(self, settings_path: str = "settings.json"):
        self.settings_path = settings_path
        self._settings: Dict = {}
        self._proxy_list: List[Dict] = []
        self._slots: Dict[int, List[Dict]] = {}  # slot_number -> proxy list
        self._load_settings()

    def _load_settings(self):
        """settings.json 로드 및 슬롯 분배"""
        if not os.path.exists(self.settings_path):
            print(f"[ProxyPool] settings.json not found: {self.settings_path}")
            return

        with open(self.settings_path, "r", encoding="utf-8") as f:
            self._settings = json.load(f)

        self._proxy_list = self._settings.get("proxy_list", [])
        self._distribute_slots()

    def _distribute_slots(self):
        """프록시를 포트 범위 기반으로 5개 슬롯에 분배"""
        self._slots = {i: [] for i in range(1, self.MAX_SLOTS + 1)}

        for proxy in self._proxy_list:
            port = proxy.get("port", 0)
            if port < self.BASE_PORT:
                continue

            # 포트 번호로 슬롯 결정
            offset = port - self.BASE_PORT
            slot_number = (offset // self.PORTS_PER_SLOT) + 1

            if 1 <= slot_number <= self.MAX_SLOTS:
                self._slots[slot_number].append(proxy)

        for slot_num, proxies in self._slots.items():
            start_port = self.BASE_PORT + (slot_num - 1) * self.PORTS_PER_SLOT
            end_port = start_port + self.PORTS_PER_SLOT - 1
            print(f"[ProxyPool] Slot {slot_num}: {len(proxies)} proxies (ports {start_port}~{end_port})")

    def get_slot_proxies(self, slot_number: int) -> List[Dict]:
        """특정 슬롯의 프록시 목록 반환"""
        if slot_number < 1 or slot_number > self.MAX_SLOTS:
            return []
        return self._slots.get(slot_number, [])

    def get_slot_proxy_dicts(self, slot_number: int) -> List[Dict]:
        """특정 슬롯의 프록시를 SmartWorker 호환 형식으로 반환

        각 프록시에 username/password 정보 추가
        """
        proxies = self.get_slot_proxies(slot_number)
        username = self._settings.get("decodo_username", "")
        password = self._settings.get("decodo_password", "")

        result = []
        for p in proxies:
            proxy_dict = dict(p)
            if username and "username" not in proxy_dict:
                proxy_dict["username"] = username
            if password and "password" not in proxy_dict:
                proxy_dict["password"] = password
            result.append(proxy_dict)

        return result

    def get_available_slot(self, used_slots: set) -> Optional[int]:
        """사용 가능한 슬롯 번호 반환 (없으면 None)"""
        for slot in range(1, self.MAX_SLOTS + 1):
            if slot not in used_slots and self._slots.get(slot):
                return slot
        return None

    @property
    def settings(self) -> Dict:
        """원본 설정 반환"""
        return self._settings

    @property
    def gemini_api_key(self) -> str:
        return self._settings.get("gemini_api_key", "")

    @property
    def use_proxy(self) -> bool:
        return self._settings.get("use_proxy", True)

    @property
    def use_own_ip(self) -> bool:
        return self._settings.get("use_own_ip", False)

    @property
    def modifiers(self) -> Dict:
        return self._settings.get("modifiers", {})

    @property
    def users(self) -> List[Dict]:
        """사용자 계정 목록"""
        return self._settings.get("users", [])
