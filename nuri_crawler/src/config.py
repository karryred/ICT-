
# URL Configuration
BASE_URL = "https://nuri.g2b.go.kr"
LIST_URL = "https://nuri.g2b.go.kr/"  # The main page usually loads the list

# Selectors
SELECTORS = {
    "list": {
        "grid_row": "tr.gridBodyDefault",
        "search_btn": "#mf_wfm_container_btnS0001, input[value='검색']",  # Added search button
        "link_column_index": 1,  # Based on intuition, usually valid. To be verified.
        "columns": {
            # This mapping might need adjustment after first run
            # Index is 0-based
            0: "row_num",
            1: "bid_no",          # 입찰공고번호
            2: "bid_type",        # 공고종류
            3: "bid_name",        # 입찰공고명 (This often contains the link)
            4: "agency",          # 공고기관
            5: "demand_agency",   # 수요기관
            6: "contract_method", # 계약방법
            6: "contract_method", # 계약방법
            7: "input_date",      # 입력일시
        },
        "pagination": {
            # WebSquare standard pagination controls
            # Try to catch the image button for 'next page' or the li.next
            "next_btn": "#mf_wfm_container_gen44_btn_next_page, .w2pageList_control_next, .w2pageList .w2pageList_next_btn, li.next",
            "page_list": ".w2pageList",
        }
    },
    "detail": {
        # Using label text to find values is more robust in WebSquare
        "fields_by_label": {
            "입찰공고번호": "bid_no",
            "입찰공고명": "bid_name",
            "공고종류": "bid_type",
            "공고처리구분": "process_type",
            "업무분류": "task_category",
            "입찰방식": "bid_method",
            "계약방법": "contract_method",
            "낙찰방법": "award_method",
            "재입찰여부": "re_bid",
            "입찰서접수시작일시": "bid_start_dt",
            "입찰서접수마감일시": "bid_end_dt",
            "개찰일시": "open_dt",
            "개찰장소": "open_place",
            "담당부서": "dept_name",
            "담당자": "manager_name",
        },
        "list_btn": ".w2trigger.btn_list, #mf_wfm_container_btn_list, a:has-text('목록'), img[alt='목록'], input[value='목록'], .btn_cm.list, button:has-text('목록')"
    }
}

# Crawler Configuration
TIMEOUT = 30000  # 30 seconds
HEADLESS = False  # Changed to False for manual execution/debugging
DELAY_BETWEEN_REQUESTS = 2.0  # Seconds - Standard delay

# Production Settings
MAX_RETRIES = 3
RETRY_DELAY = 2  # Seconds
MAX_DUPLICATE_LIMIT = 10  # Stop crawling after N consecutive duplicates
