import json
from difflib import SequenceMatcher

def get_similar_string_ratio(a: str, b: str) -> float:
    """计算两个字符串的相似度比率"""
    return SequenceMatcher(None, a, b).ratio()

def find_most_similar_file_hash(json_data: dict, query_filename: str, threshold: float = 0.6) -> str | None:
    """
    在解析后的JSON数据中, 查找与查询文件名最相似的文件, 并返回其哈希值。

    Args:
        json_data (dict): 从JSON文件加载的字典数据。
        query_filename (str): 用于搜索和匹配的文件名字符串。
        threshold (float): 相似度阈值, 只有相似度高于此值的才被认为是有效匹配。
                           取值范围为 0.0 到 1.0。默认为 0.6。

    Returns:
        str | None: 如果找到足够相似的文件, 则返回该文件的哈希值 (字符串); 
                    否则返回 None。
    """
    if not json_data or not query_filename:
        return None

    best_match_hash = None
    highest_similarity_score = -1.0

    # 将查询字符串转换为小写以进行不区分大小写的比较
    query_lower = query_filename.lower()

    # 遍历JSON数据中的每一个文件条目
    for file_hash, file_info in json_data.items():
        # 确保文件条目中有 'name' 键
        original_filename = file_info.get("name")
        if not original_filename:
            continue
        
        # 将原始文件名也转换为小写
        filename_lower = original_filename.lower()
        
        # 计算查询文件名与当前文件名的相似度
        similarity_score = get_similar_string_ratio(query_lower, filename_lower)
        
        # 如果当前文件的相似度是至今为止最高的，则记录下来
        if similarity_score > highest_similarity_score:
            highest_similarity_score = similarity_score
            best_match_hash = file_hash
    
    # 循环结束后，检查最高相似度是否达到了我们设定的阈值
    if highest_similarity_score >= threshold:
        return best_match_hash
    else:
        # 如果最高分也未达到阈值, 说明差异过大, 返回空
        return None

