package com.byzp.midiautoplayer

import android.content.Context
import android.net.Uri
import android.util.Log
import com.byzp.midiautoplayer.models.MidiNote
import com.byzp.midiautoplayer.models.NoteMapping
import com.byzp.midiautoplayer.models.ScreenConfig
import com.google.gson.Gson
import com.leff.midi.MidiFile
import com.leff.midi.event.NoteOff
import com.leff.midi.event.NoteOn
import java.io.InputStream
import java.io.InputStreamReader

class MidiParser(private val context: Context) {
    var parsedNotes: List<MidiNote> = emptyList()
    private val supportedNotes: Set<Int> by lazy { loadSupportedNotes() }

    private fun loadSupportedNotes(): Set<Int> {
        return try {
            val inputStream = context.resources.openRawResource(R.raw.note_mappings)
            InputStreamReader(inputStream).use { reader ->
                val screenConfig = Gson().fromJson(reader, ScreenConfig::class.java)
                screenConfig.mappings.map { it.note }.toSet()
            }
        } catch (e: Exception) {
            Log.e("MidiParser", "Failed to load supported notes", e)
            emptySet()
        }
    }

fun parseMidiFile(
    uri: Uri,
    releaseGapTicks: Long = 1L,
    minNoteDurationTicks: Long = 0L
): List<MidiNote> {
    val notes = mutableListOf<MidiNote>()
    try {
        context.contentResolver.openInputStream(uri)?.use { inputStream ->
            val midiFile = MidiFile(inputStream)

            val ppq = try {
                midiFile.javaClass.getMethod("getResolution").invoke(midiFile) as Int
            } catch (e: Exception) {
                480 // default PPQ
            }

            var currentTempo = 500000 // default: 120 BPM (500000 microseconds per quarter note)
            val tempoChanges = mutableListOf<Pair<Long, Int>>()
            tempoChanges.add(0L to currentTempo)

            // Collect tempo changes first
            midiFile.tracks.forEach { track ->
                track.events.forEach { event ->
                    if (event.javaClass.simpleName == "Tempo") {
                        try {
                            val mpqn = event.javaClass.getMethod("getMpqn").invoke(event) as Int
                            tempoChanges.add(event.tick to mpqn)
                        } catch (e: Exception) {
                            try {
                                val bpm = event.javaClass.getMethod("getBpm").invoke(event) as Float
                                tempoChanges.add(event.tick to (60000000 / bpm).toInt())
                            } catch (_: Exception) {}
                        }
                    }
                }
            }
            tempoChanges.sortBy { it.first }

            // Convert tick to milliseconds (uses tempoChanges & ppq)
            fun tickToMs(tick: Long): Long {
                var ms = 0.0
                var lastTick = 0L
                var lastTempo = 500000

                for ((tempoTick, tempo) in tempoChanges) {
                    if (tempoTick > tick) break
                    val tickDiff = tempoTick - lastTick
                    ms += (tickDiff * lastTempo) / (ppq * 1000.0)
                    lastTick = tempoTick
                    lastTempo = tempo
                }

                val remainingTicks = tick - lastTick
                ms += (remainingTicks * lastTempo) / (ppq * 1000.0)

                return ms.toLong()
            }

            val allEvents = midiFile.tracks.flatMap { it.events }.sortedBy { it.tick }
            val activeNotes = mutableMapOf<Pair<Int, Int>, Pair<Long, Int>>()

            fun safeGetIntViaJavaReflection(obj: Any?, candidateNames: Array<String>): Int? {
                if (obj == null) return null
                val cls = obj.javaClass
                for (name in candidateNames) {
                    val tryMethodNames = listOf(name, "get${name.capitalize()}", "is${name.capitalize()}")
                    for (mName in tryMethodNames) {
                        try {
                            val m = cls.getMethod(mName)
                            val v = m.invoke(obj)
                            if (v is Number) return v.toInt()
                        } catch (_: Exception) {}
                    }
                    try {
                        val field = cls.getDeclaredField(name)
                        field.isAccessible = true
                        val v = field.get(obj)
                        if (v is Number) return v.toInt()
                    } catch (_: Exception) {}
                }
                return null
            }

            for (event in allEvents) {
                val tick = event.tick
                when (event) {
                    is NoteOn -> {
                        val pitch = event.noteValue
                        val velocity = event.velocity
                        val channel = safeGetIntViaJavaReflection(event, arrayOf("channel")) ?: 0
                        val key = Pair(channel, pitch)

                        if (velocity > 0) {
                            // If another note with same key is active, close it (releaseGapTicks applied)
                            activeNotes.remove(key)?.let { (prevStart, prevVel) ->
                                val endMs = tickToMs((tick - releaseGapTicks).coerceAtLeast(prevStart))
                                val startMs = tickToMs(prevStart)
                                var duration = (endMs - startMs).coerceAtLeast(0L)
                                if (minNoteDurationTicks > 0L) duration = duration.coerceAtLeast(minNoteDurationTicks)
                                notes.add(MidiNote(pitch = pitch, velocity = prevVel, startTime = startMs, duration = duration))
                            }

                            if (supportedNotes.contains(pitch)) {
                                activeNotes[key] = Pair(tick, velocity)
                            }
                        } else {
                            activeNotes.remove(key)?.let { (startTick, startVel) ->
                                val startMs = tickToMs(startTick)
                                val endMs = tickToMs(tick)
                                var duration = (endMs - startMs).coerceAtLeast(0L)
                                if (minNoteDurationTicks > 0L) duration = duration.coerceAtLeast(minNoteDurationTicks)
                                notes.add(MidiNote(pitch = pitch, velocity = startVel, startTime = startMs, duration = duration))
                            }
                        }
                    }

                    is NoteOff -> {
                        val pitch = event.noteValue
                        val channel = safeGetIntViaJavaReflection(event, arrayOf("channel")) ?: 0
                        val key = Pair(channel, pitch)
                        activeNotes.remove(key)?.let { (startTick, startVel) ->
                            val startMs = tickToMs(startTick)
                            val endMs = tickToMs(tick)
                            var duration = (endMs - startMs).coerceAtLeast(0L)
                            if (minNoteDurationTicks > 0L) duration = duration.coerceAtLeast(minNoteDurationTicks)
                            notes.add(MidiNote(pitch = pitch, velocity = startVel, startTime = startMs, duration = duration))
                        }
                    }
                    else -> {}
                }
            }

            if (activeNotes.isNotEmpty()) {
                val maxTick = allEvents.maxOfOrNull { it.tick } ?: 0L
                val fileEndMs = tickToMs(maxTick)
                activeNotes.forEach { (key, noteData) ->
                    val (startTick, velocity) = noteData
                    val startMs = tickToMs(startTick)
                    var duration = (fileEndMs - startMs).coerceAtLeast(0L)
                    if (minNoteDurationTicks > 0L) duration = duration.coerceAtLeast(minNoteDurationTicks)
                    notes.add(MidiNote(pitch = key.second, velocity = velocity, startTime = startMs, duration = duration))
                }
            }

            // Shift all notes so first note starts at 0
            val sortedNotes = notes.sortedBy { it.startTime }
            val firstNoteStart = sortedNotes.firstOrNull()?.startTime ?: 0L
            val shiftedNotes = sortedNotes.map { note ->
                note.copy(startTime = note.startTime - firstNoteStart)
            }

            // Group by startTime
            val groups = shiftedNotes.groupBy { it.startTime }.toSortedMap()

            if (groups.isEmpty()) {
                this.parsedNotes = emptyList()
                return parsedNotes
            }

            // Convert preferred release gap (ticks) to ms using tickToMs
            val preferredGapMs = try {
                tickToMs(releaseGapTicks)
            } catch (e: Exception) {
                1L
            }.coerceAtLeast(0L)

            val minDurationMs = 1L // 每个音符至少要有 1 ms 的时值

            val startTimes = groups.keys.toMutableList()
            val groupNotesList = startTimes.map { st -> groups[st]!!.toMutableList() }.toMutableList()
            val adjustedStarts = startTimes.toMutableList()

            for (i in 0 until adjustedStarts.size) {
                val curStart = adjustedStarts[i]
                val curGroupNotes = groupNotesList[i]

                val nextIndex = i + 1
                val nextStart = if (nextIndex < adjustedStarts.size) adjustedStarts[nextIndex] else Long.MAX_VALUE

                val originalDurations = curGroupNotes.map { it.duration }

                var allowedEnd = if (nextStart == Long.MAX_VALUE) Long.MAX_VALUE else (nextStart - preferredGapMs)

                if (allowedEnd <= curStart && nextIndex < adjustedStarts.size) {
                    // 尝试把 gap 缩为 0
                    allowedEnd = nextStart
                }

                var maxAllowedDurationForGroup = if (allowedEnd == Long.MAX_VALUE) {
                    originalDurations.maxOrNull() ?: minDurationMs
                } else {
                    (allowedEnd - curStart).coerceAtLeast(0L)
                }

                if (maxAllowedDurationForGroup < minDurationMs && nextIndex < adjustedStarts.size) {
                    val neededEnd = curStart + minDurationMs
                    val shift = neededEnd - allowedEnd
                    if (shift > 0) {
                        for (k in nextIndex until adjustedStarts.size) {
                            adjustedStarts[k] = adjustedStarts[k] + shift
                        }
                        val newNextStart = adjustedStarts[nextIndex]
                        allowedEnd = newNextStart - preferredGapMs
                        if (allowedEnd <= curStart) {
                            allowedEnd = newNextStart
                        }
                        maxAllowedDurationForGroup = (allowedEnd - curStart).coerceAtLeast(0L)
                    }
                }

                val finalDurForGroup = if (maxAllowedDurationForGroup <= 0L) {
                    val assigned = minDurationMs
                    if (nextIndex < adjustedStarts.size) {
                        val neededShift = (curStart + assigned) - adjustedStarts[nextIndex]
                        if (neededShift > 0) {
                            for (k in nextIndex until adjustedStarts.size) {
                                adjustedStarts[k] = adjustedStarts[k] + neededShift
                            }
                        }
                    }
                    assigned
                } else {
                    maxAllowedDurationForGroup.coerceAtLeast(minDurationMs)
                }

                for (nIdx in curGroupNotes.indices) {
                    val n = curGroupNotes[nIdx]
                    val orig = n.duration
                    val newDur = orig.coerceAtMost(finalDurForGroup).coerceAtLeast(minDurationMs)
                    curGroupNotes[nIdx] = n.copy(duration = newDur)
                }
            }

            val nonOverlapping = mutableListOf<MidiNote>()
            for (i in adjustedStarts.indices) {
                val st = adjustedStarts[i]
                val group = groupNotesList[i]
                for (n in group) {
                    nonOverlapping.add(n.copy(startTime = st))
                }
            }

            val finalList = nonOverlapping.sortedWith(compareBy<MidiNote> { it.startTime }.thenBy { it.pitch })
                .map { note ->
                    if (note.duration <= 0L) note.copy(duration = minDurationMs) else note
                }

            this.parsedNotes = finalList

            // 结束 inputStream.use 的作用域（此处所有需要 tickToMs 的代码都在其内）
        } ?: run {
            Log.e("MidiParser", "Unable to open InputStream for uri: $uri")
            this.parsedNotes = emptyList()
            return parsedNotes
        }
    } catch (e: Exception) {
        Log.e("MidiParser", "Error parsing MIDI file", e)
        this.parsedNotes = emptyList()
        return parsedNotes
    }

    // 最终 logging & 返回（parsedNotes 已在上面被设置）
    this.parsedNotes.forEachIndexed { index, note ->
        val endTime = note.startTime + note.duration
        //Log.d("MidiParser", "Note[$index] pitch=${note.pitch} vel=${note.velocity} start=${note.startTime} duration=${note.duration} end=$endTime")
    }

    Log.d("MidiParser", "Successfully parsed ${this.parsedNotes.size} notes.")
    return this.parsedNotes
}


}
