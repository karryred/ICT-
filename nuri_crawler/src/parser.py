
from bs4 import BeautifulSoup
from .model import BidItem
from .config import SELECTORS
import logging

logger = logging.getLogger(__name__)

class NuriParser:
    def parse_detail(self, html_content: str, url: str = None) -> BidItem:
        """
        Parse detail page HTML to extract bid information using label-value pairs.
        
        Labels: <label class="w2textbox ">입찰공고번호</label>
        Values: <span class="w2textbox v-m">R26BK01323461-000</span>
        
        Args:
            html_content: HTML content of the detail page
            url: URL of the detail page
            
        Returns:
            BidItem with extracted data
        """
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Dictionary to store all extracted key-value pairs
        data = {}
        
        # Extract category sections (e.g., "공고일반")
        categories = soup.find_all('div', class_='df_tit')
        logger.info(f"Found {len(categories)} category sections")
        
        # Dictionary to store all extracted key-value pairs
        data = {}
        
        # Strategy: Sequential mapping of label -> span
        # Find all relevant elements in the container
        # We look for all 'label' and 'span' with class 'w2textbox'
        elements = soup.find_all(['label', 'span'], class_='w2textbox')
        logger.info(f"Found {len(elements)} relevant elements for pairing")
        
        current_key = None
        for el in elements:
            text = el.get_text(strip=True)
            if not text:
                continue
            
            if el.name == 'label':
                # This is a key
                current_key = text
            elif el.name == 'span' and current_key:
                # This is a value for the pending key
                data[current_key] = text
                logger.debug(f"Mapped: {current_key} -> {text}")
                current_key = None # Clear key after mapping to a value

        
        # 2. Extract Additional Grids (Construct Details, Competitors, etc.)
        grids_data = self._extract_all_grids(soup)
        data.update(grids_data)
        
        logger.info(f"Total extracted fields (inc. grids): {len(data)}")
        
        # Create BidItem with required fields
        item = BidItem(
            bid_no=data.get('입찰공고번호', ''),
            bid_name=data.get('공고명', data.get('입찰공고명', '')),
            url=url
        )
        
        # Store all extracted data for later use
        item.raw_data = data
        
        return item

    def _extract_all_grids(self, soup: BeautifulSoup) -> dict:
        """
        Extract all tables/grids found in the page.
        Identifies grids by looking for .w2grid containers and their preceding titles.
        """
        results = {}
        
        # Find all grid containers
        grid_containers = soup.select('div.w2grid')
        logger.info(f"Found {len(grid_containers)} potential grid containers")
        
        for container in grid_containers:
            # Try to find the title for this grid
            # Usually it's in a div.df_tit or similar above the grid
            title = "Unknown Grid"
            
            # Look for preceding sibling with title class
            prev_el = container.find_previous(['div', 'h3', 'h4'], class_=['df_tit', 'tit', 'w2textbox'])
            if prev_el:
                title = prev_el.get_text(strip=True)
            
            # Extract header and rows
            rows = self._parse_ws_grid(container)
            if rows:
                results[title] = rows
                logger.info(f"Extracted grid '{title}' with {len(rows)} rows")
        
        return results

    def _parse_ws_grid(self, grid_div: BeautifulSoup) -> list:
        """
        Parse a WebSquare grid container.
        """
        # 1. Get headers
        headers = []
        head_elements = grid_div.select('.w2grid_head_sort_div_main_outer nobr')
        if not head_elements:
             # Fallback: look for any th or common header cells
             head_elements = grid_div.select('thead th, .w2grid_hRow td')
             
        for head in head_elements:
            headers.append(head.get_text(strip=True))
        
        if not headers:
            return []
            
        # 2. Get rows
        grid_rows = []
        # WebSquare usually puts rows in a table inside .w2grid_body
        body_table = grid_div.select_one('.w2grid_body_table, .w2grid_body table')
        if not body_table:
            # Fallback: find any tbody tr within the grid div
            body_rows = grid_div.select('tbody tr, .w2grid_body tr')
        else:
            body_rows = body_table.select('tr')
            
        for tr in body_rows:
            cells = tr.select('td')
            if not cells: continue
            
            row_data = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    key = headers[i]
                    # Values are often in nobr or span with specific class
                    val_el = cell.select_one('nobr, span, input')
                    val = val_el.get_text(strip=True) if val_el else cell.get_text(strip=True)
                    row_data[key] = val
            
            if row_data:
                grid_rows.append(row_data)
                
        return grid_rows

    def parse_list(self, html_content: str):
        pass

