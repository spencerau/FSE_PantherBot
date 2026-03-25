from docling.document_converter import DocumentConverter, ImageFormatOption
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.datamodel.base_models import InputFormat
import glob
import os

pipeline_options = PdfPipelineOptions(
    do_ocr=True,
    do_table_structure=True
)

converter = DocumentConverter(
    format_options={
        InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options)
    }
)

SUPPORTED_EXT = {".pdf", ".png", ".jpg", ".jpeg"}

for year in ["2023", "2024", "2025"]:
    dir_path = f"data/4_year_plans/{year}"
    pattern = os.path.join(dir_path, "*")
    files = glob.glob(pattern)
    if not files:
        print(f"No files found in {dir_path}")
        continue

    for path in files:
        if os.path.isdir(path):
            continue
        ext = os.path.splitext(path)[1].lower()
        if ext not in SUPPORTED_EXT:
            print(f"Skipping unsupported file type: {path}")
            continue

        print(f"Processing {path}...")
        try:
            result = converter.convert(path)
            doc = result.document
            base = os.path.splitext(os.path.basename(path))[0]
            out_md = os.path.join(dir_path, f"{base}.md")
            with open(out_md, "w") as f:
                f.write(doc.export_to_markdown())
            print(f"Wrote markdown to {out_md}")
        except Exception as e:
            print(f"Error processing {path}: {e}")


# # result = converter.convert("CS.png")
# result = converter.convert("data/4_year_plans/2023/2023_CompSci_4yearplan.pdf")

# doc = result.document

# with open("out.md", "w") as f:
#     f.write(doc.export_to_markdown())

# print(doc.export_to_markdown())