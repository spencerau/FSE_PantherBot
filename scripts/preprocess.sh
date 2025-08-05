#!/bin/bash
echo "Editing metadata for PDF files..."
python3 src/ingestion/edit_metadata.py

echo "Cleaning PDF files (with automatic fallback to safe mode)..."
python3 src/utils/clean_pdf_hyperlinks.py data/major_catalogs --no-backup --safe
python3 src/utils/clean_pdf_hyperlinks.py data/minor_catalogs --no-backup --safe
python3 src/utils/clean_pdf_hyperlinks.py data/general_knowledge --no-backup --safe
python3 src/utils/clean_pdf_hyperlinks.py data/4_year_plans --no-backup --safe
echo "PDF files cleaned successfully."

