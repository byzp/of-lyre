package com.byzp.midiautoplayer.models

data class MidiNote(
    val pitch: Int,
    val velocity: Int,
    val startTime: Long,
    val duration: Long
)