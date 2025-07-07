echo "Cleaning PDF files (with automatic fallback to safe mode)..."
python src/utils/clean_pdf_hyperlinks.py data/major_catalogs --no-backup
python src/utils/clean_pdf_hyperlinks.py data/minor_catalogs --no-backup
python src/utils/clean_pdf_hyperlinks.py data/course_listings --no-backup