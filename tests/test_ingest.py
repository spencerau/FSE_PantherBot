import pytest
import tempfile
import os

from fse_ingestion.fse_edit_metadata import FSEMetadataExtractor

FSE_COLLECTIONS = ["major_catalogs", "minor_catalogs", "4_year_plans", "general_knowledge"]


# ---------------------------------------------------------------------------
# FSEMetadataExtractor — unit tests (no DB / Qdrant required)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def extractor():
    return FSEMetadataExtractor()


def test_metadata_extraction_4year_plan_filename(extractor, tmp_path):
    f = tmp_path / "4_year_plans" / "2023_cs_plan.pdf"
    meta = extractor.extract_metadata_from_path(str(f))
    assert meta["Year"] == "2023"
    assert meta["SubjectCode"] == "cs"
    assert meta["DocumentType"] == "4_year_plan"


def test_metadata_extraction_major_catalog_dir(extractor, tmp_path):
    f = tmp_path / "major_catalog" / "2024_ee.pdf"
    meta = extractor.extract_metadata_from_path(str(f))
    assert meta["DocumentType"] == "major_catalog"
    assert meta["Year"] == "2024"
    assert meta["SubjectCode"] == "ee"


def test_metadata_extraction_minor_catalog_dir(extractor, tmp_path):
    f = tmp_path / "minor_catalog" / "2022_anal.pdf"
    meta = extractor.extract_metadata_from_path(str(f))
    assert meta["DocumentType"] == "minor_catalog"
    assert meta["Year"] == "2022"
    assert meta["SubjectCode"] == "anal"


def test_metadata_extraction_no_filename_match(extractor, tmp_path):
    f = tmp_path / "major_catalog" / "some_document.pdf"
    meta = extractor.extract_metadata_from_path(str(f))
    assert meta["DocumentType"] == "major_catalog"
    assert "Year" not in meta
    assert "SubjectCode" not in meta


def test_metadata_extraction_general_knowledge_fallback(extractor, tmp_path):
    f = tmp_path / "docs" / "policy.pdf"
    meta = extractor.extract_metadata_from_path(str(f))
    assert meta["DocumentType"] == "general_knowledge"


def test_metadata_extraction_all_subject_codes(extractor, tmp_path):
    codes = ["cs", "ce", "ds", "se", "ee"]
    for code in codes:
        f = tmp_path / "major_catalog" / f"2024_{code}.pdf"
        meta = extractor.extract_metadata_from_path(str(f))
        assert meta["SubjectCode"] == code


# ---------------------------------------------------------------------------
# FSEIngestion — integration tests (requires Qdrant + Ollama)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def ingestion():
    from fse_ingestion.fse_ingestion import FSEIngestion
    return FSEIngestion()


@pytest.mark.integration
def test_ingestion_initialization(ingestion):
    assert ingestion.client is not None
    assert ingestion.config is not None
    assert ingestion.embedding_gen is not None
    assert ingestion.file_ingestor is not None


@pytest.mark.integration
def test_collection_exists_post_init(ingestion):
    existing = {c.name for c in ingestion.client.get_collections().collections}
    for coll in FSE_COLLECTIONS:
        coll_name = ingestion.config["qdrant"]["collections"].get(coll, coll)
        assert coll_name in existing, f"Collection '{coll_name}' not found in Qdrant"


@pytest.mark.integration
def test_doc_id_generation_consistency(ingestion, tmp_path):
    from core_rag.utils.doc_id import generate_doc_id

    f = tmp_path / "2024_cs.pdf"
    f.write_text("dummy")
    id1 = generate_doc_id(str(f), ingestion.base_dir)
    id2 = generate_doc_id(str(f), ingestion.base_dir)
    assert id1 == id2


@pytest.mark.integration
def test_doc_ids_differ_for_different_files(ingestion, tmp_path):
    from core_rag.utils.doc_id import generate_doc_id

    f1 = tmp_path / "2024_cs.pdf"
    f2 = tmp_path / "2024_ce.pdf"
    f1.write_text("dummy")
    f2.write_text("dummy")
    assert generate_doc_id(str(f1), ingestion.base_dir) != generate_doc_id(str(f2), ingestion.base_dir)


@pytest.mark.integration
def test_collection_has_documents(ingestion):
    for coll_key in FSE_COLLECTIONS:
        coll_name = ingestion.config["qdrant"]["collections"].get(coll_key, coll_key)
        info = ingestion.client.get_collection(coll_name)
        assert info.points_count > 0, f"Collection '{coll_name}' is empty — run ingestion first"
