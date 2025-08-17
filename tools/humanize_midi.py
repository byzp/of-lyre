import mido

def humanize_midi(input_file: str, output_file: str, step: int = 1):
    """
    读取 MIDI 文件，将同时起始的音符错开一点点时间（step ticks）。
    """
    mid = mido.MidiFile(input_file)
    new_mid = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat)

    for track in mid.tracks:
        abs_time = 0
        events = []

        # 1. 转换成 (绝对时间, message)
        for msg in track:
            abs_time += msg.time
            events.append([abs_time, msg])

        # 2. 处理同时刻的 note_on
        i = 0
        while i < len(events):
            t, msg = events[i]
            if msg.type == "note_on" and msg.velocity > 0:
                # 找所有同一时间的 note_on
                j = i + 1
                group = [(i, msg)]
                while j < len(events) and events[j][0] == t and events[j][1].type == "note_on" and events[j][1].velocity > 0:
                    group.append((j, events[j][1]))
                    j += 1
                # 给这一组错开
                for k, (idx, m) in enumerate(sorted(group, key=lambda x: x[1].note)):
                    events[idx][0] = t + step * k
                i = j
            else:
                i += 1

        # 3. 按绝对时间排序，再转回 delta time
        events.sort(key=lambda x: x[0])
        new_track = mido.MidiTrack()
        prev_time = 0
        for t, msg in events:
            delta = t - prev_time
            prev_time = t
            new_track.append(msg.copy(time=delta))

        new_mid.tracks.append(new_track)

    new_mid.save(output_file)


if __name__ == "__main__":
    humanize_midi("sum.mid", "output.mid", step=1)
