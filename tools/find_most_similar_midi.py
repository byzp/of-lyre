import os
import mido
import numpy as np
from mido import MidiFile


# 计算MIDI文件的音符序列特征
def extract_notes(midi_file):
    notes = []
    for msg in midi_file:
        if msg.type == "note_on" or msg.type == "note_off":
            notes.append((msg.note, msg.time))
    return notes


# 计算两个音符序列之间的相似度（简化版，使用欧几里得距离）
def calculate_similarity(notes1, notes2):
    # 只使用音符的数字值作为特征进行比较
    notes1 = np.array([note[0] for note in notes1])
    notes2 = np.array([note[0] for note in notes2])

    # 计算欧几里得距离（或其他相似度度量）
    distance = np.linalg.norm(notes1 - notes2)
    similarity = 1 / (1 + distance)  # 相似度越高，距离越小
    return similarity


# 主函数：读取文件并比对相似度
def find_most_similar_midi(target_midi_path, folder_path):
    # 读取目标MIDI文件
    target_midi = MidiFile(target_midi_path)
    target_notes = extract_notes(target_midi)

    max_similarity = 0
    most_similar_file = None

    # 遍历文件夹中的所有MIDI文件进行比对
    for file_name in os.listdir(folder_path):
        if file_name.endswith(".mid"):
            file_path = os.path.join(folder_path, file_name)
            midi_file = MidiFile(file_path)
            notes = extract_notes(midi_file)

            similarity = calculate_similarity(target_notes, notes)

            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_file = file_path

    return most_similar_file, max_similarity


# 示例：指定目标MIDI文件和文件夹路径
target_midi_path = "path_to_target.mid"
folder_path = "path_to_folder_with_midi_files"

most_similar_midi, similarity = find_most_similar_midi(target_midi_path, folder_path)
print(f"最相似的MIDI文件是：{most_similar_midi}，相似度为：{similarity:.4f}")
