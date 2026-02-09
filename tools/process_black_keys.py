import mido
import sys

# 黑键集合 (C#, D#, F#, G#, A#)
BLACK_KEYS = {1, 3, 6, 8, 10}


def process_midi(input_file, output_file, mode="up"):
    mid = mido.MidiFile(input_file)
    new_mid = mido.MidiFile(type=mid.type, ticks_per_beat=mid.ticks_per_beat)

    for track in mid.tracks:
        new_track = mido.MidiTrack()
        for msg in track:
            if msg.type in ["note_on", "note_off"]:
                if msg.note % 12 in BLACK_KEYS:
                    if mode == "up" and msg.note < 127:
                        msg = msg.copy(note=msg.note + 1)
                    elif mode == "down" and msg.note > 0:
                        msg = msg.copy(note=msg.note - 1)
                    elif mode == "remove":
                        continue
            # 保证包括 MetaMessage 在内的所有事件都写回
            new_track.append(msg)
        new_mid.tracks.append(new_track)

    new_mid.save(output_file)
    print(f"处理完成，结果已保存至 {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print(
            "用法: python process_black_keys.py 输入.mid 输出.mid 模式(up/down/remove)"
        )
    else:
        _, infile, outfile, mode = sys.argv
        process_midi(infile, outfile, mode)
