"""
Document Intelligence Service - Extract tables from PDFs using Azure AI
"""
import os
from typing import List, Dict, Any, Optional
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, DocumentAnalysisFeature
from azure.core.credentials import AzureKeyCredential


class DocumentIntelligenceService:
    """Service for extracting tables from PDF documents using Azure Document Intelligence."""
    
    def __init__(self):
        self.endpoint = os.getenv("AZURE_DOC_INTEL_ENDPOINT")
        self.key = os.getenv("AZURE_DOC_INTEL_KEY")
        self._client: Optional[DocumentIntelligenceClient] = None
    
    @property
    def is_configured(self) -> bool:
        """Check if Azure credentials are configured."""
        return bool(self.endpoint and self.key)
    
    @property
    def client(self) -> DocumentIntelligenceClient:
        """Lazily create the Document Intelligence client."""
        if not self._client:
            if not self.is_configured:
                raise ValueError("Azure Document Intelligence is not configured. Set AZURE_DOC_INTEL_ENDPOINT and AZURE_DOC_INTEL_KEY.")
            self._client = DocumentIntelligenceClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key)
            )
        return self._client
    
    def extract_tables_from_pdf(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """
        Extract tables from a PDF document.
        
        Args:
            pdf_bytes: Raw PDF file bytes
            
        Returns:
            Dictionary with extracted tables and metadata
        """
        # Analyze the document using the prebuilt-layout model
        poller = self.client.begin_analyze_document(
            "prebuilt-layout",
            analyze_request=pdf_bytes,
            content_type="application/pdf"
        )
        result = poller.result()
        
        tables = []
        
        for table in result.tables or []:
            # Extract table structure
            extracted_table = {
                "row_count": table.row_count,
                "column_count": table.column_count,
                "cells": []
            }
            
            # Track headers (first row)
            headers = {}
            rows_data = {}
            
            for cell in table.cells or []:
                row_idx = cell.row_index
                col_idx = cell.column_index
                content = cell.content.strip() if cell.content else ""
                
                if row_idx == 0:
                    # Header row
                    headers[col_idx] = content
                else:
                    # Data row
                    if row_idx not in rows_data:
                        rows_data[row_idx] = {}
                    rows_data[row_idx][col_idx] = content
            
            # Convert to list of row dictionaries
            rows = []
            for row_idx in sorted(rows_data.keys()):
                row = {}
                for col_idx, value in rows_data[row_idx].items():
                    header = headers.get(col_idx, f"column_{col_idx}")
                    row[header] = value
                rows.append(row)
            
            extracted_table["headers"] = list(headers.values())
            extracted_table["rows"] = rows
            tables.append(extracted_table)
        
        return {
            "page_count": len(result.pages) if result.pages else 0,
            "table_count": len(tables),
            "tables": tables
        }
    
    def map_to_population_schema(self, table: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Attempt to map extracted table columns to population schema.
        
        Expected output schema:
        - state: str
        - district: str  
        - population: int
        
        Uses fuzzy matching on column headers.
        """
        headers = [h.lower() for h in table.get("headers", [])]
        rows = table.get("rows", [])
        
        # Column mapping heuristics
        state_cols = ["state", "state name", "state_name", "statename"]
        district_cols = ["district", "district name", "district_name", "districtname", "block", "ward"]
        population_cols = ["population", "pop", "total population", "total_population", "pop_total", "population_total", "2021", "2011"]
        
        def find_col(options: List[str]) -> Optional[str]:
            for opt in options:
                for header in headers:
                    if opt in header:
                        # Return the original case header
                        return table["headers"][headers.index(header)]
            return None
        
        state_col = find_col(state_cols)
        district_col = find_col(district_cols)
        pop_col = find_col(population_cols)
        
        mapped_data = []
        for row in rows:
            entry = {}
            if state_col and state_col in row:
                entry["state"] = row[state_col]
            if district_col and district_col in row:
                entry["district"] = row[district_col]
            if pop_col and pop_col in row:
                try:
                    # Clean and parse population (remove commas, etc.)
                    pop_str = row[pop_col].replace(",", "").replace(" ", "")
                    entry["population"] = int(float(pop_str))
                except (ValueError, TypeError):
                    entry["population"] = None
            
            if entry:  # Only add if we extracted something
                mapped_data.append(entry)
        
        return mapped_data


# Singleton instance
document_service = DocumentIntelligenceService()
