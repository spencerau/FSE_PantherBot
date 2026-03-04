import os
import sys
import re
import uuid
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core_rag.ingestion import UnifiedIngestion
from core_rag.ingestion.content_extract import extract_content
from qdrant_client.models import PointStruct
from utils.config_loader import load_config
from ingestion.fse_edit_metadata import FSEMetadataExtractor


class FSEIngestion(UnifiedIngestion):
    """
    FSE-specific ingestion that extends core_rag's UnifiedIngestion.
    Adds section detection for academic catalog PDFs.
    """
    
    def __init__(self):
        super().__init__()
        self.metadata_extractor = FSEMetadataExtractor()
        self.config = load_config()
        self._load_section_patterns()
    
    def _load_section_patterns(self):
        """Load section patterns from config."""
        section_config = self.config.get('ingestion', {}).get('section_detection', {})
        self.section_detection_enabled = section_config.get('enabled', True)
        self.default_section = section_config.get('default_section', 'general')
        
        patterns = section_config.get('patterns', [])
        if patterns:
            self.section_patterns = [
                (re.compile(p['pattern'], re.IGNORECASE), p['section'])
                for p in patterns
            ]
        else:
            self.section_patterns = self._get_default_section_patterns()
    
    def _get_default_section_patterns(self) -> List[Tuple[re.Pattern, str]]:
        """Default section patterns for FSE academic catalogs."""
        return [
            (re.compile(r'grand challenges initiative', re.IGNORECASE), 'grand_challenges'),
            (re.compile(r'lower-division (?:core )?requirements', re.IGNORECASE), 'lower_division'),
            (re.compile(r'upper-division requirements', re.IGNORECASE), 'upper_division'),
            (re.compile(r'electives \(\d+ credits\)', re.IGNORECASE), 'electives'),
            (re.compile(r'professional portfolio', re.IGNORECASE), 'portfolio'),
            (re.compile(r'colloquium requirement', re.IGNORECASE), 'colloquium'),
            (re.compile(r'total credits', re.IGNORECASE), 'summary'),
        ]
    
    def _find_section_boundaries(self, text: str) -> List[Tuple[int, str]]:
        """
        Find all section boundaries in the document.
        Returns list of (position, section_name) tuples sorted by position.
        """
        boundaries = [(0, self.default_section)]
        
        for pattern, section_name in self.section_patterns:
            for match in pattern.finditer(text):
                boundaries.append((match.start(), section_name))
        
        boundaries.sort(key=lambda x: x[0])
        return boundaries
    
    def _get_section_for_position(self, position: int, boundaries: List[Tuple[int, str]]) -> str:
        """Get the section name for a given character position."""
        current_section = self.default_section
        for boundary_pos, section_name in boundaries:
            if boundary_pos <= position:
                current_section = section_name
            else:
                break
        return current_section
    
    def _find_chunk_position(self, chunk_text: str, full_text: str, start_from: int = 0) -> int:
        """Find the position of a chunk in the full text."""
        chunk_start = chunk_text[:100].strip()
        pos = full_text.find(chunk_start, start_from)
        if pos == -1:
            chunk_start = chunk_text[:50].strip()
            pos = full_text.find(chunk_start, start_from)
        return pos if pos != -1 else start_from
    
    def ingest_pdf_file(self, file_path: str) -> bool:
        """
        Ingest a PDF file with section detection.
        Extends parent method to add section metadata to chunks.
        """
        try:
            print(f"Ingesting PDF: {file_path}")
            
            text, tika_metadata = extract_content(file_path)
            if not text or len(text.strip()) < 10:
                print(f"  Warning: No content extracted from {file_path}")
                return False
            
            file_metadata = self._extract_metadata_from_path(file_path)
            combined_metadata = {**tika_metadata, **file_metadata}
            
            collection_name = self._get_collection_name_from_document_type(file_metadata['DocumentType'])
            
            section_boundaries = []
            if self.section_detection_enabled:
                section_boundaries = self._find_section_boundaries(text)
                print(f"  Found {len(section_boundaries)} section boundaries")
            
            chunk_data = self._chunk_text_with_metadata(text, combined_metadata)
            
            points = []
            last_position = 0
            
            for i, (chunk_text, chunk_metadata) in enumerate(chunk_data):
                embedding = self._get_embedding(chunk_text)
                if not embedding:
                    continue
                
                if self.section_detection_enabled and section_boundaries:
                    chunk_position = self._find_chunk_position(chunk_text, text, last_position)
                    section = self._get_section_for_position(chunk_position, section_boundaries)
                    chunk_metadata['section'] = section
                    last_position = chunk_position
                
                chunk_metadata['chunk_text'] = chunk_text
                chunk_metadata['total_chunks'] = len(chunk_data)
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload=chunk_metadata
                )
                points.append(point)
            
            if points:
                self.client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                
                if self.section_detection_enabled:
                    section_counts = {}
                    for p in points:
                        sec = p.payload.get('section', 'unknown')
                        section_counts[sec] = section_counts.get(sec, 0) + 1
                    print(f"  Ingested {len(points)} chunks into '{collection_name}'")
                    print(f"  Section distribution: {section_counts}")
                else:
                    print(f"  Ingested {len(points)} chunks into '{collection_name}'")
                return True
            else:
                print(f"  No valid chunks created for {file_path}")
                return False
                
        except Exception as e:
            print(f"Error ingesting PDF {file_path}: {e}")
            import traceback
            traceback.print_exc()
            return False


UnifiedIngestion = FSEIngestion
