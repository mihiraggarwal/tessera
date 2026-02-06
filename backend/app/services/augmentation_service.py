import pandas as pd
import io
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

class AugmentationService:
    @staticmethod
    def analyze_csv(file_path: Path) -> Dict[str, Any]:
        """
        Analyze the top 10 rows of a CSV to detect schema and suggest mappings.
        Includes semantic detection for coordinates and combined columns.
        """
        try:
            # 1. Detect best separator
            seps = [',', '\t', ';']
            max_cols = -1
            best_sep = ','
            
            for s in seps:
                try:
                    temp_df = pd.read_csv(file_path, nrows=5, sep=s, engine='python')
                    if len(temp_df.columns) > max_cols:
                        max_cols = len(temp_df.columns)
                        best_sep = s
                except:
                    continue
            
            # 2. Initial read
            df = pd.read_csv(file_path, nrows=10, dtype=str, sep=best_sep, engine='python')
            
            # Detect if the header row is actually data or empty
            # Heuristics:
            unnamed_count = sum(1 for col in df.columns if str(col).strip().startswith('Unnamed:'))
            has_data_in_header = False
            for col in df.columns:
                s_col = str(col).strip()
                # If column name is a number (e.g. 28.6, 77N) or contains digits without enough letters
                # This catches headerless data while allowing things like 'Pincode' or 'Sector 1'
                if re.search(r"\d", s_col):
                    # If it's purely numeric/punctuation OR short alphanumeric (likely data)
                    if not re.search(r"[a-zA-Z]{4,}", s_col):
                        has_data_in_header = True
                        break
            
            is_headerless = (unnamed_count >= len(df.columns) / 2) or has_data_in_header
            
            if is_headerless:
                # Re-read with header=None using the BEST detected separator
                df = pd.read_csv(file_path, nrows=11, dtype=str, header=None, sep=best_sep, engine='python')
                
                # Drop rows that are entirely empty or purely commas/tabs
                while not df.empty:
                    first_row = df.iloc[0].astype(str).str.strip()
                    if (df.iloc[0].isna().all()) or (first_row == "").all() or (first_row == "nan").all():
                        df = df.iloc[1:].reset_index(drop=True)
                    else:
                        break
                
                # Name columns Column 1, Column 2... for easy mapping
                df.columns = [f"Column {i+1}" for i in range(len(df.columns))]
            
            # Atomic Cleanup: Trim all column values in sample
            df = df.apply(lambda x: x.str.strip() if hasattr(x, "str") else x)
            
            columns = df.columns.tolist()
            sample_data = df.to_dict(orient='records')
            
            # Suggest mapping based on column names and content analysis
            suggestions = {}
            for col in columns:
                col_lower = col.lower().strip().replace('_', ' ').replace('-', ' ')
                
                # Semantic Name Detection
                if any(x in col_lower for x in ['name', 'facility', 'title', 'label', 'site']):
                    if 'name' not in suggestions:
                        suggestions['name'] = col
                
                # Coordinate Detection
                if any(x == col_lower or x in col_lower.split() for x in ['lat', 'latitude', 'y']):
                    suggestions['lat'] = col
                if any(x == col_lower or x in col_lower.split() for x in ['lng', 'lon', 'longitude', 'x']):
                    suggestions['lng'] = col
                
                # Combined Coordinate Detection (e.g., "Location: 28.5, 77.2")
                if 'lat' not in suggestions or 'lng' not in suggestions:
                    # Check first row for comma/space separated numbers
                    first_val = str(df[col].iloc[0]) if not df[col].empty else ""
                    if ',' in first_val or ' ' in first_val:
                        nums = re.findall(r"[-+]?\d*\.\d+|\d+", first_val)
                        if len(nums) >= 2:
                            # If we found at least 2 numbers and the column name implies location
                            if any(x in col_lower for x in ['loc', 'coord', 'pos', 'point', 'lat']):
                                suggestions['lat'] = col
                                suggestions['lng'] = col
                
                # Metadata Detection
                if any(x in col_lower for x in ['type', 'category', 'class', 'kind']):
                    suggestions['type'] = col
                if any(x in col_lower for x in ['state', 'province', 'region']):
                    suggestions['state'] = col
                if any(x in col_lower for x in ['district', 'county', 'municipality']):
                    suggestions['district'] = col
            
            # Logic for generic "Column X" suggestions if nothing found
            if is_headerless:
                # Based on analysis above, or simple defaults:
                if 'name' not in suggestions and 'Column 1' in columns:
                    suggestions['name'] = 'Column 1'
                if 'lat' not in suggestions and 'Column 2' in columns:
                    suggestions['lat'] = 'Column 2'
                if 'lng' not in suggestions and 'Column 3' in columns:
                    suggestions['lng'] = 'Column 3'
            
            return {
                "version": "1.2.1-headerless-fix",
                "columns": columns,
                "sample_data": sample_data,
                "suggested_mapping": suggestions
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def clean_coordinate(val: Any) -> Optional[float]:
        """Extra numbers from a polluted string (e.g., '28.5 N' -> 28.5)"""
        if pd.isna(val): return None
        s = str(val).strip()
        # Extract first numeric-looking thing
        match = re.search(r"[-+]?\d*\.\d+|\d+", s)
        if match:
            try:
                num = float(match.group())
                # Handle S/W suffixes for negative coordinates
                if any(x in s.upper() for x in ['S', 'W']) and num > 0:
                    num = -num
                return num
            except ValueError:
                return None
        return None

    @staticmethod
    def transform_csv(input_path: Path, mapping: Dict[str, str], output_name: str) -> Path:
        """
        Transform a raw CSV into the standard format used by Tessera.
        Handles splitting, cleaning, and normalization.
        """
        # 1. Detect best separator
        seps = [',', '\t', ';']
        max_cols = -1
        best_sep = ','
        for s in seps:
            try:
                temp_df = pd.read_csv(input_path, nrows=5, sep=s, engine='python')
                if len(temp_df.columns) > max_cols:
                    max_cols = len(temp_df.columns)
                    best_sep = s
            except:
                continue
        
        # 2. Initial load
        df = pd.read_csv(input_path, dtype=str, sep=best_sep, engine='python')
        
        # Detect and fix headerless data
        unnamed_count = sum(1 for col in df.columns if str(col).strip().startswith('Unnamed:'))
        has_data_in_header = False
        for col in df.columns:
            s_col = str(col).strip()
            if re.search(r"\d", s_col) and not re.search(r"[a-zA-Z]{4,}", s_col):
                has_data_in_header = True
                break
        
        is_headerless = (unnamed_count >= len(df.columns) / 2) or has_data_in_header
        
        if is_headerless:
            df = pd.read_csv(input_path, dtype=str, header=None, sep=best_sep, engine='python')
            # Drop empty first rows
            while not df.empty:
                first_row = df.iloc[0].astype(str).str.strip()
                if (df.iloc[0].isna().all()) or (first_row == "").all() or (first_row == "nan").all():
                    df = df.iloc[1:].reset_index(drop=True)
                else:
                    break
            
            df.columns = [f"Column {i+1}" for i in range(len(df.columns))]
            
        # Atomic Cleanup: Trim all strings
        df = df.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
        
        # Validate mapping
        required = ['name', 'lat', 'lng']
        for req in required:
            if req not in mapping or mapping[req] not in df.columns:
                raise ValueError(f"Mapping for required field '{req}' is missing or invalid.")
        
        # Prepare transformation
        df_final = pd.DataFrame()
        
        # 1. Map Name
        df_final['name'] = df[mapping['name']].fillna('Unnamed Facility')
        
        # 2. Handle Coordinates (including potential split)
        if mapping['lat'] == mapping['lng']:
            # Combined column logic
            def split_coords(val):
                if pd.isna(val): return None, None
                nums = re.findall(r"[-+]?\d*\.\d+|\d+", str(val))
                if len(nums) >= 2:
                    return nums[0], nums[1]
                return None, None
            
            splits = df[mapping['lat']].apply(split_coords)
            df_final['lat'] = splits.apply(lambda x: x[0])
            df_final['lng'] = splits.apply(lambda x: x[1])
        else:
            df_final['lat'] = df[mapping['lat']]
            df_final['lng'] = df[mapping['lng']]
            
        # Clean coordinates (remove units like 'N/E', degree symbols, etc.)
        df_final['lat'] = df_final['lat'].apply(AugmentationService.clean_coordinate)
        df_final['lng'] = df_final['lng'].apply(AugmentationService.clean_coordinate)
        
        # Smart Swap: If Lat looks like Longitude and vice versa (India specific hint)
        # India Lat is ~8-37, Lng is ~68-97
        avg_lat = df_final['lat'].abs().mean()
        avg_lng = df_final['lng'].abs().mean()
        if avg_lat > 50 and avg_lng < 40:
             # Likely swapped
             df_final['lat'], df_final['lng'] = df_final['lng'], df_final['lat']
        
        # 3. Optional Columns with Normalization
        for standard_key in ['type', 'state', 'district']:
            if standard_key in mapping and mapping[standard_key] in df.columns:
                raw_col = mapping[standard_key]
                # Normalize categories to Title Case
                df_final[standard_key] = df[raw_col].fillna('').str.title().str.strip()
            else:
                df_final[standard_key] = None
                
        # Drop rows with invalid coordinates
        df_final = df_final.dropna(subset=['lat', 'lng'])
        
        # Save to processed data folder
        output_dir = input_path.parent.parent
        output_path = output_dir / output_name
        if not output_name.endswith('.csv'):
            output_path = output_path.with_suffix('.csv')
            
        df_final.to_csv(output_path, index=False)
        return output_path
