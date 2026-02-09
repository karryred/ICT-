
import csv
import json
import os
from typing import List
from .model import BidItem
import pandas as pd
from openpyxl.utils import get_column_letter

import logging
logger = logging.getLogger(__name__)

class Storage:
    @staticmethod
    def save_csv(items: List[BidItem], filename: str):
        if not items:
            return
            
        keys = items[0].to_dict().keys()
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        mode = 'w'
        write_header = True
        
        with open(filename, mode, newline='', encoding='utf-8-sig') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            if write_header:
                writer.writeheader()
            for item in items:
                writer.writerow(item.to_dict())

    @staticmethod
    def save_json(items: List[BidItem], filename: str):
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        data = [item.to_dict() for item in items]
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def save_excel(items: List[BidItem], filename: str):
        """
        Save items to Excel file with all raw_data fields expanded.
        Nested lists (grids) are saved to separate sheets.
        
        Args:
            items: List of BidItem objects
            filename: Output Excel filename
        """
        if not items:
            logger.info("No items to save.")
            return
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else '.', exist_ok=True)
        
        # 1. Prepare Main Sheet and Sub-grids
        main_rows = []
        all_detected_keys = []
        sub_grids = {} # { sheet_name: [all_rows_across_all_items] }
        
        for item in items:
            if not item.raw_data:
                continue
                
            bid_no = item.bid_no
            main_row = {'상세페이지URL': item.url}
            
            for k, v in item.raw_data.items():
                clean_k = k.strip()
                
                # Check if value is a list (discovered grid)
                if isinstance(v, list):
                    # Store in sub_grids
                    sheet_name = clean_k[:31] if clean_k else "Grid_Data"  # Excel sheet name limit
                    # Ensure sheet name is not empty
                    if not sheet_name.strip():
                        sheet_name = "Grid_Data"
                    if sheet_name not in sub_grids:
                        sub_grids[sheet_name] = []
                    
                    for grid_row in v:
                        # Prepend bid_no for reference
                        flat_row = {'입찰공고번호': bid_no}
                        flat_row.update(grid_row)
                        sub_grids[sheet_name].append(flat_row)
                    
                    # Store a placeholder in main sheet
                    main_row[clean_k] = f"[Sub-grid: See Sheet '{sheet_name}']"
                else:
                    # Normal key-value parsing
                    if clean_k not in all_detected_keys:
                        all_detected_keys.append(clean_k)
                    
                    if isinstance(v, str):
                        cleaned_v = " ".join(v.split())
                        main_row[clean_k] = cleaned_v
                    else:
                        main_row[clean_k] = v
            
            main_rows.append(main_row)
        
        if not main_rows:
            logger.info("No valid data rows found.")
            return

        # 2. Save using ExcelWriter
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # A. Process Main Sheet
            df_main = pd.DataFrame(main_rows)
            priority_keys = ['입찰공고번호', '입찰공고명', '공고명', '수요기관', '공고기관', '계약방법', '상세페이지URL']
            cols_to_use = [ck for ck in priority_keys if ck in df_main.columns]
            for k in all_detected_keys:
                if k not in cols_to_use and k in df_main.columns:
                    cols_to_use.append(k)
            
            df_main = df_main[cols_to_use].dropna(axis=1, how='all')
            df_main.to_excel(writer, index=False, sheet_name='입찰공고요약')
            Storage._auto_adjust_columns(writer, '입찰공고요약', df_main)
            
            # B. Process Sub-grids
            for sheet_name, grid_rows in sub_grids.items():
                if not grid_rows: continue
                df_sub = pd.DataFrame(grid_rows)
                # Sheet names must be unique and valid
                safe_name = sheet_name.replace(':', '_').replace('/', '_').replace('*', '_')
                df_sub.to_excel(writer, index=False, sheet_name=safe_name)
                Storage._auto_adjust_columns(writer, safe_name, df_sub)
        
        logger.info(f"Saved {len(main_rows)} items to {filename} (Sub-sheets: {list(sub_grids.keys())})")

    @staticmethod
    def _auto_adjust_columns(writer, sheet_name, df):
        """Helper to auto-adjust column widths in a sheet."""
        worksheet = writer.sheets[sheet_name]
        for idx, col in enumerate(df.columns):
            max_len = max(
                df[col].astype(str).map(len).max(),
                len(str(col))
            )
            col_letter = get_column_letter(idx + 1)
            worksheet.column_dimensions[col_letter].width = min(max_len + 5, 80)


