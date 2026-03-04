#!/usr/bin/env python3
"""
Quick test script to debug ingestion issues with a single file
"""

import os
import sys

# Set config before any imports
os.environ['CONFIG_FILE'] = 'config.local.yaml'

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import from installed package
from core_rag.ingestion.ingest import UnifiedIngestion

# Import FSE metadata extractor with proper path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'ingestion'))
from fse_edit_metadata import FSEMetadataExtractor

import json


def main():
    print("="*60)
    print("Single File Ingestion Test")
    print("="*60)
    
    test_file = 'data/major_catalog_json/2022/2022_CompSci.json'
    
    print(f"\nTest file: {test_file}\n")
    
    # Load file to see structure
    with open(test_file, 'r') as f:
        data = json.load(f)
    
    print(f"Program: {data.get('program', 'N/A')}")
    print(f"Sections in JSON: {len(data.get('sections', []))}")
    
    # Create ingestion
    print("\nInitializing ingestion...")
    ingestion = UnifiedIngestion()
    ingestion.metadata_extractor = FSEMetadataExtractor()
    
    # Extract content items
    print("Extracting content for embedding...")
    items = ingestion._extract_json_content_for_embedding(data)
    print(f"Content items extracted: {len(items)}\n")
    
    # Test embedding each item
    print("Testing embeddings:")
    print("-" * 60)
    success_count = 0
    fail_count = 0
    
    for i, item in enumerate(items):
        text = item['text']
        section_name = item.get('section_name', 'Unknown')
        text_len = len(text)
        
        print(f"\n[{i+1}/{len(items)}] {section_name}")
        print(f"  Length: {text_len} chars")
        
        try:
            embedding = ingestion._get_embedding(text)
            if embedding and len(embedding) > 0:
                print(f"  ✓ Success: {len(embedding)}D")
                success_count += 1
            else:
                print(f"  ✗ Failed: Empty embedding")
                print(f"  Preview: {text[:100]}...")
                fail_count += 1
        except Exception as e:
            print(f"  ✗ Error: {e}")
            print(f"  Preview: {text[:100]}...")
            fail_count += 1
    
    print("\n" + "="*60)
    print(f"SUMMARY: {success_count} succeeded, {fail_count} failed")
    print("="*60)
    
    if fail_count > 0:
        print("\n⚠ Some embeddings failed. Check chunk size settings.")
    else:
        print("\n✓ All embeddings succeeded! Ready for full ingestion.")
    
    return success_count, fail_count


if __name__ == "__main__":
    success, failed = main()
    sys.exit(0 if failed == 0 else 1)
