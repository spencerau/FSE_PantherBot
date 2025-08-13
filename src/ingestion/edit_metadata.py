from pypdf import PdfReader, PdfWriter
import re
import os
import pandas as pd
import json

def extract_year_and_subject(filename):
    year_match = re.search(r"(\d{4})", filename)
    year = year_match.group(1) if year_match else None
    subject_match = re.search(r"_([A-Za-z]+)\.pdf$", filename)
    subject = subject_match.group(1) if subject_match else None
    return year, subject

def edit_course_catalog(filename, year, programType, subject, out_pdf=None):
    reader = PdfReader(filename)
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({
        "/Year": f"{year}",
        "/ProgramType": f"{programType}",
        "/Subject": f"{subject}"
    })
    if out_pdf:
        with open(out_pdf, "wb") as f:
            writer.write(f)
    else:
        output_filename = f"{year}_{subject}.pdf"
        programType = programType.lower()
        os.makedirs(f"data/{programType}_catalogs", exist_ok=True)
        output_path = os.path.join(f"data/{programType}_catalogs", output_filename)
        with open(output_path, "wb") as f:
            writer.write(f)

def grab_course_catalog_metadata(filename):
    year, subject = extract_year_and_subject(filename)
    subject_mapping = {"CompSci": "Computer Science", "CompEng": "Computer Engineering", "Analytics": "Analytics"}
    full_subject = subject_mapping.get(subject, subject)
    program_type = "Minor" if "minor" in filename.lower() else "Major"
    
    return {
        "Year": year,
        "ProgramType": program_type,
        "Subject": full_subject
    }

def extract_metadata_from_json_filename(filename):
    year_match = re.search(r"(\d{4})", filename)
    year = year_match.group(1) if year_match else None
    
    subject_match = re.search(r"_([A-Za-z]+)\.json$", filename)
    subject = subject_match.group(1) if subject_match else None
    
    return year, subject

def add_metadata_to_json(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        filename = os.path.basename(json_path)
        year, subject = extract_metadata_from_json_filename(filename)
        
        subject_mapping = {
            "CompSci": "Computer Science", 
            "CompEng": "Computer Engineering", 
            "DataSci": "Data Science",
            "SoftEng": "Software Engineering",
            "ElecEng": "Electrical Engineering"
        }
        full_subject = subject_mapping.get(subject, subject)
        
        data["metadata"] = {
            "year": year,
            "subject": full_subject,
            "program_type": "Major",
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            
        return True
    except Exception as e:
        print(f"Error processing {json_path}: {e}")
        return False

def main():
    plan_base_dir = "data/4_year_plans/"
    subject_map = {
        "cs": "Computer Science",
        "ce": "Computer Engineering",
        "se": "Software Engineering",
        "ee": "Electrical Engineering",
        "ds": "Data Science"
    }
    
    if os.path.exists(plan_base_dir):
        for year_dir in os.listdir(plan_base_dir):
            year_path = os.path.join(plan_base_dir, year_dir)
            if os.path.isdir(year_path) and year_dir.isdigit():
                print(f"Processing 4-year plans for year: {year_dir}")
                os.makedirs(year_path, exist_ok=True)
                
                for filename in os.listdir(year_path):
                    if filename.endswith(".pdf"):
                        subject = None
                        for key, value in subject_map.items():
                            if key in filename:
                                subject = value
                                break
                        if not subject:
                            subject = "Unknown"
                        
                        input_path = os.path.join(year_path, filename)
                        reader = PdfReader(input_path)
                        writer = PdfWriter()
                        for page in reader.pages:
                            writer.add_page(page)
                        writer.add_metadata({
                            "/Subject": f"{subject}",
                            "/Year": f"{year_dir}"
                        })
                        
                        output_path = input_path
                        with open(output_path, "wb") as f:
                            writer.write(f)
                        print(f"Processed 4-year plan: {filename} -> {output_path}")

    # major course catalog metadata - process JSON files
    major_json_base_dir = "data/major_catalog_json/"
    if os.path.exists(major_json_base_dir):
        for year_dir in os.listdir(major_json_base_dir):
            year_path = os.path.join(major_json_base_dir, year_dir)
            if os.path.isdir(year_path) and year_dir.isdigit():
                print(f"Processing JSON major catalogs for year: {year_dir}")
                
                for filename in os.listdir(year_path):
                    if filename.endswith(".json"):
                        full_path = os.path.join(year_path, filename)
                        success = add_metadata_to_json(full_path)
                        if success:
                            print(f"Added metadata to {filename}")
                        else:
                            print(f"Failed to process {filename}")

    # minor course catalog metadata
    # minor_base_dir = "data/raw_minor_catalogs/"
    # if os.path.exists(minor_base_dir):
    #     for year_dir in os.listdir(minor_base_dir):
    #         year_path = os.path.join(minor_base_dir, year_dir)
    #         if os.path.isdir(year_path) and year_dir.isdigit():
    #             print(f"Processing minor catalogs for year: {year_dir}")
                
    #             for filename in os.listdir(year_path):
    #                 if filename.endswith(".pdf"):
    #                     full_path = os.path.join(year_path, filename)
    #                     metadata = grab_course_catalog_metadata(full_path)
                        
    #                     output_year_dir = os.path.join("data/minor_catalogs", year_dir)
    #                     os.makedirs(output_year_dir, exist_ok=True)
                        
    #                     edit_course_catalog(full_path,
    #                                         metadata["Year"],
    #                                         metadata["ProgramType"],
    #                                         metadata["Subject"],
    #                                         out_pdf=os.path.join(output_year_dir, filename))
    #                     print(f"Processed {filename} with metadata: {metadata}")

if __name__ == "__main__":
    main()
