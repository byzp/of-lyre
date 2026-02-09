import mido
import sys
import os


def transpose_midi(input_file, output_file, semitone_shift):
    # 读取MIDI文件
    mid = mido.MidiFile(input_file)
    new_mid = mido.MidiFile()

    for track in mid.tracks:
        new_track = mido.MidiTrack()
        for msg in track:
            # 只处理 note_on 和 note_off
            if msg.type in ["note_on", "note_off"]:
                new_note = msg.note + semitone_shift
                # 限制音符在0~127范围内
                new_note = max(0, min(127, new_note))
                new_msg = msg.copy(note=new_note)
                new_track.append(new_msg)
            else:
                new_track.append(msg)
        new_mid.tracks.append(new_track)

    # 保存移调后的MIDI文件
    new_mid.save(output_file)
    print(f"已保存移调后的MIDI: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("用法: python transpose_midi.py 输入文件.mid 输出文件.mid 偏移量")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    semitone_shift = int(sys.argv[3])

    if not os.path.exists(input_file):
        print(f"错误: 找不到文件 {input_file}")
        sys.exit(1)

    transpose_midi(input_file, output_file, semitone_shift)
