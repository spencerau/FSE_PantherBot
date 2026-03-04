import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core_rag.ingestion.edit_metadata import MetadataExtractor
from utils.config_loader import load_config


class FSEMetadataExtractor(MetadataExtractor):
    
    def get_subject_mappings(self):
        config = load_config()
        programs = config.get('domain', {}).get('programs', {})
        minors = config.get('domain', {}).get('minors', {})
        
        mappings = {}
        
        for name, code in programs.items():
            clean_name = name.replace(' ', '')
            if clean_name not in mappings:
                mappings[clean_name] = (name, code)
        
        for name, code in minors.items():
            clean_name = name.replace(' ', '')
            if clean_name not in mappings:
                mappings[clean_name] = (name, code)
        
        return mappings
    
    def extract_metadata_from_path(self, file_path: str) -> dict:
        metadata = super().extract_metadata_from_path(file_path)
        
        path_lower = file_path.lower()
        if 'major_catalog' in path_lower:
            doc_type = 'major_catalog'
        elif 'minor_catalog' in path_lower:
            doc_type = 'minor_catalog'
        elif '4_year_plan' in path_lower or '4yearplan' in path_lower:
            doc_type = '4_year_plan'
        elif 'general_knowledge' in path_lower:
            doc_type = 'general_knowledge'
        else:
            doc_type = metadata.get('program_type', metadata.get('document_type', 'general'))
        
        fse_metadata = {
            'DocumentType': doc_type,
            'Year': metadata.get('year'),
            'Subject': metadata.get('subject'),
            'SubjectCode': metadata.get('subject_code')
        }
        
        return {k: v for k, v in fse_metadata.items() if v is not None}


MetadataExtractor = FSEMetadataExtractor
