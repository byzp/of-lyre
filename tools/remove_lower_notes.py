import pretty_midi

def remove_lower_notes(input_file, output_file):
    # 读取 MIDI 文件
    midi_data = pretty_midi.PrettyMIDI(input_file)

    for instrument in midi_data.instruments:
        # 存储按 (start, end) 分组的音符
        grouped_notes = {}
        for note in instrument.notes:
            key = (round(note.start, 5), round(note.end, 5))  # 用起止时间做key（避免浮点误差）
            grouped_notes.setdefault(key, []).append(note)

        new_notes = []
        for key, notes in grouped_notes.items():
            if len(notes) == 1:
                # 只有一个音符，直接保留
                new_notes.append(notes[0])
            else:
                # 多个音符，保留最高音
                highest_note = max(notes, key=lambda n: n.pitch)
                new_notes.append(highest_note)

        # 更新乐器里的音符
        instrument.notes = sorted(new_notes, key=lambda n: n.start)

    # 保存处理后的 MIDI
    midi_data.write(output_file)


if __name__ == "__main__":
    input_midi = input("输入需要处理的文件的路径: ")
    output_midi = "output.mid"
    remove_lower_notes(input_midi, output_midi)
    print(f"处理完成，结果已保存到 {output_midi}")
