#!/usr/bin/env python3

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.config_loader import load_config

sys.path.insert(0, os.path.dirname(__file__))
from fse_ingestion import FSEIngestion


def main():
    config = load_config()
    ingestion = FSEIngestion()
    
    data_dirs_config = config.get('data_directories', {})
    data_dirs = [
        data_dirs_config.get('major_catalogs', 'data/major_catalog'),
        data_dirs_config.get('minor_catalogs', 'data/minor_catalog'),
        data_dirs_config.get('general_knowledge', 'data/general_knowledge'),
        data_dirs_config.get('4_year_plans', 'data/4_year_plans')
    ]
    
    print(f"Ingesting from directories: {data_dirs}")
    ingestion.bulk_ingest(data_dirs)


if __name__ == "__main__":
    main()
