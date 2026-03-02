import pandas as pd
import argparse
import logging
import os
import sys
import time
from typing import List, Dict, Any, Optional
from pathlib import Path

from execution.utils.logging_config import setup_logging
from execution.utils.validators import validate_file_exists, ValidationError

logger = setup_logging()

class CSVProcessor:
    def __init__(self, input_path: str, output_path: str, chunk_size: Optional[int] = None):
        try:
            validate_file_exists(input_path)
            self.input_path = input_path
            self.output_path = output_path
            self.chunk_size = chunk_size
            self.df: Optional[pd.DataFrame] = None
        except ValidationError as ve:
            logger.error(f"Validation failed for CSV input: {ve}")
            raise

    def load_data(self) -> None:
        """Loads CSV data using pandas."""
        logger.info(f"Loading CSV file: {self.input_path}", extra={"action": "load"})
        try:
            if self.chunk_size:
                chunks = pd.read_csv(self.input_path, chunksize=self.chunk_size)
                self.df = pd.concat(chunks, ignore_index=True)
            else:
                self.df = pd.read_csv(self.input_path)
            logger.info(f"Loaded {len(self.df)} rows successfully.")
        except Exception as e:
            logger.error(f"Failed to read CSV {self.input_path}: {e}")
            raise

    def process(self, operations: List[str], kwargs: Optional[Dict[str, Any]] = None) -> None:
        """Applies a list of processing operations sequentially."""
        if self.df is None:
            self.load_data()
        
        initial_count = len(self.df)
        logger.info(f"Applying operations: {operations}")

        for op in operations:
            op = op.strip().lower()
            try:
                if op == 'clean':
                    self._clean()
                elif op == 'deduplicate':
                    self._deduplicate()
                elif op == 'trim_strings':
                    self._trim_strings()
                elif op.startswith('drop_'):
                    col = op.split('drop_')[1]
                    self._drop_column(col)
                elif op == 'fill_na':
                    val = kwargs.get('fill_value', '') if kwargs else ''
                    self._fill_na(val)
                else:
                    logger.warning(f"Unknown operation skipped: {op}")
            except Exception as e:
                logger.error(f"Operation '{op}' failed: {e}")
                raise

        final_count = len(self.df)
        logger.info("Processing complete", extra={
            "initial_rows": initial_count,
            "final_rows": final_count,
            "removed_rows": initial_count - final_count,
            "operations_applied": operations
        })

    def _clean(self):
        """Removes completely empty rows and columns."""
        original_rows = len(self.df)
        self.df.dropna(how='all', inplace=True)
        self.df.dropna(axis=1, how='all', inplace=True)
        logger.debug(f"Clean removed {original_rows - len(self.df)} empty rows.")

    def _deduplicate(self):
        """Removes exact duplicate rows."""
        original_rows = len(self.df)
        self.df.drop_duplicates(inplace=True)
        logger.debug(f"Deduplicate removed {original_rows - len(self.df)} duplicate rows.")

    def _trim_strings(self):
        """Trims whitespace from string columns."""
        str_cols = self.df.select_dtypes(include=['object']).columns
        for col in str_cols:
            self.df[col] = self.df[col].str.strip()
        logger.debug("Trimmed whitespace across string columns.")

    def _drop_column(self, col: str):
        if col in self.df.columns:
            self.df.drop(columns=[col], inplace=True)
            logger.debug(f"Dropped column: {col}")
        else:
            logger.warning(f"Drop failed - column not found: {col}")

    def _fill_na(self, value: Any):
        self.df.fillna(value, inplace=True)
        logger.debug(f"Filled missing values with '{value}'")

    def save(self) -> None:
        """Saves the processed DataFrame safely to output path."""
        if self.df is None:
            raise ValueError("No data to save. Processor runs may have failed.")
            
        try:
            dir_name = os.path.dirname(self.output_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
                
            temp_path = f"{self.output_path}.tmp"
            self.df.to_csv(temp_path, index=False)
            os.replace(temp_path, self.output_path)
            logger.info(f"Successfully saved to {self.output_path}", extra={"action": "save"})
        except Exception as e:
            logger.error(f"Failed to save CSV to {self.output_path}: {e}")
            raise

def main():
    parser = argparse.ArgumentParser(description="Production CSV Data Processor")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--output", required=True, help="Output CSV path")
    parser.add_argument("--operations", default="clean,deduplicate,trim_strings", 
                        help="Comma-separated operations (e.g., clean,deduplicate,drop_id,fill_na)")
    parser.add_argument("--chunk-size", type=int, default=100000, help="Rows per chunk for large files (default: 100k)")
    
    try:
        args = parser.parse_args()
    except argparse.ArgumentError as e:
        logger.critical(f"Argument error: {e}")
        sys.exit(1)
        
    operations_list = [op.strip() for op in args.operations.split(',')]
    start_time = time.time()
    
    try:
        processor = CSVProcessor(args.input, args.output, chunk_size=args.chunk_size)
        processor.process(operations_list)
        processor.save()
        execution_time = time.time() - start_time
        logger.info(f"Total processing time: {round(execution_time, 2)}s")
    except Exception as e:
        logger.error(f"CSV Processor workflow failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
