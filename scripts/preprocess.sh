#!/bin/bash

echo "Cleaning PDF files (with automatic fallback to safe mode)..."
python src/utils/clean_pdf_hyperlinks.py data/major_catalogs --no-backup
python src/utils/clean_pdf_hyperlinks.py data/minor_catalogs --no-backup
python src/utils/clean_pdf_hyperlinks.py data/course_listings --no-backup
python src/utils/clean_pdf_hyperlinks.py data/general_knowledge --no-backup
python src/utils/clean_pdf_hyperlinks.py data/4_year_plans --no-backup
echo "PDF files cleaned successfully."

echo "Editing metadata for PDF files..."
python src/ingestion/edit_metadata.py
