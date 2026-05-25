"""
Seed Data Ingestion Script for Grandmaster.AI

Run this script to populate the ChromaDB vector database with
annotated chess positions for the RAG pipeline.

Usage:
    python -m data.seed_data
"""

import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.rag_engine import ingest_annotations, init_vector_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Ingest seed data into ChromaDB."""
    logger.info("=" * 60)
    logger.info("Grandmaster.AI — Seed Data Ingestion")
    logger.info("=" * 60)

    # Initialize the vector database
    collection = init_vector_db()
    logger.info(f"Current collection size: {collection.count()} documents")

    # Ingest annotations
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "annotations")
    count = ingest_annotations(data_dir)

    # Verify
    final_count = collection.count()
    logger.info(f"\n{'=' * 60}")
    logger.info(f"Ingestion complete!")
    logger.info(f"  New documents added: {count}")
    logger.info(f"  Total documents in DB: {final_count}")
    logger.info(f"{'=' * 60}")

    # Test a sample query
    if final_count > 0:
        logger.info("\nRunning test query...")
        results = collection.query(
            query_texts=["A tactical blunder involving an undefended piece in the middlegame"],
            n_results=3,
        )
        if results and results["documents"]:
            for i, (doc, meta) in enumerate(zip(results["documents"][0], results["metadatas"][0])):
                logger.info(f"\n  Match {i+1}: {meta.get('source', 'Unknown')}")
                logger.info(f"  Theme: {meta.get('theme', 'N/A')}")
                logger.info(f"  Preview: {doc[:120]}...")


if __name__ == "__main__":
    main()
