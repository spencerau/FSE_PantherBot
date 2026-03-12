import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core_rag.ingestion.edit_metadata import MetadataExtractor

# Convention: YYYY_<code>[_plan].<ext>  e.g. 2023_cs_plan.md, 2022_anal.pdf
_FILENAME_RE = re.compile(r'^(\d{4})_([A-Za-z]+?)(?:_plan)?\.\w+$', re.IGNORECASE)

_DOC_TYPE_MAP = {
    'major_catalog':      'major_catalog',
    'major_catalog_json': 'major_catalog',
    'minor_catalog':      'minor_catalog',
    '4_year_plan':        '4_year_plan',
    '4_year_plans':       '4_year_plan',
    'general_knowledge':  'general_knowledge',
}


class FSEMetadataExtractor(MetadataExtractor):

    def extract_metadata_from_path(self, file_path: str) -> dict:
        path = Path(file_path)

        doc_type = 'general_knowledge'
        for part in [p.lower() for p in path.parts]:
            if part in _DOC_TYPE_MAP:
                doc_type = _DOC_TYPE_MAP[part]
                break

        metadata = {'DocumentType': doc_type}
        m = _FILENAME_RE.match(path.name)
        if m:
            metadata['Year'] = m.group(1)
            metadata['SubjectCode'] = m.group(2).lower()

        return metadata


MetadataExtractor = FSEMetadataExtractor
