"""
Test suite for TableRAG agent — mirrors the 10 preset queries.

Strategies covered:
  Aggregation  — COUNT, GROUP BY
  SQL          — SELECT / listing by schema fields
  Semantic     — FAISS vector similarity (with optional filter_category)
  Hybrid       — SQL filter → vector ranking

Run from project root:
    python tests/test_queries.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from api import run_query_structured

TEST_CASES = [
    # --- Aggregation ---
    (
        "Aggregation: count by category",
        "How many articles are in each category?",
    ),
    (
        "Aggregation: by year and category",
        "What are the articles by year and category?",
    ),

    # --- SQL Listing ---
    (
        "SQL: list sports articles",
        "List all sports articles.",
    ),
    (
        "SQL: articles by Reuters",
        "Show me articles by Reuters.",
    ),

    # --- Semantic Search ---
    (
        "Semantic: electric vehicles",
        "What do articles say about electric vehicles?",
    ),
    (
        "Semantic: articles about children",
        "What articles about children do you have?",
    ),
    (
        "Semantic: fashion trends",
        "What are the trends in fashion?",
    ),
    (
        "Semantic: cancer and chemotherapy",
        "What do health articles say about cancer and chemotherapy?",
    ),

    # --- Hybrid (SQL filter -> vector ranking) ---
    (
        "Hybrid: stocks and inflation (word count range)",
        "In business articles between 500 and 700 words, which ones discuss stocks or inflation?",
    ),
    (
        "Hybrid: tech crypto 2023",
        "Tell me technology articles about crypto in 2023.",
    ),
]


def run_all():
    total = len(TEST_CASES)
    print(f"\n{'='*60}")
    print(f"  TableRAG Test Suite  --  {total} test cases")
    print(f"{'='*60}\n")

    for i, (description, query) in enumerate(TEST_CASES, 1):
        print(f"\n[{i}/{total}] {description}")
        print(f"{'─'*60}")
        result = run_query_structured(query)
        print(f"Path:     {result.get('tool_path')}")
        print(f"Response: {result.get('response')}")


if __name__ == "__main__":
    run_all()
