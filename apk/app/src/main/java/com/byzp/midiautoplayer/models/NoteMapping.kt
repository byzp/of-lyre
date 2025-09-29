package com.byzp.midiautoplayer.models

data class NoteMapping(
    val note: Int,  // MIDI音高 (0-127)
    val x: Float,   // X坐标 (绝对值或百分比)
    val y: Float,   // Y坐标 (绝对值或百分比)
    val isPercentage: Boolean = true  // 是否使用百分比坐标
)

data class ScreenConfig(
    val screenWidth: Int,
    val screenHeight: Int,
    val mappings: List<NoteMapping>
)