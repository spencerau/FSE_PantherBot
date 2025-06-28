from pypdf import PdfReader, PdfWriter
import re
import os

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
        os.makedirs(f"data/{programType}_Catalogs", exist_ok=True)
        output_path = os.path.join(f"data/{programType}_Catalogs", output_filename)
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
    # Allow for any character except comma (non-greedy), then comma, then degree/minor
    subject_match = re.search(r"([A-Za-z0-9 .&-]+?),\s*(B\.S\.|B\.A\.|Minor)", norm_text, re.IGNORECASE)
    #print("--- Regex Match ---", subject_match.groups() if subject_match else "No match")
    if subject_match:
        subject = subject_match.group(1).strip()
        if "minor" in subject_match.group(2).lower():
            program_type = "Minor"
        else:
            program_type = "Major"
    else:
        if re.search(r"B\.?S\.?|B\.?A\.?", norm_text, re.IGNORECASE):
            program_type = "Major"
        elif re.search(r"Minor", norm_text, re.IGNORECASE):
            program_type = "Minor"
    link = "https://example.com/dummy"
    return {
        "Year": year,
        "ProgramType": program_type,
        "Subject": subject,
        "Link": link
    }


def main():
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
            print("Metadata saved to:", os.path.join("data", f"{metadata['Year']}_{metadata['Subject']}.pdf"))

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
            print("Metadata saved to:", os.path.join("data", f"{metadata['Year']}_{metadata['Subject']}.pdf"))


if __name__ == "__main__":
    main()