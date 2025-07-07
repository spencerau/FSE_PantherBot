from pypdf import PdfReader, PdfWriter
import re
import os
import pandas as pd

# 2022 Fowler Catalog Site
# https://catalog.chapman.edu/content.php?catoid=42&navoid=2235

# 2023 Fowler Catalog Site
# https://catalog.chapman.edu/content.php?catoid=45&navoid=2393

# 2024 Fowler Catalog Site
# https://catalog.chapman.edu/content.php?catoid=46&navoid=2429


def extract_year_and_subject(filename):
    year_match = re.search(r"(\d{4})", filename)
    year = year_match.group(1) if year_match else None

    subject_match = re.search(r"_([A-Za-z]+)\.pdf$", filename)
    subject = subject_match.group(1) if subject_match else None

    return year, subject


def edit_course_catalog(filename, year, programType, subject, link, out_pdf=None):
    reader = PdfReader(filename)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.add_metadata({
        "/Year": f"{year}",
        "/ProgramType": f"{programType}",
        "/Subject": f"{subject}",
        "/Link": f"{link}"
    })

    if out_pdf:
        with open(out_pdf, "wb") as f:
            writer.write(f)
    else:
        output_filename = f"{year}_{subject}.pdf"
        # make programType lowercase and replace spaces with underscores
        programType = programType.lower()
        os.makedirs(f"data/{programType}_catalogs", exist_ok=True)
        output_path = os.path.join(f"data/{programType}_catalogs", output_filename)
        with open(output_path, "wb") as f:
            writer.write(f)


def grab_course_catalog_metadata(filename):
    reader = PdfReader(filename)
    text = ""
    for page in reader.pages[:1]:
        page_text = page.extract_text()
        if page_text:
            text += page_text
    #print("--- Extracted Text ---\n", text)
    norm_text = re.sub(r"\s+", " ", text)
    year_match = re.search(r"(20\d{2})-20\d{2} Undergraduate Catalog", norm_text)
    year = year_match.group(1) if year_match else "Unknown"
    program_type = "Unknown"
    subject = "Unknown"
    # Try to extract subject from a line ending with ', Minor', ', Major', ', B.S.', or ', B.A.'
    for line in text.splitlines():
        line = line.strip()
        print(f"DEBUG: Checking line: {line!r}")
        line_match = re.match(r"([A-Za-z0-9 .&-]+),\s*(Minor|Major|B\.S\.|B\.A\.)", line)
        if line_match:
            subject = line_match.group(1).strip()
            if "minor" in line_match.group(2).lower():
                program_type = "Minor"
            else:
                program_type = "Major"
            break
    else:
        # Try to extract subject after 'Chapman University' and before 'Minor' or degree
        alt_match = re.search(r"Chapman University ([A-Za-z0-9 .&-]+?) (Minor|B\.S\.|B\.A\.)", norm_text)
        if alt_match:
            subject = alt_match.group(1).strip()
        else:
            # As a last resort, try to extract the last capitalized phrase
            last_caps = re.findall(r"([A-Z][a-zA-Z& ]{2,})", norm_text)
            if last_caps:
                subject = last_caps[-1].strip()
    if subject == "Unknown":
        print("--- DEBUG: Could not extract subject ---")
        print(text)
    link = "https://example.com/dummy"
    return {
        "Year": year,
        "ProgramType": program_type,
        "Subject": subject,
        "Link": link
    }


def extract_csv_metadata(filename):
    """Extract metadata from CSV filename patterns like Fall_2024.csv"""
    basename = os.path.basename(filename)
    metadata = {}
    
    term_match = re.search(r'(Fall|Spring|Summer|Interterm)_(\d{4})\.csv', basename)
    if term_match:
        metadata['Term'] = term_match.group(1)
        metadata['Year'] = term_match.group(2)
        metadata['SourceType'] = 'Schedule'
        metadata['Subject'] = 'Course Schedule'
        metadata['ProgramType'] = 'Schedule'
    
    return metadata


def process_csv_with_metadata(filename):
    """Add metadata to CSV file by creating a companion metadata file"""
    metadata = extract_csv_metadata(filename)
    
    # Create a metadata file alongside the CSV
    metadata_filename = filename.replace('.csv', '_metadata.json')
    
    import json
    with open(metadata_filename, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Created metadata file: {metadata_filename}")
    return metadata


def extract_course_catalog_year(filename):
    basename = os.path.basename(filename)
    year_match = re.search(r'(\d{4})_Catalog\.pdf', basename)
    if year_match:
        return year_match.group(1)
    return None


def process_raw_course_catalog(filename, output_dir="data/course_listings"):
    year = extract_course_catalog_year(filename)
    if not year:
        print(f"Could not extract year from filename: {filename}")
        return None
    
    reader = PdfReader(filename)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.add_metadata({
        "/Year": year,
        "/ProgramType": "Course_Catalog",
        "/Subject": "Course Catalog",
        "/DocumentType": "course",
        "/Link": f"https://catalog.chapman.edu/content.php?catoid=46&navoid=2429"
    })

    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{year}_Course_Catalog.pdf"
    output_path = os.path.join(output_dir, output_filename)
    
    with open(output_path, "wb") as f:
        writer.write(f)
    
    print(f"Processed course catalog: {filename} -> {output_path}")
    return output_path


def main():
    # Process Major PDFs
    parent_dir = "data/raw_major_catalogs/"
    for filename in os.listdir(parent_dir):
        if filename.endswith(".pdf"):
            metadata = grab_course_catalog_metadata(os.path.join(parent_dir, filename))
            edit_course_catalog(os.path.join(parent_dir, filename),
                                metadata["Year"],
                                metadata["ProgramType"],
                                metadata["Subject"],
                                metadata["Link"])
            print(f"Processed {filename} with metadata: {metadata}")

    # Process Minor PDFs
    parent_dir = "data/raw_minor_catalogs/"
    for filename in os.listdir(parent_dir):
        if filename.endswith(".pdf"):
            metadata = grab_course_catalog_metadata(os.path.join(parent_dir, filename))
            edit_course_catalog(os.path.join(parent_dir, filename),
                                metadata["Year"],
                                metadata["ProgramType"],
                                metadata["Subject"],
                                metadata["Link"])
            print(f"Processed {filename} with metadata: {metadata}")

    # Process Raw Course Catalogs
    raw_course_dir = "data/raw_course_catalogs/"
    if os.path.exists(raw_course_dir):
        for filename in os.listdir(raw_course_dir):
            if filename.endswith(".pdf"):
                input_path = os.path.join(raw_course_dir, filename)
                output_path = process_raw_course_catalog(input_path)
                if output_path:
                    print(f"Successfully processed course catalog: {filename}")
    else:
        print(f"Raw course catalog directory {raw_course_dir} not found")

    # Process CSVs
    # csv_dir = "data/course_history/"
    # if os.path.exists(csv_dir):
    #     for filename in os.listdir(csv_dir):
    #         if filename.endswith(".csv"):
    #             csv_path = os.path.join(csv_dir, filename)
    #             metadata = process_csv_with_metadata(csv_path)
    #             print(f"Processed CSV {filename} with metadata: {metadata}")
    # else:
    #     print(f"CSV directory {csv_dir} not found")


if __name__ == "__main__":
    main()