import os
import json
from cache_manager import get_chroma_cache, set_chroma_cache, _compute_file_hash


def load_data_from_files(data_paths):
    """Load and merge data from multiple JSON data files."""
    all_data = []
    seen_ids = set()
    for path in data_paths:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                cid = item.get("course_id")
                if cid and cid not in seen_ids:
                    seen_ids.add(cid)
                    all_data.append(item)
    return all_data


def _compute_multi_hash(data_paths):
    """Compute combined hash of multiple source files."""
    combined = ""
    for path in sorted(data_paths):
        combined += _compute_file_hash(path) or ""
    return combined


def creat_db(data_paths=None, reset=False):
    """
    ChromaDB collection builder that accepts one or more data files.
    
    Args:
        data_paths: List of paths to JSON data files (or single path string).
        reset: Force re-index even if cache is valid.
    """
    try:
        import chromadb
    except Exception as e:
        raise ModuleNotFoundError(
            "The 'chromadb' package is required for the vector DB but is not installed. "
            "Install it with `pip install chromadb` or provide an alternative vector store. "
            f"(Original error: {e})"
        )

    # Normalize data_paths
    if data_paths is None:
        data_paths = ["Data&relation.txt"]
    elif isinstance(data_paths, str):
        data_paths = [data_paths]

    # Load and merge data from all files
    data = load_data_from_files(data_paths)
    if not data:
        raise FileNotFoundError(f"No valid data found in paths: {data_paths}")

    db = chromadb.PersistentClient("./chroma_db")

    # --- Caching: Check if we can skip re-indexing ---
    if not reset:
        cached_state = get_chroma_cache(data_paths[0])
        if cached_state is not None:
            try:
                collection = db.get_or_create_collection(name="courses_links")
                if collection.count() == cached_state.get("course_count", 0):
                    print(f"ChromaDB cache valid ({collection.count()} courses). Skipping re-index.")
                    return collection
            except Exception:
                pass

    # If reset is requested or cache is invalid, rebuild
    try:
        collection = db.get_or_create_collection(name="courses_links")
        if reset or collection.count() != len(data):
            db.delete_collection(name="courses_links")
            collection = db.get_or_create_collection(name="courses_links")
        else:
            print(f"ChromaDB already contains {collection.count()} courses. Saving new cache.")
            set_chroma_cache({"course_count": collection.count()}, data_paths[0])
    except Exception as e:
        print(f"Error managing collection: {e}")
        collection = db.get_or_create_collection(name="courses_links")

    if not collection.count():
        documents = []
        metadatas = []
        ids = []

        for item in data:
            course_id = item["course_id"]
            title = item["title"]
            url = item["url"]
            platform = item["platform"]

            domains = ", ".join(item.get("domains", []))

            tech_stack = item.get("tech_stack", {})
            langs = ", ".join(tech_stack.get("languages", []))
            frameworks = ", ".join(tech_stack.get("frameworks_libraries", []))
            databases = ", ".join(tech_stack.get("databases", []))
            paradigms = ", ".join(tech_stack.get("paradigms_architectures", []))

            # Build rich document string for embedding
            doc_str = (
                f"Course Title: {title}. "
                f"Platform: {platform}. "
                f"Domains: {domains}. "
                f"Languages: {langs}. "
                f"Frameworks & Libraries: {frameworks}. "
                f"Databases: {databases}. "
                f"Paradigms & Architectures: {paradigms}."
            )

            documents.append(doc_str)
            metadatas.append({
                "course_id": course_id,
                "url": url,
                "links": url,
                "links_url": url,
                "title": title,
                "platform": platform
            })
            ids.append(course_id)

        # Bulk add to Chroma DB
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        print(f"Chroma DB collection populated with {len(ids)} courses from {len(data_paths)} file(s).")

        # Save cache state
        set_chroma_cache({"course_count": len(ids)}, data_paths[0])

    return collection