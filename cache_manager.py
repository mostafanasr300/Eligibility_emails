"""
Cache Manager for Neo4j and ChromaDB.

Persists database state metadata locally so application startup
takes seconds instead of minutes. Re-indexing only occurs when
source data changes (checked via file modification time + hash).
"""
import os
import json
import hashlib
import time
from typing import Optional, Dict, Any

CACHE_DIR = "./chroma_db/.db_cache"
NEO4J_CACHE_FILE = os.path.join(CACHE_DIR, "neo4j_cache.json")
CHROMA_CACHE_FILE = os.path.join(CACHE_DIR, "chroma_cache.json")
QUERY_CACHE_FILE = os.path.join(CACHE_DIR, "query_cache.json")


def _ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR, exist_ok=True)


def _compute_file_hash(data_path: str) -> str:
    """Compute SHA256 hash of the source data file for change detection."""
    if not os.path.exists(data_path):
        return ""
    hasher = hashlib.sha256()
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            content = f.read().replace("\r\n", "\n")
            hasher.update(content.encode("utf-8"))
    except UnicodeDecodeError:
        # Fallback for non-text files if ever needed
        with open(data_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
    return hasher.hexdigest()


def _get_file_mtime(data_path: str) -> float:
    """Get file modification time."""
    if not os.path.exists(data_path):
        return 0.0
    return os.path.getmtime(data_path)


# ─── Neo4j Cache ─────────────────────────────────────────────────────────

def get_neo4j_cache(data_path: str = "Data&relation.txt") -> Optional[Dict[str, Any]]:
    """
    Return cached Neo4j population state if source data hasn't changed.
    Returns None if cache is invalid or missing.
    """
    _ensure_cache_dir()
    if not os.path.exists(NEO4J_CACHE_FILE):
        return None

    try:
        with open(NEO4J_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)

        # Check if source data has changed
        stored_hash = cache.get("data_hash", "")
        current_hash = _compute_file_hash(data_path)
        if stored_hash != current_hash:
            print("Cache invalidated: source data file has changed.")
            return None

        # Check if cache is fresh (less than 24 hours old)
        cached_time = cache.get("cached_at", 0)
        if time.time() - cached_time > 86400:  # 24 hours
            print("Cache expired (older than 24 hours).")
            return None

        print("Neo4j cache hit — skipping population.")
        return cache.get("state", {})
    except Exception as e:
        print(f"Error reading Neo4j cache: {e}")
        return None


def set_neo4j_cache(state: Dict[str, Any], data_path: str = "Data&relation.txt"):
    """Save Neo4j population state to cache."""
    _ensure_cache_dir()
    try:
        cache = {
            "cached_at": time.time(),
            "data_hash": _compute_file_hash(data_path),
            "data_mtime": _get_file_mtime(data_path),
            "state": state
        }
        with open(NEO4J_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        print("Neo4j cache saved.")
    except Exception as e:
        print(f"Error saving Neo4j cache: {e}")


def invalidate_neo4j_cache():
    """Force Neo4j cache invalidation."""
    _ensure_cache_dir()
    try:
        if os.path.exists(NEO4J_CACHE_FILE):
            os.remove(NEO4J_CACHE_FILE)
            print("Neo4j cache invalidated.")
    except Exception as e:
        print(f"Error invalidating Neo4j cache: {e}")


# ─── ChromaDB Cache ──────────────────────────────────────────────────────

def get_chroma_cache(data_path: str = "Data&relation.txt") -> Optional[Dict[str, Any]]:
    """
    Return cached ChromaDB state if source data hasn't changed.
    Returns None if cache is invalid or missing.
    """
    _ensure_cache_dir()
    if not os.path.exists(CHROMA_CACHE_FILE):
        return None

    try:
        with open(CHROMA_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)

        stored_hash = cache.get("data_hash", "")
        current_hash = _compute_file_hash(data_path)
        if stored_hash != current_hash:
            print("ChromaDB cache invalidated: source data file has changed.")
            return None

        cached_time = cache.get("cached_at", 0)
        if time.time() - cached_time > 86400:
            print("ChromaDB cache expired (older than 24 hours).")
            return None

        print("ChromaDB cache hit — skipping re-indexing.")
        return cache.get("state", {})
    except Exception as e:
        print(f"Error reading ChromaDB cache: {e}")
        return None


def set_chroma_cache(state: Dict[str, Any], data_path: str = "Data&relation.txt"):
    """Save ChromaDB state to cache."""
    _ensure_cache_dir()
    try:
        cache = {
            "cached_at": time.time(),
            "data_hash": _compute_file_hash(data_path),
            "data_mtime": _get_file_mtime(data_path),
            "state": state
        }
        with open(CHROMA_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        print("ChromaDB cache saved.")
    except Exception as e:
        print(f"Error saving ChromaDB cache: {e}")


def invalidate_chroma_cache():
    """Force ChromaDB cache invalidation."""
    _ensure_cache_dir()
    try:
        if os.path.exists(CHROMA_CACHE_FILE):
            os.remove(CHROMA_CACHE_FILE)
            print("ChromaDB cache invalidated.")
    except Exception as e:
        print(f"Error invalidating ChromaDB cache: {e}")


# ─── Query Result Cache ──────────────────────────────────────────────────

def get_cached_query(query_key: str) -> Optional[Dict]:
    """
    Retrieve cached query results.
    Cache is reset on application restart (in-memory) but we persist it.
    """
    _ensure_cache_dir()
    if not os.path.exists(QUERY_CACHE_FILE):
        return None
    try:
        with open(QUERY_CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
        entry = cache.get(query_key)
        if entry:
            # Cache individual queries for 1 hour
            if time.time() - entry.get("cached_at", 0) < 3600:
                return entry.get("result")
        return None
    except Exception:
        return None


def set_cached_query(query_key: str, result: Dict):
    """Cache query results."""
    _ensure_cache_dir()
    try:
        cache = {}
        if os.path.exists(QUERY_CACHE_FILE):
            with open(QUERY_CACHE_FILE, "r", encoding="utf-8") as f:
                cache = json.load(f)
        # Limit cache size to 100 entries
        if len(cache) > 100:
            # Remove oldest entries
            sorted_keys = sorted(cache.keys(), key=lambda k: cache[k].get("cached_at", 0))
            for old_key in sorted_keys[:50]:
                del cache[old_key]
        cache[query_key] = {
            "cached_at": time.time(),
            "result": result
        }
        with open(QUERY_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Error caching query result: {e}")


# ─── Utility ─────────────────────────────────────────────────────────────

def clear_all_caches():
    """Clear all cached data."""
    invalidate_neo4j_cache()
    invalidate_chroma_cache()
    _ensure_cache_dir()
    try:
        if os.path.exists(QUERY_CACHE_FILE):
            os.remove(QUERY_CACHE_FILE)
        print("All caches cleared.")
    except Exception as e:
        print(f"Error clearing query cache: {e}")


def get_cache_stats() -> Dict[str, Any]:
    """Get cache statistics for display."""
    stats = {"neo4j": False, "chroma": False, "query_cache_entries": 0, "cache_dir_size_kb": 0}
    
    if os.path.exists(NEO4J_CACHE_FILE):
        stats["neo4j"] = True
    if os.path.exists(CHROMA_CACHE_FILE):
        stats["chroma"] = True
    if os.path.exists(QUERY_CACHE_FILE):
        try:
            with open(QUERY_CACHE_FILE, "r", encoding="utf-8") as f:
                stats["query_cache_entries"] = len(json.load(f))
        except Exception:
            pass
    
    # Calculate cache directory size
    total_size = 0
    if os.path.exists(CACHE_DIR):
        for dirpath, dirnames, filenames in os.walk(CACHE_DIR):
            for fname in filenames:
                fpath = os.path.join(dirpath, fname)
                try:
                    total_size += os.path.getsize(fpath)
                except Exception:
                    pass
    stats["cache_dir_size_kb"] = round(total_size / 1024, 1)
    
    return stats