import os
import pytest
from pathlib import Path
import sys
from pypdf import PdfReader

project_root = Path(__file__).parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from src.preprocess.edit_metadata import edit_course_catalog, grab_course_catalog_metadata


@pytest.mark.parametrize(
    "filepath, expected",
    [
        (
            "data/raw_major_catalogs/2022-2023_Undergrad_CompEng.pdf",
            {"/Year": "2022", "/ProgramType": "Major", "/Subject": "Computer Engineering", "/Link": "https://example.com/dummy"},
        ),
        (
            "data/raw_major_catalogs/2022-2023_Undergrad_CompSci.pdf",
            {"/Year": "2022", "/ProgramType": "Major", "/Subject": "Computer Science", "/Link": "https://example.com/dummy"},
        ),
        (
            "data/raw_major_catalogs/2023-2024_Undergrad_SoftEng.pdf",
            {"/Year": "2023", "/ProgramType": "Major", "/Subject": "Software Engineering", "/Link": "https://example.com/dummy"},
        ),
        (
            "data/raw_minor_catalogs/2022-2023_Undergrad_Analytics.pdf",
            {"/Year": "2022", "/ProgramType": "Minor", "/Subject": "Analytics", "/Link": "https://example.com/dummy"},
        ),
        (
            "data/raw_minor_catalogs/2023-2024_Undergrad_GameDev.pdf",
            {"/Year": "2023", "/ProgramType": "Minor", "/Subject": "Game Development Programming", "/Link": "https://example.com/dummy"},
        ),
        (
            "data/raw_minor_catalogs/2023-2024_Undergrad_ISP.pdf",
            {"/Year": "2023", "/ProgramType": "Minor", "/Subject": "Information Security and Policy", "/Link": "https://example.com/dummy"},
        ),
    ],
)
def test_edit_and_check_metadata(filepath, expected, tmp_path):
    abs_path = os.path.join(project_root, filepath)
    out_pdf = tmp_path / f"{expected['/Year']}_{expected['/Subject']}.pdf"

    metadata = grab_course_catalog_metadata(abs_path)
    
    edit_course_catalog(
        abs_path,
        metadata["Year"],
        metadata["ProgramType"],
        metadata["Subject"],
        metadata["Link"],
        out_pdf=str(out_pdf)
    )

    reader = PdfReader(str(out_pdf))
    meta = reader.metadata
    for key, value in expected.items():
        print(f"Comparing {key}: expected={value!r}, actual={meta.get(key)!r}")
        assert meta.get(key) == value
