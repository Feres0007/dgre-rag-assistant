"""Compatibility entrypoint; extraction lives in the versioned package."""
from dgre_rag.ingestion.reference_catalog import main
if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--release-id')
    main(parser.parse_args().release_id)
