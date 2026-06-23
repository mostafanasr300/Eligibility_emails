import os
from main import prepare_model, apply_query
from CHromdb import creat_db
from graph_db import get_graph_provider

def run_tests():
    print("=== Testing Hybrid RAG System ===")
    
    # 1. Initialize Chroma DB
    print("\n1. Initializing Chroma DB...")
    collection = creat_db("Data&relation.txt")
    print(f"Chroma DB initialized. Document count: {collection.count()}")
    assert collection.count() > 0, "Chroma DB should have documents indexed."

    # 2. Get Graph Provider
    print("\n2. Getting Graph Provider...")
    graph_provider, provider_name = get_graph_provider("Data&relation.txt")
    print(f"Active Graph Provider: {provider_name}")

    # 3. Test Graph Query
    test_skills = ["Vue.js", "Ruby", "PostgreSQL", "JavaScript"]
    print(f"\n3. Querying Graph for skills: {test_skills}...")
    graph_results = graph_provider.query_graph(test_skills)
    print(f"Graph matches found: {len(graph_results)}")
    
    # Print top graph matches
    for g in graph_results[:3]:
        print(f" - Course: {g['title']} ({g['course_id']}) | Score: {g['score']} | Matches: {g['matched_skills']}")
    
    assert len(graph_results) > 0, "Graph query should return matches."
    # Course CRS-003 teaches Vue.js, Ruby, PostgreSQL, JavaScript, so it should be the top match
    top_match = graph_results[0]
    assert top_match["course_id"] == "CRS-003", f"Top match should be CRS-003, got {top_match['course_id']}"

    # 4. Test Hybrid Query Blending
    test_job_json = {
        "role": "Frontend Developer",
        "skills": ["Vue.js", "JavaScript"],
        "description": "We are looking for a Frontend Developer with strong Vue.js and JavaScript experience to build web applications."
    }
    print("\n4. Running Hybrid query...")
    results = apply_query(test_job_json, collection, w_vector=0.5, w_graph=0.5)
    
    print(f"Hybrid recommendations count: {len(results['hybrid'])}")
    print(f"Vector-only matches: {len(results['vector'])}")
    print(f"Graph-only matches: {len(results['graph'])}")
    
    assert len(results["hybrid"]) > 0, "Hybrid results should not be empty."
    
    print("\nTop 3 Hybrid Course Recommendations:")
    for h in results["hybrid"][:3]:
        print(f" - {h['title']} ({h['course_id']}) | Combined: {h['combined_score']:.3f} | Vector: {h['vector_score']:.3f} | Graph: {h['graph_score']:.3f}")
        
    print("\n=== All Tests Passed Successfully! ===")

if __name__ == "__main__":
    # Add project root directory to path if needed (not needed here since executing in same folder)
    run_tests()
