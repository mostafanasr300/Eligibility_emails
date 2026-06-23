import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from main import apply_query
from CHromdb import creat_db
from graph_db import get_graph_provider

def test_chroma_initialization():
    collection = creat_db("Data&relation.txt")
    assert collection.count() > 0

def test_graph_query():
    provider, name = get_graph_provider("Data&relation.txt")
    results = provider.query_graph(["React"])
    assert isinstance(results, list)

def test_hybrid_blending():
    collection = creat_db("Data&relation.txt")
    test_job_json = {
        "role": "Frontend Developer",
        "skills": ["React"],
        "description": "Looking for React dev"
    }
    
    results = apply_query(test_job_json, collection, w_vector=0.5, w_graph=0.5)
    
    assert "hybrid" in results
    assert len(results["hybrid"]) > 0
    top_result = results["hybrid"][0]
    # Validate result structure, not a specific course ranking (ranking is data-dependent)
    assert "course_id" in top_result
    assert isinstance(top_result["course_id"], str)
    assert top_result["course_id"].startswith("CRS-")
