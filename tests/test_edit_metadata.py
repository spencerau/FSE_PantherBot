import os
import pytest
from pathlib import Path
import sys
from pypdf import PdfReader

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from ingestion.edit_metadata import edit_course_catalog, grab_course_catalog_metadata, extract_year_and_subject

project_root = Path(__file__).parent.parent


@pytest.mark.parametrize(
    "filepath, expected",
    [
        # Major catalog tests - 2022, 2023, 2024
        (
            "data/raw_major_catalogs/2022_CompEng.pdf",
            {"/Year": "2022", "/ProgramType": "Major", "/Subject": "Computer Engineering"},
        ),
        (
            "data/raw_major_catalogs/2022_CompSci.pdf",
            {"/Year": "2022", "/ProgramType": "Major", "/Subject": "Computer Science"},
        ),
        (
            "data/raw_major_catalogs/2023_CompEng.pdf",
            {"/Year": "2023", "/ProgramType": "Major", "/Subject": "Computer Engineering"},
        ),
        (
            "data/raw_major_catalogs/2023_CompSci.pdf",
            {"/Year": "2023", "/ProgramType": "Major", "/Subject": "Computer Science"},
        ),
        (
            "data/raw_major_catalogs/2024_CompEng.pdf",
            {"/Year": "2024", "/ProgramType": "Major", "/Subject": "Computer Engineering"},
        ),
        (
            "data/raw_major_catalogs/2024_CompSci.pdf",
            {"/Year": "2024", "/ProgramType": "Major", "/Subject": "Computer Science"},
        ),
        # Minor catalog tests - 2022, 2023, 2024
        (
            "data/raw_minor_catalogs/2022-2023_Undergrad_Analytics.pdf",
            {"/Year": "2022", "/ProgramType": "Minor", "/Subject": "Analytics"},
        ),
        (
            "data/raw_minor_catalogs/2022-2023_Undergrad_CompSci.pdf",
            {"/Year": "2022", "/ProgramType": "Minor", "/Subject": "Computer Science"},
        ),
        (
            "data/raw_minor_catalogs/2023-2024_Undergrad_Analytics.pdf",
            {"/Year": "2023", "/ProgramType": "Minor", "/Subject": "Analytics"},
        ),
        (
            "data/raw_minor_catalogs/2023-2024_Undergrad_CompEng.pdf",
            {"/Year": "2023", "/ProgramType": "Minor", "/Subject": "Computer Engineering"},
        ),
    ],
)
def test_edit_and_check_metadata(filepath, expected, tmp_path):
    abs_path = project_root / filepath
    
    if not abs_path.exists():
        pytest.skip(f"Test file {abs_path} does not exist")
    
    out_pdf = tmp_path / f"{expected['/Year']}_{expected['/Subject'].replace(' ', '_')}.pdf"

    metadata = grab_course_catalog_metadata(str(abs_path))
    
    edit_course_catalog(
        str(abs_path),
        metadata["Year"],
        metadata["ProgramType"],
        metadata["Subject"],
        out_pdf=str(out_pdf)
    )

    reader = PdfReader(str(out_pdf))
    meta = reader.metadata
    for key, value in expected.items():
        print(f"Comparing {key}: expected={value!r}, actual={meta.get(key)!r}")
        assert meta.get(key) == value

# Commented out tests that require missing function process_raw_course_catalog
# @pytest.mark.parametrize(
#     "filepath, expected_year",
#     [
#         ("data/raw_course_catalogs/2022_Catalog.pdf", "2022"),
#         ("data/raw_course_catalogs/2023_Catalog.pdf", "2023"),
#         ("data/raw_course_catalogs/2024_Catalog.pdf", "2024"),
#     ],
# )
# def test_course_catalog_metadata(filepath, expected_year, tmp_path):
#     """Test processing of raw course catalogs with year extraction"""
#     abs_path = project_root / filepath
    
#     if not abs_path.exists():
#         pytest.skip(f"Test file {abs_path} does not exist")
    
#     output_dir = str(tmp_path / "course_listings")
    
#     output_path = process_raw_course_catalog(str(abs_path), output_dir)
    
#     assert output_path is not None
#     assert os.path.exists(output_path)
    
#     reader = PdfReader(output_path)
#     meta = reader.metadata
    
#     expected_metadata = {
#         "/Year": expected_year,
#         "/ProgramType": "Course_Catalog",
#         "/Subject": "Course Catalog",
#         "/DocumentType": "course"
#     }
    
#     for key, value in expected_metadata.items():
#         print(f"Comparing {key}: expected={value!r}, actual={meta.get(key)!r}")
#         assert meta.get(key) == value
    
#     expected_filename = f"{expected_year}_Course_Catalog.pdf"
#     assert os.path.basename(output_path) == expected_filename


# def test_course_catalog_integration(tmp_path):
#     """Integration test to verify course catalogs are processed and stored correctly"""
#     course_catalog_dir = project_root / "data" / "raw_course_catalogs"
    
#     if not course_catalog_dir.exists():
#         pytest.skip("Raw course catalogs directory does not exist")
    
#     pdf_files = list(course_catalog_dir.glob("*.pdf"))
#     if not pdf_files:
#         pytest.skip("No PDF files found in raw course catalogs directory")
    
#     output_dir = str(tmp_path / "course_listings")
    
#     processed_files = []
#     for pdf_file in pdf_files:
#         output_path = process_raw_course_catalog(str(pdf_file), output_dir)
#         if output_path:
#             processed_files.append(output_path)
    
#     assert len(processed_files) > 0, "No course catalog files were processed"
    
#     for output_path in processed_files:
#         reader = PdfReader(output_path)
#         meta = reader.metadata
        
#         required_fields = ["/Year", "/ProgramType", "/Subject", "/DocumentType"]
#         for field in required_fields:
#             assert field in meta, f"Missing required metadata field {field}"

#         assert meta.get("/ProgramType") == "Course_Catalog"
#         assert meta.get("/Subject") == "Course Catalog"
#         assert meta.get("/DocumentType") == "course"
        
#         year = meta.get("/Year")
#         assert year and len(year) == 4 and year.isdigit(), f"Invalid year format: {year}"
