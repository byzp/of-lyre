import json
import os
import json
from difflib import SequenceMatcher

data=None

def get_similar_string_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()

def find_most_similar_file_hash(query_filename: str, json_data: dict=None, threshold: float = 0.6) -> str | None:
    if not query_filename:
        return None
    
    if json_data is None:
        global data
        json_data = data
    
    best_match_hash = None
    highest_similarity_score = -1.0

    query_lower = query_filename.lower()

    for file_hash, file_info in json_data.items():
        original_filename = file_info.get("name")
        if not original_filename:
            continue
        
        filename_lower = original_filename.lower()
        
        fname = filename_lower.split(".")[0]
        
        similarity_score = get_similar_string_ratio(query_lower, fname)
        
        if similarity_score > highest_similarity_score:
            highest_similarity_score = similarity_score
            best_match_hash = file_hash
    
    if highest_similarity_score >= threshold:
        return best_match_hash
    else:
        return None

db_file_path = "songs.json"
def load_database():
    if os.path.exists(db_file_path):
        with open(db_file_path, "r") as f:
            return json.load(f)
    return {}
data=load_database()