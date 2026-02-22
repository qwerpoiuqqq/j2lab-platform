"""
네이버 플레이스 키워드 추출기 (Naver Place Keyword Generator)
사용자가 입력한 검색어 또는 URL을 통해 플레이스 정보를 수집하고,
업종(맛집/병원/일반)에 맞는 최적화된 검색 키워드를 생성합니다.
"""
import asyncio
import sys
import os
from typing import Optional

from src.place_scraper import PlaceScraper
from src.keyword_generator import KeywordGenerator
from src.models import PlaceData

LOGO = """
=============================================
  Naver Place Smart Keyword Generator v1.0
=============================================
"""

async def process_keyword(input_str: str):
    """단일 입력 처리 로직"""
    print(f"\n[1/3] 데이터 수집 시작: {input_str}")
    
    place_data: Optional[PlaceData] = None
    
    async with PlaceScraper(headless=False) as scraper:
        if "place.naver.com" in input_str:
             # URL 직접 입력 시
            print("  - URL 모드로 동작합니다.")
            place_data = await scraper.get_place_data_by_url(input_str)
        else:
            # 검색어 입력 시
            print("  - 검색 모드로 동작합니다.")
            place_data = await scraper.get_place_data(input_str)
            
    if not place_data:
        print("\n❌ 실패: 데이터를 수집하지 못했습니다.")
        print("  - 검색어가 정확한지 확인해주세요.")
        print("  - 잠시 후 다시 시도해주세요.")
        return

    print(f"\n[2/3] 수집 완료: {place_data.name}")
    print(f"  - 카테고리: {place_data.category}")
    print(f"  - 지역: {place_data.region.gu} {place_data.region.dong}")
    print(f"  - 대표 키워드(keywordList): {place_data.keywords}")
    print(f"  - 진료과목: {place_data.medical_subjects}")
    if place_data.medical_subjects:
        print(f"  - 진료과목: {', '.join(place_data.medical_subjects)}")
    
    print("\n[3/3] 키워드 생성 중...")
    generator = KeywordGenerator()
    keywords = generator.generate(place_data)
    
    # 결과 출력
    print(f"\n✅ 생성된 키워드 (총 {len(keywords)}개):")
    print("-" * 40)
    for kw in keywords[:50]: # 화면엔 50개만 출력
        print(kw)
    if len(keywords) > 50:
        print(f"... 외 {len(keywords) - 50}개")
        
    # 파일 저장
    filename = f"result_{place_data.name}_{len(keywords)}개.txt"
    # 특수문자 제거
    filename = "".join(c for c in filename if c.isalnum() or c in "_. -가-힣")
    
    with open(filename, "w", encoding="utf-8") as f:
        for kw in keywords:
            f.write(f"{kw}\n")
            
    print("-" * 40)
    print(f"📁 파일 저장 완료: {os.path.abspath(filename)}")


async def main():
    print(LOGO)
    
    if len(sys.argv) > 1:
        # 커맨드라인 인자 모드
        input_str = sys.argv[1]
        await process_keyword(input_str)
    else:
        # 인터랙티브 모드
        while True:
            print("\n검색어 또는 플레이스 URL을 입력하세요 (종료: q):")
            user_input = input("> ").strip()
            
            if user_input.lower() in ["q", "quit", "exit"]:
                print("프로그램을 종료합니다.")
                break
                
            if not user_input:
                continue
                
            await process_keyword(user_input)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n중단되었습니다.")
    except Exception as e:
        print(f"\n오류 발생: {e}")
