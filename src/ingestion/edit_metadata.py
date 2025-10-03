from pypdf import PdfReader, PdfWriter
import re
import os
import json
from pathlib import Path
from datetime import datetime

SUBJECT_MAPPINGS = {
    'CompSci': ('Computer Science', 'cs'),
    'CompEng': ('Computer Engineering', 'ce'),
    'SoftEng': ('Software Engineering', 'se'), 
    'ElecEng': ('Electrical Engineering', 'ee'),
    'DataSci': ('Data Science', 'ds'),
    'Analytics': ('Analytics', 'anal'),
    'ISP': ('Information Security Policy', 'isp'),
    'GameDev': ('Game Development', 'gamedev')
}

def extract_metadata_from_path(file_path: str) -> dict:
    path = Path(file_path)
    
    year = None
    for part in path.parts:
        if part.isdigit() and len(part) == 4 and part.startswith('20'):
            year = part
            break
    
    path_str = str(path).lower()
    if 'minor_catalog' in path_str:
        program_type, collection_type, doc_type = 'Minor', 'minor_catalogs', 'minor_catalog'
    elif 'major_catalog' in path_str:
        program_type, collection_type, doc_type = 'Major', 'major_catalogs', 'major_catalog'
    elif '4_year_plan' in path_str:
        program_type, collection_type, doc_type = '4_Year_Plan', '4_year_plans', '4_year_plan'
    else:
        program_type, collection_type, doc_type = 'General', 'general_knowledge', 'general_knowledge'
    
    subject, subject_code = None, None
    if path.suffix.lower() in ['.pdf', '.json']:
        match = re.search(r'(\d{4})_(.+)\.(pdf|json)', path.name)
        if match:
            year = match.group(1) or year
            subject_part = match.group(2)
            
            for pattern, (full_name, code) in SUBJECT_MAPPINGS.items():
                if pattern in subject_part:
                    subject, subject_code = full_name, code
                    break
            else:
                subject = subject_part.replace('_', ' ')
                subject_code = subject_part.lower()
    
    metadata = {
        'Year': year,
        'DocumentType': program_type,
        'Subject': subject,
        'SubjectCode': subject_code
    }
    
    return metadata

def add_pdf_metadata(pdf_path: str, metadata: dict) -> None:
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    pdf_metadata = {
        "/Year": str(metadata.get('Year', '')),
        "/DocumentType": str(metadata.get('DocumentType', '')),
        "/Subject": str(metadata.get('Subject', '')),
        "/SubjectCode": str(metadata.get('SubjectCode', ''))
    }
    writer.add_metadata(pdf_metadata)
    
    with open(pdf_path, "wb") as f:
        writer.write(f)

def add_json_metadata(json_path: str, metadata: dict) -> bool:
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        data["metadata"] = {
            "Year": metadata.get('Year'),
            "DocumentType": metadata.get('DocumentType'),
            "Subject": metadata.get('Subject'),
            "SubjectCode": metadata.get('SubjectCode')
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error processing {json_path}: {e}")
        return False

def process_files_in_directory(base_dir: str, file_extension: str) -> None:
    if not os.path.exists(base_dir):
        return
    
    for year_dir in os.listdir(base_dir):
        year_path = os.path.join(base_dir, year_dir)
        if not (os.path.isdir(year_path) and year_dir.isdigit()):
            continue
            
        print(f"Processing {file_extension} files in {base_dir} for year: {year_dir}")
        
        for filename in os.listdir(year_path):
            if not filename.endswith(file_extension):
                continue
            if filename.startswith("backup_"):
                continue
                
            full_path = os.path.join(year_path, filename)
            metadata = extract_metadata_from_path(full_path)
            
            try:
                if file_extension == ".pdf":
                    add_pdf_metadata(full_path, metadata)
                elif file_extension == ".json":
                    add_json_metadata(full_path, metadata)
                
                print(f"Processed {filename}")
                print(f"  Year: {metadata.get('Year', 'None')}")
                print(f"  DocumentType: {metadata.get('DocumentType', 'None')}")
                print(f"  Subject: {metadata.get('Subject', 'None')}")
                print(f"  SubjectCode: {metadata.get('SubjectCode', 'None')}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")

def main():
    print("Adding metadata to catalog files...")
    
    process_files_in_directory("data/4_year_plans/", ".pdf")
    process_files_in_directory("data/major_catalog_json/", ".json") 
    process_files_in_directory("data/minor_catalog/", ".pdf")
    
    print("Metadata processing complete!")

if __name__ == "__main__":
    main()
