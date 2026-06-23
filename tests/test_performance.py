import sys
import os


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import apply_query  # noqa: E402
from CHromdb import creat_db  # noqa: E402


def test_hybrid_query_performance(benchmark):
    collection = creat_db("Data&relation.txt")

    test_job_json = {
        "role": "Frontend Developer",
        "skills": ["React"],
        "description": "Looking for React dev"
    }

    # Benchmark the hybrid blending function
    result = benchmark(apply_query, test_job_json, collection, w_vector=0.5, w_graph=0.5)

    assert len(result["hybrid"]) > 0
