import os
import json
from cache_manager import get_neo4j_cache, set_neo4j_cache
# Defer importing optional external libs (neo4j, dotenv) to runtime so module
# can be imported even when those packages are not installed.

# Define helper to check if a string represents a Course ID
def is_course_id(node_id):
    return str(node_id).startswith("CRS-")

class InMemoryGraphFallback:
    def __init__(self, data_paths):
        self.data_paths = data_paths if isinstance(data_paths, list) else [data_paths]
        self.courses = {}  # course_id -> course details
        self.nodes = {}    # node_id -> node properties/labels
        self.edges = []    # list of (source, type, target)
        self.load_data()

    def load_data(self):
        data = []
        for path in self.data_paths:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data.extend(json.load(f))
                    print(f"Loaded {path} for in-memory graph.")
                except Exception as e:
                    print(f"Warning: Could not load {path}: {e}")
            else:
                print(f"Warning: {path} not found for in-memory graph.")
        
        if not data:
            print("Warning: No data loaded for in-memory graph.")
            return
        
        try:
            for item in data:
                course_id = item["course_id"]
                self.courses[course_id] = {
                    "course_id": course_id,
                    "title": item["title"],
                    "url": item["url"],
                    "platform": item["platform"]
                }
                
                # Add course to nodes
                self.nodes[course_id] = {"label": "Course", "id": course_id, "title": item["title"], "url": item["url"]}
                
                # Add target nodes and relationships
                for rel in item.get("relationships", []):
                    src = rel["source"]
                    rel_type = rel["type"]
                    tgt = rel["target"]
                    
                    # Ensure source node exists
                    if src not in self.nodes:
                        if is_course_id(src):
                            self.nodes[src] = {"label": "Course", "id": src}
                        else:
                            self.nodes[src] = {"label": "Skill", "name": src}
                            
                    # Ensure target node exists
                    if tgt not in self.nodes:
                        if is_course_id(tgt):
                            self.nodes[tgt] = {"label": "Course", "id": tgt}
                        else:
                            self.nodes[tgt] = {"label": "Skill", "name": tgt}
                            
                    self.edges.append((src, rel_type, tgt))
            print(f"Successfully loaded in-memory graph with {len(self.courses)} courses and {len(self.edges)} relationships.")
        except Exception as e:
            print(f"Error loading in-memory graph: {e}")

    def query_graph(self, skills):
        # Normalize search skills to lowercase set for fast lookup
        skills_lower = {s.strip().lower() for s in skills if s}
        
        # We want to find:
        # 1. (c:Course)-[r]->(s:Skill) where s in skills (direct match, weight 2.0)
        # 2. (c:Course)-[r1]->(m:Skill)-[r2]->(s:Skill) where s in skills (indirect match, weight 1.0)
        
        course_scores = {} # course_id -> { "score": float, "matches": set }
        
        # Step 1: Direct matches
        for src, rel_type, tgt in self.edges:
            if is_course_id(src) and not is_course_id(tgt):
                # Check direct match
                if tgt.lower() in skills_lower:
                    course_id = src
                    if course_id not in course_scores:
                        course_scores[course_id] = {"score": 0.0, "matches": set()}
                    # Direct match gets 2.0 weight
                    if tgt not in course_scores[course_id]["matches"]:
                        course_scores[course_id]["score"] += 2.0
                        course_scores[course_id]["matches"].add(tgt)
                        
        # Step 2: 2-hop (indirect) matches
        # Find all paths c -> m -> s
        # Map c -> list of m
        c_to_m = {}
        # Map m -> list of s
        m_to_s = {}
        for src, rel_type, tgt in self.edges:
            if is_course_id(src) and not is_course_id(tgt):
                c_to_m.setdefault(src, []).append(tgt)
            elif not is_course_id(src) and not is_course_id(tgt):
                m_to_s.setdefault(src, []).append(tgt)
                
        for course_id, intermediate_skills in c_to_m.items():
            for m in intermediate_skills:
                if m in m_to_s:
                    for s in m_to_s[m]:
                        if s.lower() in skills_lower:
                            if course_id not in course_scores:
                                course_scores[course_id] = {"score": 0.0, "matches": set()}
                            # 2-hop match gets 1.0 weight
                            if s not in course_scores[course_id]["matches"]:
                                course_scores[course_id]["score"] += 1.0
                                course_scores[course_id]["matches"].add(s)
                                
        # Convert to sorted list of results
        results = []
        for course_id, info in course_scores.items():
            course = self.courses.get(course_id)
            if course:
                results.append({
                    "course_id": course_id,
                    "title": course["title"],
                    "url": course["url"],
                    "platform": course["platform"],
                    "score": info["score"],
                    "matched_skills": list(info["matches"])
                })
                
        results.sort(key=lambda x: x["score"], reverse=True)
        return results


class Neo4jGraphManager:
    def __init__(self, uri, username, password):
        self.uri = uri
        self.username = username
        self.password = password
        self.driver = None
        self.connect()

    def connect(self):
        try:
            from neo4j import GraphDatabase

            self.driver = GraphDatabase.driver(self.uri, auth=(self.username, self.password))
            # Verify connectivity
            self.driver.verify_connectivity()
            print("Connected successfully to Neo4j database.")
        except Exception as e:
            self.driver = None
            raise ConnectionError(f"Failed to connect to Neo4j: {e}")

    def close(self):
        if self.driver:
            self.driver.close()

    def populate_db(self, data_paths):
        """Populate Neo4j from one or more data files, merging and deduplicating by course_id."""
        if not self.driver:
            print("Neo4j driver not connected. Cannot populate database.")
            return False
        
        # Normalize to list
        if isinstance(data_paths, str):
            data_paths = [data_paths]
        
        # Load and merge data from all files, deduplicating by course_id
        all_data = []
        seen_ids = set()
        for path in data_paths:
            if not os.path.exists(path):
                print(f"Warning: {path} not found for Neo4j population.")
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    file_data = json.load(f)
                for item in file_data:
                    cid = item.get("course_id")
                    if cid and cid not in seen_ids:
                        seen_ids.add(cid)
                        all_data.append(item)
            except Exception as e:
                print(f"Error loading {path}: {e}")
        
        if not all_data:
            print("Error: No valid data loaded for Neo4j.")
            return False
        
        # Cache key based on primary file + count
        primary_path = data_paths[0]
        cached = get_neo4j_cache(primary_path)
        if cached is not None and cached.get("populated", False) and cached.get("course_count", 0) == len(all_data):
            print(f"Neo4j cache valid ({len(all_data)} courses) — skipping population.")
            return True

        try:
            with self.driver.session() as session:
                # Clear database
                session.run("MATCH (n) DETACH DELETE n")
                # Clear database
                session.run("MATCH (n) DETACH DELETE n")
                
                # First pass: create all Course nodes
                for item in all_data:
                    session.run(
                        """
                        MERGE (c:Course {id: $course_id})
                        SET c.title = $title, c.url = $url, c.platform = $platform
                        """,
                        course_id=item["course_id"],
                        title=item["title"],
                        url=item["url"],
                        platform=item["platform"]
                    )
                
                # Second pass: create all target nodes and relationships
                for item in all_data:
                    for rel in item.get("relationships", []):
                        src = rel["source"]
                        rel_type = rel["type"]
                        tgt = rel["target"]
                        
                        # Define labels/properties based on node type
                        src_query = "MERGE (src:Course {id: $src})" if is_course_id(src) else "MERGE (src:Skill {name: $src})"
                        tgt_query = "MERGE (tgt:Course {id: $tgt})" if is_course_id(tgt) else "MERGE (tgt:Skill {name: $tgt})"
                        
                        # Match and merge relationship (interpolating safe relationship type)
                        rel_query = f"""
                        MATCH (src), (tgt)
                        WHERE (src:Course AND src.id = $src OR src:Skill AND src.name = $src)
                          AND (tgt:Course AND tgt.id = $tgt OR tgt:Skill AND tgt.name = $tgt)
                        MERGE (src)-[:{rel_type}]->(tgt)
                        """
                        
                        # Execute transaction
                        session.run(src_query, src=src)
                        session.run(tgt_query, tgt=tgt)
                        session.run(rel_query, src=src, tgt=tgt)
                        
            print(f"Neo4j database successfully populated with {len(all_data)} courses from {len(data_paths)} file(s).")
            
            # Save cache state
            set_neo4j_cache({"populated": True, "course_count": len(all_data)}, primary_path)
            return True
        except Exception as e:
            print(f"Error populating Neo4j database: {e}")
            return False

    def query_graph(self, skills):
        if not self.driver:
            raise ConnectionError("Neo4j driver is not connected.")

        skills_lower = [s.strip().lower() for s in skills if s]
        if not skills_lower:
            return []

        query = """
        CALL () {
          // Direct matches
          MATCH (c:Course)-[:TEACHES_DOMAIN|TEACHES_LANGUAGE|TEACHES_FRAMEWORK|TEACHES_DATABASE|TEACHES_RUNTIME|TEACHES_CLOUD_SERVICE|TEACHES_TOOL|TEACHES_OS|TEACHES_ENGINE|TEACHES_PROTOCOLS|TEACHES_HARDWARE|TEACHES_HARDWARE_ARCH|TEACHES_STORAGE|HOSTED_ON]->(s:Skill)
          WHERE tolower(s.name) IN $skills_lower
          RETURN c, s.name AS skill_name, 2.0 AS match_score

          UNION ALL

          // Indirect matches
          MATCH (c:Course)-[:TEACHES_DOMAIN|TEACHES_LANGUAGE|TEACHES_FRAMEWORK|TEACHES_DATABASE|TEACHES_RUNTIME|TEACHES_CLOUD_SERVICE|TEACHES_TOOL|TEACHES_OS|TEACHES_ENGINE|TEACHES_PROTOCOLS|TEACHES_HARDWARE|TEACHES_HARDWARE_ARCH|TEACHES_STORAGE|HOSTED_ON]->(m:Skill)-[:RUNS_ON|BUILT_ON|DEPENDS_ON|PRIMARY_LANGUAGE|CATEGORY|INTERFACES_WITH|NATIVE_LANGUAGE|NATIVE_BINDINGS|COMPANION_TO|ABSTRACTS|TARGETS_COMPILATION|RUNS_ON_TOP_OF|CONSUMES_FROM|STORES_ARTIFACTS_IN]->(s:Skill)
          WHERE tolower(s.name) IN $skills_lower
          RETURN c, s.name AS skill_name, 1.0 AS match_score
        }
        WITH c, skill_name, max(match_score) AS final_skill_score
        RETURN c.id AS course_id, c.title AS title, c.url AS url, c.platform AS platform, sum(final_skill_score) AS score, collect(skill_name) AS matched_skills
        ORDER BY score DESC
        """
        
        try:
            with self.driver.session() as session:
                result = session.run(query, skills_lower=skills_lower)
                records = []
                for record in result:
                    records.append({
                        "course_id": record["course_id"],
                        "title": record["title"],
                        "url": record["url"],
                        "platform": record["platform"],
                        "score": record["score"],
                        "matched_skills": list(set(record["matched_skills"]))
                    })
                return records
        except Exception as e:
            print(f"Error querying Neo4j: {e}")
            return []

    # ─── Graph Visualization Helpers ────────────────────────────────────
    
    def get_graph_stats(self):
        """Get graph statistics for visualization."""
        if not self.driver:
            return None
        try:
            with self.driver.session() as session:
                # Course count
                course_count = session.run("MATCH (c:Course) RETURN count(c) AS count").single()["count"]
                # Skill count
                skill_count = session.run("MATCH (s:Skill) RETURN count(s) AS count").single()["count"]
                # Relationship count
                rel_count = session.run("MATCH ()-[r]->() RETURN count(r) AS count").single()["count"]
                # Top skills by connection count
                top_skills = session.run(
                    "MATCH (s:Skill)<-[r]-() RETURN s.name AS skill, count(r) AS connections ORDER BY connections DESC LIMIT 20"
                ).data()
                # Top courses by connection count
                top_courses = session.run(
                    "MATCH (c:Course)-[r]->() RETURN c.title AS title, count(r) AS connections ORDER BY connections DESC LIMIT 10"
                ).data()
                # Relationship type distribution
                rel_types = session.run(
                    "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS count ORDER BY count DESC"
                ).data()
                
                return {
                    "course_count": course_count,
                    "skill_count": skill_count,
                    "relationship_count": rel_count,
                    "top_skills": top_skills,
                    "top_courses": top_courses,
                    "relationship_types": rel_types
                }
        except Exception as e:
            print(f"Error getting graph stats: {e}")
            return None

    def get_graph_pyvis(self, max_nodes=2000):
        """Generate a PyVis graph visualization from Neo4j data."""
        if not self.driver:
            return None
        try:
            from pyvis.network import Network
            with self.driver.session() as session:
                # Get nodes and relationships
                nodes_result = session.run(
                    f"MATCH (n) RETURN n.id AS id, n.name AS name, n.title AS title, labels(n) AS labels LIMIT {max_nodes}"
                ).data()
                
                rels_result = session.run(
                    f"MATCH (a)-[r]->(b) RETURN a.id AS src_id, a.name AS src_name, type(r) AS rel_type, b.id AS tgt_id, b.name AS tgt_name LIMIT {max_nodes * 2}"
                ).data()
                
            net = Network(height='600px', width='100%', bgcolor='#1a1a2e', font_color='white')
            # Use default barnes_hut physics which is most stable
            net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=250, spring_strength=0.001, damping=0.09)
            
            node_ids = {}
            
            for node in nodes_result:
                node_id = node.get("id") or node.get("name", "")
                if not node_id:
                    continue
                label = node.get("labels", ["Unknown"])[0] if node.get("labels") else "Unknown"
                display_name = node.get("title") or node.get("name") or node_id
                
                node_ids[node_id] = node_id
                
                if label == "Course":
                    net.add_node(node_id, label=display_name, title=f"Course: {display_name}", color='#7000FF', size=25)
                else:
                    net.add_node(node_id, label=display_name, title=f"Skill: {display_name}", color='#00CC99', size=15)
            
            for rel in rels_result:
                src = rel.get("src_id") or rel.get("src_name", "")
                tgt = rel.get("tgt_id") or rel.get("tgt_name", "")
                if src in node_ids and tgt in node_ids:
                    rel_label = rel.get("rel_type", "RELATED_TO").replace("_", " ")
                    net.add_edge(src, tgt, title=rel_label, color='#F87272')
            
            return net.generate_html()
        except Exception as e:
            print(f"Error generating pyvis graph: {e}")
            return f"<div style='color:red'>Error: {str(e)}</div>"


# Factory function to get active graph provider
_GRAPH_PROVIDER_CACHE = None


def get_graph_provider(data_path="Data&relation.txt"):
    """Return a cached graph provider (Neo4j manager or in-memory fallback).

    This avoids re-initializing and re-populating Neo4j on every call which can
    cause surprising behavior where the DB appears empty until a second run.
    """
    global _GRAPH_PROVIDER_CACHE

    if _GRAPH_PROVIDER_CACHE is not None:
        return _GRAPH_PROVIDER_CACHE

    # Try to load environment variables if python-dotenv is available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass

    uri = os.getenv("NEO4J_URI")
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv("NEO4J_PASSWORD")

    # Try connecting to Neo4j if env credentials present
    if uri and username and password:
        try:
            print("Attempting to connect to Neo4j using env credentials...")
            manager = Neo4jGraphManager(uri, username, password)
            # Populate/initialize database with BOTH data files for consistency
            try:
                data_paths = [data_path, "course_skill_graph_50_samples.json", "course_skill_graph_samples.json"]
                manager.populate_db(data_paths)
            except Exception:
                pass

            _GRAPH_PROVIDER_CACHE = (manager, "Neo4j")
            return _GRAPH_PROVIDER_CACHE
        except Exception as e:
            print(f"Neo4j connection attempt failed: {e}. Falling back to in-memory graph.")

    # Fallback to local in-memory graph database using multiple data files
    data_paths = [data_path, "course_skill_graph_50_samples.json", "course_skill_graph_samples.json"]
    print(f"Using local in-memory graph fallback. Data: {data_paths}")
    fallback = InMemoryGraphFallback(data_paths)
    _GRAPH_PROVIDER_CACHE = (fallback, "In-Memory Fallback")
    return _GRAPH_PROVIDER_CACHE


def get_graph_visualization_data():
    """Get graph visualization data from the active provider."""
    provider, provider_name = get_graph_provider()
    if provider_name == "Neo4j":
        return provider.get_graph_stats(), provider.get_graph_pyvis()
    return None, None