from pypdf import PdfReader, PdfWriter
import re
import os
import pandas as pd

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
    norm_text = re.sub(r"\s+", " ", text)
    year_match = re.search(r"(20\d{2})-20\d{2} Undergraduate Catalog", norm_text)
    year = year_match.group(1) if year_match else "Unknown"
    program_type = "Unknown"
    subject = "Unknown"
    for line in text.splitlines():
        line = line.strip()
        line_match = re.match(r"([A-Za-z0-9 .&-]+),\s*(Minor|Major|B\.S\.|B\.A\.)", line)
        if line_match:
            subject = line_match.group(1).strip()
            if "minor" in line_match.group(2).lower():
                program_type = "Minor"
            else:
                program_type = "Major"
            break
    else:
        alt_match = re.search(r"Chapman University ([A-Za-z0-9 .&-]+?) (Minor|B\.S\.|B\.A\.)", norm_text)
        if alt_match:
            subject = alt_match.group(1).strip()
        else:
            last_caps = re.findall(r"([A-Z][a-zA-Z& ]{2,})", norm_text)
            if last_caps:
                subject = last_caps[-1].strip()
    link = "https://example.com/dummy"
    return {
        "Year": year,
        "ProgramType": program_type,
        "Subject": subject,
        "Link": link
    }

def main():
    # 4 year plans metadata
    plan_dir = "data/4_year_plans/"
    subject_map = {
        "cs": "Computer Science",
        "ce": "Computer Engineering",
        "se": "Software Engineering",
        "ee": "Electrical Engineering",
        "ds": "Data Science"
    }
    if os.path.exists(plan_dir):
        for filename in os.listdir(plan_dir):
            if filename.endswith(".pdf"):
                subject = None
                for key, value in subject_map.items():
                    if key in filename:
                        subject = value
                        break
                if not subject:
                    subject = "Unknown"
                reader = PdfReader(os.path.join(plan_dir, filename))
                writer = PdfWriter()
                for page in reader.pages:
                    writer.add_page(page)
                writer.add_metadata({
                    "/Subject": f"{subject}"
                })
                os.makedirs("data/4_year_plans", exist_ok=True)
                output_path = os.path.join("data/4_year_plans", filename)
                with open(output_path, "wb") as f:
                    writer.write(f)
                print(f"Processed 4-year plan: {filename} -> {output_path}")

    # major course catalog metadata
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

    # minor course catalog metadata
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

if __name__ == "__main__":
    main()
