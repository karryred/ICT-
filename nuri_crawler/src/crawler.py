from playwright.sync_api import sync_playwright, Page, BrowserContext
import time
import logging
from .config import LIST_URL, TIMEOUT, HEADLESS, SELECTORS, DELAY_BETWEEN_REQUESTS, MAX_RETRIES, RETRY_DELAY, MAX_DUPLICATE_LIMIT
from .parser import NuriParser
from .model import BidItem

logger = logging.getLogger(__name__)

from .state import StateManager
from .storage import Storage

class NuriCrawler:
    def __init__(self):
        self.parser = NuriParser()
        self.results = []
        self.state = StateManager()
        self.consecutive_duplicates = 0  # Track consecutive duplicate items

    def _retry(self, func, description, *args, **kwargs):
        """Retry a function with exponential backoff"""
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                wait_time = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"{description} failed (Attempt {attempt+1}/{MAX_RETRIES}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        
        logger.error(f"{description} failed after {MAX_RETRIES} attempts.")
        raise last_exception

    def _find_content_frame(self, page: Page):
        """Find the main content frame containing the grid."""
        target_frame = None
        
        # Extensive Frame Discovery Loop
        for attempt in range(15): # Retry up to 30 seconds (15 * 2s)
                # Refresh frames list
                frames = page.frames
                logger.info(f"Attempt {attempt+1}: Checking {len(frames)} frames...")
                
                for frame in frames:
                    try:
                        # Strategy 1: URL contains "BidPbancL" (List XML)
                        if "BidPbancL" in frame.url:
                            logger.info(f"Found content frame by URL: {frame.url}")
                            target_frame = frame
                            break
                        
                        # Strategy 2: Contains "입찰공고번호" (Header Text)
                        if frame.get_by_text("입찰공고번호", exact=False).count() > 0:
                                logger.info(f"Found content frame by Header Text: {frame.name}")
                                target_frame = frame
                                break
                        
                        # Strategy 3: Contains w2grid (WebSquare Grid)
                        if frame.locator(".w2grid").count() > 0:
                                logger.info(f"Found content frame by w2grid class: {frame.name}")
                                target_frame = frame
                                break
                                
                    except Exception as e:
                        pass
                        
                if target_frame: 
                    return target_frame
                
                # Check main page as fallback immediately if found there
                if page.locator(".w2grid").count() > 0:
                    logger.info("Found grid on MAIN PAGE.")
                    return page
                    
                time.sleep(2)
        return None

    def _navigate_to_list(self, page: Page):
        """Navigate to the list page from scratch (URL -> Popups -> Menu)."""
        logger.info(f"Navigating to {LIST_URL}...")
        try:
            # 1. Goto URL
            self._retry(lambda: page.goto(LIST_URL, timeout=TIMEOUT), "Navigate to URL")
            page.wait_for_load_state('networkidle')
            
            # 2. Close Popups
            logger.info("Checking for popups...")
            try:
                popup_closers = page.locator("input[type='button'].btn.close, .w2window_close, .w2trigger.btn.close")
                count = popup_closers.count()
                if count > 0:
                    for i in range(count):
                        if popup_closers.nth(i).is_visible():
                            try:
                                popup_closers.nth(i).click(timeout=1000)
                                time.sleep(0.5)
                            except: pass
                page.keyboard.press("Escape")
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Popup handling warning: {e}")

            # 3. Navigate Menu
            logger.info("Navigating menu...")
            
            # Hover Depth 1 "입찰공고"
            menu_1 = page.locator("a.depth1").filter(has_text="입찰공고").first
            if menu_1.count() > 0:
                 logger.info("Hovering Depth 1...")
                 menu_1.hover()
                 time.sleep(1.0)
            
            # Hover Depth 2 "입찰공고"
            menu_2 = page.locator("a.depth2").filter(has_text="입찰공고").first
            if menu_2.count() > 0 and menu_2.is_visible():
                 logger.info("Hovering Depth 2...")
                 menu_2.hover()
                 time.sleep(1.0)

            # Click Depth 3 "입찰공고목록"
            menu_3 = page.locator("a.depth3").filter(has_text="입찰공고목록").first
            if menu_3.count() > 0:
                logger.info("Clicking Depth 3 '입찰공고목록'...")
                if menu_3.is_visible():
                    self._retry(lambda: menu_3.click(), "Menu click")
                else:
                    logger.warning("Depth 3 not visible, forcing click...")
                    menu_3.evaluate("el => el.click()")
            else:
                logger.error("Menu '입찰공고목록' not found.")
                return None
                
            page.wait_for_load_state('networkidle')
            
            # 4. Wait for WebSquare Loading Spinner
            logger.info("Waiting for processing spinner to hide...")
            try:
                page.locator("iframe[name='__processbarIFrame']").wait_for(state="hidden", timeout=10000)
            except:
                logger.warning("Spinner wait timed out")

            # 5. Locate Content Frame
            logger.info("Locating Content Frame...")
            target_frame = self._find_content_frame(page)
            
            if not target_frame:
                logger.warning("Target content frame not found. Fallback to main page.")
                target_frame = page
            
            # 6. Verify List Page
            logger.info("Verifying List Page content...")
            try:
                target_frame.wait_for_selector(SELECTORS['list']['search_btn'], timeout=10000)
                logger.info("✓ List page loaded.")
                return target_frame
            except Exception as e:
                logger.error("Failed to verify list page load.")
                return None

        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return None

    def run(self):
        with sync_playwright() as p:
            # Enhanced Browser Launch for WebSquare Compatibility
            browser = p.chromium.launch(
                headless=HEADLESS,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-infobars',
                    '--window-size=1920,1080',
                ],
                ignore_default_args=["--enable-automation"]
            )
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
                locale='ko-KR',
                timezone_id='Asia/Seoul'
            )
            
            page = context.new_page()
            
            # Initial Navigation
            target_frame = self._navigate_to_list(page)
            if not target_frame:
                logger.error("Initial navigation failed. Exiting.")
                browser.close()
                return

            # 6. Click Search Button (Crucial Step)
            logger.info("Clicking Search Button to load data...")
            try:
                search_btn = target_frame.locator(SELECTORS['list']['search_btn'])
                if search_btn.count() > 0:
                    # Retry search button click
                    self._retry(lambda: search_btn.first.click(), "Search button click")
                    
                    page.wait_for_load_state('networkidle')
                    # Wait specifically for rows to appear
                    logger.info("Waiting for grid rows...")
                    try:
                        target_frame.locator(SELECTORS['list']['grid_row']).first.wait_for(state="visible", timeout=10000)
                    except:
                        logger.warning("Timeout waiting for first row.")
                else:
                    logger.warning("Search button not found with configured selector.")
                    
            except Exception as e:
                logger.error(f"Failed to click search button: {e}")
            


            # Pagination Loop
            TARGET_COUNT = 22
            page_num = 1
            stop_crawling = False
            
            while len(self.results) < TARGET_COUNT:
                if stop_crawling:
                     break
                     
                logger.info(f"Processing Page {page_num}...")
                
                # Ensure frame is valid
                if not target_frame or target_frame.is_detached():
                     target_frame = self._find_content_frame(page)
                
                if not target_frame:
                     logger.error("Content frame not found. Stopping.")
                     break

                # 7. Dynamic Grid Discovery (Re-run for each page)
                logger.info("Locating Grid in Frame...")
                rows_locator = None
                try:
                    # Strategy A: Find by Header Text "입찰공고번호" inside frame
                    if target_frame.get_by_text("입찰공고번호").count() > 0:
                        # Try multiple selectors for WebSquare grids
                        grid_selectors = [
                            ".w2grid_body tbody tr",
                            ".w2grid tbody tr", 
                            "tbody tr",
                        ]
                        
                        for selector in grid_selectors:
                            test_rows = target_frame.locator(selector)
                            row_count = test_rows.count()
                            if row_count > 0:
                                rows_locator = test_rows
                                logger.info(f"✓ Using selector: {selector}")
                                break
                    
                    # Strategy B: Fallback to Config Selector
                    if not rows_locator:
                        rows_locator = target_frame.locator(SELECTORS['list']['grid_row'])
                    
                    # Check if we have rows
                    count = rows_locator.count()
                    logger.info(f"Found {count} rows on page {page_num}")
                    
                    if count == 0:
                        logger.warning("No rows found. Stopping.")
                        break

                except Exception as e:
                    logger.error(f"Grid location failed: {e}")
                    break
                
                # Process Rows on Current Page
                # Data Loading Wait: Ensure first row has text
                try:
                    for _ in range(10):
                        if rows_locator.first.inner_text().strip():
                            break
                        time.sleep(0.5)
                except: pass

                processed_on_page = 0
                for i in range(count):
                    if len(self.results) >= TARGET_COUNT:
                        break
                    
                    if target_frame.is_detached():
                        logger.warning("Frame detached during row processing. Restarting grid discovery.")
                        break
                        
                    row = rows_locator.nth(i)
                    
                    try:
                        # Optimization 1: System Row Check (Class/ID/Style)
                        try:
                           id_attr = row.get_attribute("id") or ""
                           style_attr = row.get_attribute("style") or ""
                           class_attr = row.get_attribute("class") or ""
                           
                           if "scroll" in id_attr or "display: none" in style_attr or "height:0px" in style_attr or "w2grid_hidedRow" in class_attr:
                               logger.debug(f"Skipping system/hidden row {i}")
                               continue
                        except: pass

                        # Optimization 2: Visibility Check (Fastest)
                        if not row.is_visible():
                            logger.debug(f"Skipping hidden row {i}")
                            continue

                        # Optimization 3: Cell Count Check
                        # Data rows must have at least 5 columns
                        if row.locator("td").count() < 5:
                            logger.debug(f"Skipping row {i} (insufficient columns)")
                            continue

                        # Optimization 4: Skip empty text rows
                        row_text = row.inner_text().strip()
                        if not row_text:
                            logger.debug(f"Skipping empty text row {i}")
                            continue
                            
                        bid_no = ""
                        # Try to find bid_no in the row text or specific cells
                        # ...
                        # Extract bid number from first or second column
                        bid_no = row.locator('td').nth(1).inner_text().strip()
                        
                        if not bid_no:
                            logger.debug(f"Skipping row {i}: Empty bid_no")
                            continue
                            
                    except:
                        # If any of the above fails (e.g. detached), skip
                        continue
                    
                    # Smart Resume / Duplicate Checks
                    if self.state.is_visited(bid_no):
                        self.consecutive_duplicates += 1
                        logger.info(f"Skipping already visited: {bid_no} (Consecutive: {self.consecutive_duplicates})")
                        
                        if self.consecutive_duplicates >= MAX_DUPLICATE_LIMIT:
                            logger.info(f"Smart Resume: Reached {MAX_DUPLICATE_LIMIT} consecutive duplicates. Stopping crawler.")
                            stop_crawling = True
                            break
                        continue
                    else:
                        # Reset counter on new item
                        self.consecutive_duplicates = 0


                    try:
                        # Strategy: Find clickable link in row
                        link = None
                        
                        # 1. Try to find any visible anchor tag in the row
                        anchors = row.locator('a')
                        anchor_count = anchors.count()
                        
                        if anchor_count > 0:
                            # Find first visible anchor (skip hidden ones)
                            for j in range(anchor_count):
                                try:
                                    candidate = anchors.nth(j)
                                    if candidate.is_visible(timeout=1000):
                                        link = candidate
                                        break
                                except:
                                    continue
                        
                        # 2. If no visible anchor found, try clicking specific td columns
                        if not link:
                            # Try different columns (skip nth(2) which might be fixed)
                            for col_idx in [1, 3, 4]:  # Try columns 2, 4, 5
                                try:
                                    td = row.locator('td').nth(col_idx)
                                    if td.count() > 0:
                                        td_anchor = td.locator('a').first
                                        if td_anchor.count() > 0 and td_anchor.is_visible(timeout=1000):
                                            link = td_anchor
                                            break
                                except:
                                    continue
                        
                        # 3. Last resort: click the row itself
                        if not link:
                            logger.warning(f"No anchor found in row {i}, clicking row itself")
                            link = row
                        
                        link_text = link.inner_text().strip() if link else ""
                        logger.info(f"Processing row {i}: {link_text[:50]}... (Bid: {bid_no})")
                        
                        # Scroll into view before clicking
                        try:
                            link.scroll_into_view_if_needed(timeout=3000)
                        except:
                            pass
                        
                        # Click with timeout and force fallback
                        try:
                            self._retry(lambda: link.click(timeout=10000), "Click row link")
                        except Exception as click_error:
                            logger.warning(f"Normal click failed, trying force click: {click_error}")
                            link.click(force=True)
                        
                        # Wait for the detail page content to load in the frame
                        try:
                            target_frame.wait_for_selector("label:has-text('입찰공고번호')", timeout=15000)
                            time.sleep(1)
                        except Exception as wait_error:
                            logger.warning(f"Timeout waiting for detail content: {wait_error}")
                        
                        # Get the detail page content from the frame
                        detail_html = target_frame.content()
                        detail_url = target_frame.url
                        
                        # Retry parsing if it fails? (Usually CPU bound, not network, but maybe good for robustness)
                        try:
                            item = self.parser.parse_detail(detail_html, detail_url)
                        except Exception as parse_e:
                            logger.error(f"Parsing failed for {bid_no}: {parse_e}")
                            item = BidItem() # Empty item
                        
                        if item.bid_no:
                            self.results.append(item)
                            self.state.mark_visited(item.bid_no)
                            self.state.save_state()  # Save state incrementally
                            logger.info(f"✓ Parsed: {item.bid_no} - {item.bid_name} ({len(self.results)}/{TARGET_COUNT})")
                            processed_on_page += 1
                            
                            # Incremental Save
                            try:
                                Storage.save_json(self.results, "data/results.json")
                            except Exception as e:
                                logger.error(f"Incremental save failed: {e}")
                        else:
                            logger.warning(f"Failed to extract bid_no from detail page")
                        
                        # --- Navigation Back Logic ---
                        back_success = False
                        
                        # Strategy 1: Click 'List' button in Detail Page (Best for WebSquare)
                        try:
                            # Verify frame is still attached
                            if target_frame.is_detached():
                                target_frame = self._find_content_frame(page)
                                
                            if target_frame:
                                list_btn_selector = SELECTORS['detail'].get('list_btn')
                                if list_btn_selector:
                                    list_btn = target_frame.locator(list_btn_selector).first
                                    if list_btn.is_visible(timeout=2000):
                                        logger.info("Clicking 'List' button on detail page...")
                                        list_btn.click()
                                        back_success = True
                        except Exception as e:
                            logger.warning(f"List button strategy failed: {e}")

                        # Strategy 2: Browser Back (History)
                        if not back_success:
                            logger.info("List button not found/clicked. Trying browser back...")
                            try:
                                page.go_back()
                                back_success = True
                            except Exception as e:
                                logger.warning(f"Browser back failed: {e}")

                        # Verification & Recovery
                        try:
                            # Re-locate frame if needed
                            if target_frame.is_detached():
                                target_frame = self._find_content_frame(page)
                                
                            if target_frame:
                                # Check if we are back on list
                                try:
                                    # Wait for search button or grid to confirm list page
                                    target_frame.wait_for_selector(SELECTORS['list']['search_btn'], timeout=3000)
                                    logger.info("✓ Returned to list page (verified).")
                                    back_success = True
                                    
                                    # Ensure Grid is Visible again
                                    try:
                                        target_frame.locator(SELECTORS['list']['grid_row']).first.wait_for(state="visible", timeout=3000)
                                    except:
                                        logger.warning("Grid rows not immediately visible, might need search click.")
                                        
                                except:
                                    back_success = False # Verification failed
                            
                            # Strategy 3: Soft Recovery (Menu Click)
                            if not back_success:
                                logger.warning("Still on detail page or lost. Executing SOFT RECOVERY (Menu Click)...")
                                try:
                                    menu_3 = page.locator("a.depth3").filter(has_text="입찰공고목록").first
                                    if menu_3.is_visible():
                                        menu_3.click()
                                        logger.info("Clicked menu item. Waiting for list...")
                                        # Wait for list to load
                                        target_frame = self._find_content_frame(page) # Re-find frame
                                        if target_frame:
                                            target_frame.wait_for_selector(SELECTORS['list']['search_btn'], timeout=5000)
                                            logger.info("✓ SOFT RECOVERY SUCCESS: Menu click returned to list.")
                                            back_success = True
                                except Exception as e:
                                    logger.warning(f"Soft recovery failed: {e}")

                            # Strategy 4: Hard Recovery (Full Reset) - Last Resort
                            if not back_success:
                                logger.error("All back strategies failed. Executing HARD RECOVERY (Full Restart & Navigation)...")
                                # FORCE RECOVERY: Call _navigate_to_list to reset everything
                                try:
                                    # Refresh page and re-do menu
                                    new_frame = self._navigate_to_list(page)
                                    if new_frame:
                                        target_frame = new_frame
                                        # Click search button again to ensure data?
                                        try:
                                             search_btn = target_frame.locator(SELECTORS['list']['search_btn'])
                                             if search_btn.count() > 0:
                                                 search_btn.first.click()
                                                 target_frame.locator(SELECTORS['list']['grid_row']).first.wait_for(state="visible", timeout=10000)
                                        except: pass
                                        
                                        logger.info("✓ HARD RECOVERY SUCCESS: Full navigation reset completed.")
                                        back_success = True
                                        
                                        # Reset page_num logic because hard recovery usually resets pagination to 1
                                        # If we were on page 2, we are now on page 1.
                                        # This is a limitation of hard recovery.
                                        logger.warning("Hard recovery resets pagination. Crawler might re-process page 1.")
                                        
                                    else:
                                        logger.error("Recovery failed: Reference frame not found.")
                                except Exception as recovery_e:
                                    logger.error(f"Recovery failed: {recovery_e}")
                                    
                        except Exception as e:
                            logger.error(f"Failed to verify/recover list state: {e}")

                    except Exception as e:
                        logger.error(f"Failed to process row {i}: {e}")
                        # Try to recover navigation via menu (last ditch)
                        try: 
                             page.locator("a.depth3").filter(has_text="입찰공고목록").first.click()
                             time.sleep(3)
                        except: pass
                    
                    time.sleep(DELAY_BETWEEN_REQUESTS)
                
                if stop_crawling:
                     break

                # Check if we need more items
                if len(self.results) >= TARGET_COUNT:
                    logger.info(f"Reached target count ({len(self.results)}). Stopping.")
                    break
                
                # Pagination Logic: Click Next Page
                logger.info("Attempting to move to next page...")
                pagination_success = False
                
                try:
                    # Strategy 1: removed (generic next buttons often skip to next block 1->11)
                    # We will rely solely on explicit page number clicking below
                    pass
                    
                    # Strategy 2: Click page number using index attribute (accurate page selection)
                    if not pagination_success:
                        try:
                            next_page = page_num + 1
                            logger.info(f"Trying to find page {next_page}...")
                            
                            # Simplified Pagination Strategy
                            
                            # Strategy 1: Find by exact text and click (Most robust)
                            try:
                                # Try locating by index attribute (from user feedback)
                                # <a id="mf_wfm_container_pagelist_page_2" index="2" ...>2</a>
                                page_link_index = target_frame.locator(f"a[index='{next_page}']").first
                                if page_link_index.count() > 0 and page_link_index.is_visible():
                                     logger.info(f"Found page {next_page} by index='{next_page}'. Clicking...")
                                     page_link_index.click()
                                     pagination_success = True
                                else:
                                     # Try locating by ID pattern
                                     page_link_id = target_frame.locator(f"#mf_wfm_container_pagelist_page_{next_page}").first
                                     if page_link_id.count() > 0:
                                          logger.info(f"Found page {next_page} by ID. Clicking...")
                                          page_link_id.click()
                                          pagination_success = True
                                     else:
                                          # Try locating by text directly
                                          page_link = target_frame.locator(f"a:text-is('{next_page}')").first
                                          if page_link.count() > 0 and page_link.is_visible():
                                               logger.info(f"Found page {next_page} by text-is. Clicking...")
                                               page_link.click()
                                               pagination_success = True
                                          else:
                                               # Try with specific classes if generic fails
                                               candidate = target_frame.locator(f".w2pageList_label:text-is('{next_page}')").first
                                               if candidate.count() > 0:
                                                    candidate.click()
                                                    pagination_success = True
                                               else:
                                                    # Try partial text allowing for whitespace
                                                    candidate_lax = target_frame.locator(f"a:has-text('{next_page}')").filter(has_text=f"^{next_page}$").first
                                                    if candidate_lax.count() > 0:
                                                        candidate_lax.click()
                                                        pagination_success = True
                            except Exception as e:
                                logger.warning(f"Standard pagination click failed: {e}")

                            # Strategy 2: 'Next' Image Button (Arrow)
                            if not pagination_success:
                                try:
                                    next_btn = target_frame.locator(SELECTORS['list']['pagination']['next_btn']).first
                                    if next_btn.count() > 0 and next_btn.is_visible():
                                         logger.info("Clicking 'Next' button...")
                                         next_btn.click()
                                         pagination_success = True
                                except Exception as e:
                                    logger.warning(f"Next button strategy failed: {e}")

                            # Strategy 3: Javascript Fallback (Simpler)
                            if not pagination_success:
                                try:
                                    # Try by ID specifically in JS
                                    js_code_id = f"""() => {{
                                        const el = document.getElementById('mf_wfm_container_pagelist_page_{next_page}');
                                        if (el) {{
                                            el.click();
                                            return true;
                                        }}
                                        return false;
                                    }}"""
                                    if target_frame.evaluate(js_code_id):
                                         logger.info(f"Clicked page {next_page} via JS ID fallback.")
                                         pagination_success = True
                                    else:
                                        # Generic JS
                                        js_code = f"""() => {{
                                            const links = document.querySelectorAll('a, li, div');
                                            for (const link of links) {{
                                                if (link.innerText.trim() === '{next_page}' && link.offsetParent !== null) {{
                                                    link.click();
                                                    return true;
                                                }}
                                            }}
                                            return false;
                                        }}"""
                                        if target_frame.evaluate(js_code):
                                            logger.info(f"Clicked page {next_page} via JS fallback.")
                                            pagination_success = True
                                except Exception as e:
                                    logger.warning(f"JS fallback failed: {e}")

                            if pagination_success:
                                page_num = next_page
                                page.wait_for_load_state('networkidle')
                                time.sleep(3)
                            else:
                                logger.warning(f"Could not find link for page {next_page}")
                                # Debug: Print available numbers
                                try:
                                     texts = target_frame.locator(".w2pageList_label, .w2pageList a").all_inner_texts()
                                     logger.info(f"Visible generic pagination links: {texts}")
                                except: pass
                                
                        except Exception as e:
                            logger.debug(f"Page number strategy failed: {e}")
                    
                    if not pagination_success:
                        logger.info("Could not find or click pagination button. End of list.")
                        # Dump HTML for debugging
                        try:
                            html = target_frame.content()
                            with open("data/debug_pagination.html", "w", encoding="utf-8") as f:
                                f.write(html)
                            logger.info("Saved debug_pagination.html")
                        except: pass
                        break
                        
                except Exception as e:
                    logger.error(f"Pagination failed: {e}")
                    break

            
            browser.close()
            
            # Save results
            self.state.save_state()
            
            if self.results:
                logger.info("Attempting to save results...")
                try:
                    Storage.save_json(self.results, "data/results.json")
                    logger.info("✓ Saved to data/results.json")
                except Exception as e:
                    logger.error(f"Failed to save JSON: {e}")

                try:
                    Storage.save_excel(self.results, "data/results.xlsx")
                    logger.info("✓ Saved to data/results.xlsx")
                except Exception as e:
                    logger.error(f"Failed to save Excel: {e}")
            else:
                logger.warning("No results to save")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    crawler = NuriCrawler()
    crawler.run()
