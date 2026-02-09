# Nuri G2B Crawler (누리장터 크롤러)

본 프로젝트는 `[2026 ICT_리코] 인턴십 개발 과제`의 일환으로 개발된 누리장터(G2B) 입찰 공고 크롤러입니다.  
Playwright를 사용하여 동적 웹 페이지(WebSquare)를 제어하며, 안정적인 데이터 수집과 복구 기능을 제공합니다.

## 1. 실행 방법 (Local Reproduction)

### 환경 설정
본 프로젝트는 **Python 3.8 이상** 환경에서 실행을 권장합니다.

1.  **저장소 클론 및 이동**
    ```bash
    git clone https://github.com/karryred/ICT.git
    cd nuri_crawler
    ```

2.  **가상 환경 생성 및 활성화 (권장)**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Mac/Linux
    source venv/bin/activate
    ```

3.  **의존성 설치**
    ```bash
    pip install -r requirements.txt
    playwright install chromium
    ```

### 크롤러 실행
```bash
python main.py
```
- 실행 시 브라우저가 열리며(Headless=False 설정 시) 크롤링 과정이 진행됩니다.
- 수집된 데이터는 `data/results.json` 및 `data/results.xlsx` 파일로 저장됩니다.
- 중단 시 `data/state.json`을 통해 이전에 방문한 입찰 공고는 건너뛰고 실행됩니다.

---

## 2. 의존성 및 환경

- **Python Version**: 3.8+
- **주요 라이브러리**:
    - `playwright`: 동적 웹 페이지(Javascript, WebSquare) 제어 및 데이터 추출
    - `pandas`: 데이터 구조화 및 처리
    - `openpyxl`: Excel 파일 저장 지원
    - `beautifulsoup4`: HTML 파싱 보조 (필요 시)
    - `lxml`: XML/HTML 처리 속도 최적화

상세 버전은 `requirements.txt`를 참고하십시오.

---

## 3. 설계 및 주요 가정

### 아키텍처
- **Crawler (`src/crawler.py`)**: 브라우저 제어, 페이지 탐색, 페이지네이션 처리, 예외 상황 복구(Recovery) 담당.
    - *참고: 현재 기본 수집 개수(`TARGET_COUNT`)는 `22개`로 하드코딩 되어 있습니다.*
- **Parser (`src/parser.py`)**: 상세 페이지 HTML에서 필요한 필드(공고번호, 명칭, 마감일 등) 추출.
- **Model (`src/model.py`)**: 입찰 공고 데이터(`BidItem`)의 구조 정의 (Data Class).
- **Storage (`src/storage.py`)**: 수집된 데이터를 JSON, CSV, Excel 파일로 저장하며, 엑셀 저장 시 서브 그리드(Sub-grid) 분리 및 스타일 조정 담당.
- **State Manager (`src/state.py`)**: 중복 수집 방지 및 진행 상황 저장 (Incremental Crawling).
- **Config (`src/config.py`)**: URL, 선택자(Selector), 타임아웃 등 설정 값 관리.

### 주요 설계 포인트
1.  **견고한 탐색 (Robust Navigation)**:
    - WebSquare 그리드 및 동적 로딩을 처리하기 위해 `iframe` 자동 감지 및 재진입 로직 구현.
    - 팝업 자동 닫기 및 메뉴 이동(`입찰공고목록`) 자동화.
2.  **복구 전략 (Recovery Strategy)**:
    - 상세 페이지 진입 후 '목록' 버튼 클릭 실패 시, 브라우저 '뒤로 가기' -> 메뉴 재진입(Soft Recovery) -> 전체 새로고침(Hard Recovery) 순으로 복구 시도.
3.  **최적화 (Optimization)**:
    - 빈 행(스크롤바, 시스템 행)을 `id`, `style` 속성으로 즉시 식별하여 불필요한 처리 스킵.
    - 페이지네이션 시 텍스트 및 `index` 속성을 활용하여 정확한 페이지 이동 보장.

### 주요 가정
- 대상 사이트(`nuri.g2b.go.kr`)의 HTML 구조(WebSquare 프레임워크)가 크게 변경되지 않는다고 가정합니다.
- 네트워크 상태가 불안정할 경우를 대비해 `Exponential Backoff` 방식의 재시도 로직이 적용되어 있습니다.

---

## 4. 한계 및 개선 아이디어

### 한계점 (Limitations)
- **DOM 의존성**: 웹 사이트의 DOM 구조나 Class 명이 변경될 경우 수집이 실패할 수 있습니다. (Config 파일로 선택자 관리)
- **속도**: 단일 브라우저/단일 탭으로 순차 수집하므로 대량 데이터 수집 시 속도 한계가 있습니다.
- **메모리**: 장시간 실행 시 브라우저 리소스 점유율이 높아질 수 있습니다.

### 개선 아이디어 (Improvements)
1.  **병렬 처리**: `asyncio` 및 Playwright의 비동기 기능을 활용하여 다중 탭/브라우저로 동시 수집 구현.
2.  **데이터베이스 연동**: 로컬 파일(`json/xlsx`) 대신 SQLite/PostgreSQL 등 DB에 저장하여 데이터 무결성 및 조회 성능 확보.
3.  **Headless 모드**: 개발/디버깅 완료 후 `HEADLESS = True`로 설정하여 서버 환경에서 리소스 효율성 증대.
4.  **API 활용**: 가능하다면 공공데이터포털(OpenAPI)을 활용하여 크롤링 부하 감소 및 정확도 향상.

---

## 5. 주기적 실행 (Periodic Execution) 구성

크롤러를 주기적(Interval/Cron)으로 실행하기 위한 방법은 다음과 같습니다.

### 방법 A: Python 라이브러리 `schedule` 사용
`main.py` 또는 별도의 스케줄러 스크립트를 작성하여 루프 내에서 실행합니다.
```python
import schedule
import time
import subprocess

def job():
    print("크롤러 실행 중...")
    subprocess.run(["python", "main.py"])

# 매일 09:00 실행
schedule.every().day.at("09:00").do(job)
# 또는 1시간마다 실행
# schedule.every(1).hours.do(job)

while True:
    schedule.run_pending()
    time.sleep(1)
```

### 방법 B: 운영체제 스케줄러 사용 (권장)
**Windows (Task Scheduler)**
1.  `작업 스케줄러` 실행 -> `기본 작업 만들기`.
2.  트리거 설정 (예: 매일, 매 시간).
3.  동작: `프로그램 시작` -> `python.exe` 경로 입력, 인수로 `main.py` 경로 설정.

**Linux (Crontab)**
1.  `crontab -e` 명령어로 설정 파일 편집.
2.  예: 매시간 정각에 실행
    ```cron
    0 * * * * cd /path/to/nuri_crawler && /usr/bin/python3 main.py >> crawler.log 2>&1
    ```
