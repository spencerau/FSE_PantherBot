import os
import re
import json
from pathlib import Path
from typing import Dict, List
import sys
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from datetime import datetime
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.config_loader import load_config
from utils.ollama_api import get_ollama_api
from utils.text_preprocessing import preprocess_for_embedding
from ingestion.content_extract import extract_content
from ingestion.chunking import AdvancedChunker


class UnifiedIngestion:
    def __init__(self):
        self.config = load_config()
        self.client = QdrantClient(
            host=self.config['qdrant']['host'],
            port=self.config['qdrant']['port'],
            timeout=self.config['qdrant']['timeout']
        )
        self.embedding_model = self.config['embedding']['model']
        self.chunker = AdvancedChunker(self.config.get('chunker', {}))
        self.ollama_api = get_ollama_api()
        
        self._ensure_collections_exist()
    
    def _ensure_collections_exist(self):
        collections = self.config['qdrant']['collections']
        
        for collection_name in collections.values():
            try:
                self.client.get_collection(collection_name)
                print(f"Collection '{collection_name}' already exists")
            except Exception:
                test_embedding = self._get_embedding("test")
                if test_embedding is None or len(test_embedding) == 0:
                    # Fallback: determine vector size based on embedding model
                    if 'bge-m3' in self.embedding_model:
                        vector_size = 1024
                    elif 'nomic-embed' in self.embedding_model:
                        vector_size = 768
                    else:
                        vector_size = 768
                    print(f"Could not get test embedding, using fallback vector size {vector_size} for model {self.embedding_model}")
                else:
                    vector_size = len(test_embedding)
                
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=VectorParams(
                        size=vector_size,
                        distance=Distance.COSINE
                    )
                )
                print(f"Created collection '{collection_name}' with vector size {vector_size}")

    def _get_embedding(self, text: str, task_type: str = 'document') -> List[float]:
        try:
            processed_text = preprocess_for_embedding([text], task_type, self.config.get('embedding', {}))[0]
            embedding = self.ollama_api.get_embeddings(
                model=self.embedding_model,
                prompt=processed_text
            )
            return embedding if embedding is not None else []
        except Exception as e:
            print(f"Error getting embedding: {e}")
            return []
    
    def _get_embeddings_batch(self, texts: List[str], task_type: str = 'document') -> List[List[float]]:
        try:
            processed_texts = preprocess_for_embedding(texts, task_type, self.config.get('embedding', {}))
            embeddings = []
            batch_size = self.config.get('embedding', {}).get('batch_size', 32)
            
            for i in range(0, len(processed_texts), batch_size):
                batch = processed_texts[i:i + batch_size]
                for text in batch:
                    embedding = self.ollama_api.get_embeddings(
                        model=self.embedding_model,
                        prompt=text
                    )
                    embeddings.append(embedding)
            
            return embeddings
        except Exception as e:
            print(f"Error getting batch embeddings: {e}")
            return []
    
    def _chunk_text_with_metadata(self, text: str, base_metadata: Dict) -> List[tuple]:
        return self.chunker.chunk_text(text, base_metadata)
    
    def _extract_json_content_for_embedding(self, json_data, section_path: str = "") -> List[Dict]:
        """
        Extract meaningful text content from JSON for embedding.
        Returns list of content dictionaries with text and metadata.
        Handles both array format (like important_links.json) and catalog format.
        """
        content_items = []
        
        if isinstance(json_data, list):
            content_items = self._extract_json_array_content(json_data)
        
        elif isinstance(json_data, dict):
            if 'program' in json_data and 'sections' in json_data:
                content_items = self._extract_catalog_json_content(json_data)
            
            else:
                content_items = self._extract_dict_json_content(json_data)
        
        return content_items
    
    def _extract_json_array_content(self, json_array: List) -> List[Dict]:
        """Handle JSON arrays like important_links.json"""
        content_items = []
        
        for item in json_array:
            if isinstance(item, dict):
                if 'title' in item and 'url' in item:
                    text_content = f"Title: {item.get('title', '')}\n"
                    text_content += f"URL: {item.get('url', '')}\n"
                    text_content += f"Category: {item.get('category', '')}\n"
                    text_content += f"Description: {item.get('description', '')}\n"
                    
                    content_items.append({
                        'text': text_content.strip(),
                        'section_type': 'resource_link',
                        'section_name': item.get('category', 'General Resource'),
                        'section_classification': 'Resource Links'
                    })
                
                else:
                    text_parts = []
                    for key, value in item.items():
                        if isinstance(value, (str, int, float, bool)):
                            text_parts.append(f"{key.title()}: {value}")
                    
                    if text_parts:
                        content_items.append({
                            'text': '\n'.join(text_parts),
                            'section_type': 'structured_data',
                            'section_name': 'Data Entry',
                            'section_classification': 'Structured Information'
                        })
        
        return content_items
    
    def _extract_dict_json_content(self, json_dict: Dict) -> List[Dict]:
        """Handle general dictionary JSON structures"""
        content_items = []
        
        text_parts = []
        for key, value in json_dict.items():
            if isinstance(value, (str, int, float, bool)):
                text_parts.append(f"{key.title()}: {value}")
            elif isinstance(value, list) and value and isinstance(value[0], str):
                text_parts.append(f"{key.title()}: {', '.join(value)}")
        
        if text_parts:
            content_items.append({
                'text': '\n'.join(text_parts),
                'section_type': 'general_info',
                'section_name': 'General Information',
                'section_classification': 'Information'
            })
        
        return content_items
    
    def _extract_catalog_json_content(self, json_data: Dict) -> List[Dict]:
        """Handle academic catalog JSON structure (original logic)"""
        content_items = []
        
        program_text = f"Program: {json_data.get('program', '')}\n"
        program_text += f"Institution: {json_data.get('institution', '')}\n"
        program_text += f"Academic Year: {json_data.get('academic_year', '')}\n"
        
        if 'requirements' in json_data:
            req = json_data['requirements']
            program_text += f"\nAcademic Requirements:\n"
            if 'GPA' in req:
                program_text += f"• Lower Division GPA Requirement: {req['GPA'].get('lower_division', 'N/A')}\n"
                program_text += f"• Major GPA Requirement: {req['GPA'].get('major', 'N/A')}\n"
            if 'grade_requirement' in req:
                program_text += f"• Minimum Grade Requirement: {req['grade_requirement']}\n"
            if 'upper_division_units' in req:
                program_text += f"• Upper Division Unit Requirement: {req['upper_division_units']} units\n"
        
        if 'total_credits' in json_data:
            program_text += f"\nTotal Program Credits: {json_data['total_credits']}\n"
        
        content_items.append({
            'text': program_text.strip(),
            'section_type': 'program_overview',
            'section_name': 'Program Information'
        })
        
        for section in json_data.get('sections', []):
            section_content = self._process_catalog_section(section)
            content_items.extend(section_content)
        
        if 'sections' in json_data:
            summary_text = f"Program Structure Summary for {json_data.get('program', 'Unknown Program')}:\n\n"
            summary_text += "This program consists of the following requirement categories:\n"
            
            for section in json_data['sections']:
                section_name = section.get('name', 'Unknown Section')
                section_credits = section.get('credits', 'N/A')
                classification = self._classify_section(section_name)
                summary_text += f"• {classification}: {section_name} ({section_credits} credits)\n"
            
            if 'total_credits' in json_data:
                summary_text += f"\nTotal Program Credits: {json_data['total_credits']}"
            
            content_items.append({
                'text': summary_text.strip(),
                'section_type': 'program_structure',
                'section_name': 'Program Structure Summary'
            })
        
        return content_items
    
    def _process_catalog_section(self, section: Dict) -> List[Dict]:
        content_items = []
        
        section_name = section.get('name', 'Unknown Section')
        section_credits = section.get('credits', 'N/A')
        section_classification = self._classify_section(section_name)
        
        section_text = f"Section: {section_name}\n"
        section_text += f"Classification: {section_classification}\n"
        section_text += f"Credits: {section_credits}\n"
        
        if 'notes' in section:
            section_text += f"Notes: {section['notes']}\n"
        
        if section.get('courses'):
            section_text += f"\n{section_classification} Courses:\n"
            for course in section['courses']:
                course_text = f"• {course.get('course_number', '')}: {course.get('name', '')}\n"
                if course.get('prerequisite'):
                    course_text += f"  Prerequisite: {course['prerequisite']}\n"
                if course.get('description'):
                    course_text += f"  Description: {course['description']}\n"
                section_text += course_text
        
        if 'math_sequences' in section:
            section_text += f"\nMathematics Sequence Options:\n"
            for i, seq in enumerate(section['math_sequences'], 1):
                seq_text = f"Math Sequence Option {i}:\n"
                for course in seq.get('courses', []):
                    seq_text += f"  • {course.get('course_number', '')}: {course.get('name', '')}\n"
                    if course.get('description'):
                        seq_text += f"    {course['description']}\n"
                section_text += seq_text + "\n"
        
        if 'approved_sequences' in section:
            section_text += f"\nApproved Course Sequences:\n"
            for i, seq in enumerate(section['approved_sequences'], 1):
                seq_text = f"Approved Sequence {i}:\n"
                for course in seq.get('courses', []):
                    seq_text += f"  • {course.get('course_number', '')}: {course.get('name', '')}\n"
                    if course.get('description'):
                        seq_text += f"    {course['description']}\n"
                section_text += seq_text + "\n"
        
        content_items.append({
            'text': section_text.strip(),
            'section_type': 'section',
            'section_name': section_name,
            'section_classification': section_classification
        })
        
        return content_items
    
    def _classify_section(self, section_name: str) -> str:
        """
        Classify a section based on its actual name from the JSON.
        """
        return section_name
    
    def _extract_metadata_from_path(self, file_path: str) -> Dict:
        path = Path(file_path)
        metadata = {
            'file_name': path.name,
            'file_path': str(path),
            'file_extension': path.suffix,
            'ingested_at': datetime.now().isoformat()
        }
        
        path_parts = path.parts
        year_from_path = None
        for part in path_parts:
            if part.isdigit() and len(part) == 4 and part.startswith('20'):
                year_from_path = part
                break
        
        if path.suffix.lower() == '.json':
            json_match = re.search(r'(\d{4})_(.+)\.json', path.name)
            if json_match:
                metadata['year'] = json_match.group(1)
                subject_part = json_match.group(2)
                
                program_mappings = {
                    'CompSci': ('cs', 'Computer Science'),
                    'Computer Science': ('cs', 'Computer Science'),
                    'CompEng': ('ce', 'Computer Engineering'),
                    'Computer Engineering': ('ce', 'Computer Engineering'),
                    'SoftEng': ('se', 'Software Engineering'),
                    'Software Engineering': ('se', 'Software Engineering'),
                    'ElecEng': ('ee', 'Electrical Engineering'),
                    'Electrical Engineering': ('ee', 'Electrical Engineering'),
                    'DataSci': ('ds', 'Data Science'),
                    'Analytics': ('ds', 'Data Science'),
                    'Data Science': ('ds', 'Data Science')
                }
                
                program_code, program_full = None, None
                for pattern, (code, full_name) in program_mappings.items():
                    if pattern.lower() in subject_part.lower():
                        program_code = code
                        program_full = full_name
                        break
                
                if program_code and program_full:
                    metadata['program'] = program_code
                    metadata['program_full'] = program_full
                    metadata['subject'] = program_full
                else:
                    metadata['subject'] = subject_part.replace('_', ' ')
                    
            elif year_from_path:
                metadata['year'] = year_from_path
        else:
            match = re.search(r'(\d{4})_(.+)\.pdf', path.name)
            plan_match = re.search(r'^([a-z]{2})_(\d{4})_', path.name)
            
            if plan_match:
                program_code = plan_match.group(1)
                metadata['year'] = plan_match.group(2) or year_from_path
                metadata['program'] = program_code
                
                code_to_full_name = {
                    'cs': 'Computer Science',
                    'ce': 'Computer Engineering', 
                    'se': 'Software Engineering',
                    'ee': 'Electrical Engineering',
                    'ds': 'Data Science'
                }
                
                metadata['program_full'] = code_to_full_name.get(program_code, program_code)
                metadata['subject'] = metadata['program_full']
            elif match:
                metadata['year'] = match.group(1) or year_from_path
                subject_part = match.group(2)
                metadata['subject'] = subject_part.replace('_', ' ')
                
                program_mappings = {
                    'Computer Science': 'cs',
                    'Computer Engineering': 'ce',
                    'Software Engineering': 'se',
                    'Electrical Engineering': 'ee',
                    'Data Science': 'ds'
                }
                
                for full_name, code in program_mappings.items():
                    if full_name in metadata['subject']:
                        metadata['program'] = code
                        metadata['program_full'] = full_name
                        break
            elif year_from_path:
                metadata['year'] = year_from_path
        
        if 'major_catalog_json' in str(path).lower():
            metadata['collection_type'] = 'major_catalogs'
            metadata['document_type'] = 'major'
            metadata['doc_type'] = 'major_catalog'
        # elif 'minor_catalog_json' in str(path).lower() or ('minor_catalogs' in str(path).lower() and path.suffix.lower() != '.pdf'):
        #     metadata['collection_type'] = 'minor_catalogs'
        #     metadata['document_type'] = 'minor'
        #     metadata['doc_type'] = 'minor_catalog'
        elif 'course_catalogs' in str(path) or 'course_listings' in str(path):
            metadata['collection_type'] = 'course_listings'
            metadata['document_type'] = 'course'
            metadata['doc_type'] = 'course_catalog'
        elif 'general_knowledge' in str(path).lower():
            metadata['collection_type'] = 'general_knowledge'
            metadata['document_type'] = 'general'
            metadata['doc_type'] = 'general_knowledge'
        elif '4_year_plans' in str(path).lower():
            metadata['collection_type'] = '4_year_plans'
            metadata['document_type'] = '4_year_plan'
            metadata['doc_type'] = '4_year_plan'
        else:
            metadata['collection_type'] = 'general_knowledge'
            metadata['document_type'] = 'general'
            metadata['doc_type'] = 'general_knowledge'
        
        return metadata
    
    def ingest_json_file(self, file_path: str) -> bool:
        """Ingest a JSON file containing structured catalog data."""
        try:
            print(f"Ingesting JSON: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            file_metadata = self._extract_metadata_from_path(file_path)
            
            content_items = self._extract_json_content_for_embedding(json_data)
            
            if not content_items:
                print(f"  Warning: No content extracted from {file_path}")
                return False
            
            collection_name = self.config['qdrant']['collections'][file_metadata['collection_type']]
            
            points = []
            for item in content_items:
                combined_metadata = {
                    **file_metadata,
                    'section_type': item.get('section_type', 'unknown'),
                    'section_name': item.get('section_name', 'Unknown Section'),
                    'section_classification': item.get('section_classification', 'Program Requirements'),
                    'content_type': 'structured_json'
                }
                
                chunk_text = item['text']
                embedding = self._get_embedding(chunk_text)
                if embedding is None:
                    continue
                
                combined_metadata['chunk_text'] = chunk_text
                combined_metadata['total_chunks'] = 1
                
                point = PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload=combined_metadata
                )
                points.append(point)
            
            if points:
                self.client.upsert(
                    collection_name=collection_name,
                    points=points
                )
                print(f"Ingested {len(points)} chunks from {len(content_items)} sections into collection '{collection_name}'")
                return True
            else:
                print(f"No valid chunks created for {file_path}")
                return False
                
        except Exception as e:
            print(f"Error ingesting JSON {file_path}: {e}")
            return False
    
    def ingest_file(self, file_path: str) -> bool:
        file_extension = Path(file_path).suffix.lower()
        
        if file_extension == '.json':
            return self.ingest_json_file(file_path)
        elif file_extension == '.pdf':
            return self.ingest_pdf_file(file_path)
        else:
            print(f"Unsupported file type: {file_extension}")
            return False
    
    def ingest_pdf_file(self, file_path: str) -> bool:
        try:
            print(f"Ingesting PDF: {file_path}")
            
            text, tika_metadata = extract_content(file_path)
            if not text or len(text.strip()) < 10:
                print(f"  Warning: No content extracted from {file_path}")
                return False
            
            file_metadata = self._extract_metadata_from_path(file_path)
            combined_metadata = {**tika_metadata, **file_metadata}
            
            collection_name = self.config['qdrant']['collections'][combined_metadata['collection_type']]
            
            chunk_data = self._chunk_text_with_metadata(text, combined_metadata)
            
            points = []
            for i, (chunk_text, chunk_metadata) in enumerate(chunk_data):
                embedding = self._get_embedding(chunk_text)
                if embedding is None:
                    continue
                
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
                print(f"Ingested {len(points)} chunks into collection '{collection_name}'")
                return True
            else:
                print(f"No valid chunks created for {file_path}")
                return False
                
        except Exception as e:
            print(f"Error ingesting PDF {file_path}: {e}")
            return False
    
    def ingest_directory(self, directory: str, file_extensions: List[str] = None) -> Dict:
        if file_extensions is None:
            file_extensions = ['.pdf', '.json']
        
        stats = {
            'total_files': 0,
            'success_files': 0,
            'failed_files': 0,
            'collections_used': set()
        }
        
        directory = Path(directory)
        if not directory.exists():
            print(f"Directory not found: {directory}")
            return stats
        
        for file_path in directory.rglob('*'):
            if file_path.is_file() and file_path.suffix.lower() in file_extensions:
                if 'readme' in file_path.name.lower():
                    continue
                    
                stats['total_files'] += 1
                
                if self.ingest_file(str(file_path)):
                    stats['success_files'] += 1
                else:
                    stats['failed_files'] += 1
        
        return stats
    
    def bulk_ingest(self, data_directories: List[str]) -> Dict:
        total_stats = {
            'total_files': 0,
            'success_files': 0,
            'failed_files': 0,
            'collections_used': set()
        }
        
        for directory in data_directories:
            print(f"\n=== Ingesting from {directory} ===")
            stats = self.ingest_directory(directory)
            
            total_stats['total_files'] += stats['total_files']
            total_stats['success_files'] += stats['success_files']
            total_stats['failed_files'] += stats['failed_files']
            total_stats['collections_used'].update(stats['collections_used'])
            
            print(f"Directory stats: {stats['success_files']}/{stats['total_files']} files successful")
        
        return total_stats
    
    def print_collection_summary(self):
        print("\n=== Collection Summary ===")
        collections = self.config['qdrant']['collections']
        
        for collection_name in collections.values():
            try:
                info = self.client.get_collection(collection_name)
                print(f"{collection_name}: {info.points_count} documents")
            except Exception as e:
                print(f"{collection_name}: Error - {e}")
    
    def clear_collections(self):
        collections = self.config['qdrant']['collections']
        
        for collection_name in collections.values():
            try:
                self.client.delete_collection(collection_name)
                print(f"Deleted collection '{collection_name}'")
            except Exception as e:
                print(f"Error deleting collection '{collection_name}': {e}")
        
        self._ensure_collections_exist()


def main():
    print("Starting unified RAG ingestion...")
    
    ingestion = UnifiedIngestion()
    config = load_config()
    data_dirs = []
    
    if os.path.exists("data/major_catalog_json"):
        data_dirs.append("data/major_catalog_json")
        print("Added major_catalog_json directory")
    
    # if os.path.exists("data/minor_catalog_json"):
    #     data_dirs.append("data/minor_catalog_json")
    #     print("Added minor_catalog_json directory")
    
    if os.path.exists(config['data']['general_knowledge_path']):
        data_dirs.append(config['data']['general_knowledge_path'])
        print("Added general knowledge directory")
    
    if '4_year_plans' in config['data'] and os.path.exists(config['data']['4_year_plans']):
        data_dirs.append(config['data']['4_year_plans'])
        print("Added 4_year_plans directory")
    
    if not data_dirs:
        print("No data directories found to process!")
        return
    
    stats = ingestion.bulk_ingest(data_dirs)
    
    print(f"\n=== Final Results ===")
    print(f"Total files processed: {stats['total_files']}")
    print(f"Successfully ingested: {stats['success_files']}")
    print(f"Failed: {stats['failed_files']}")
    print(f"Collections used: {stats['collections_used']}")
    ingestion.print_collection_summary()


if __name__ == "__main__":
    main()
