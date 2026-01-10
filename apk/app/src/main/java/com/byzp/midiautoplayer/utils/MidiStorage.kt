package com.byzp.midiautoplayer.utils

import android.content.Context
import java.io.File

class MidiStorage(private val context: Context) {
    private val midiDir: File by lazy {
        val dir = File(context.getExternalFilesDir(null), "midis")
        if (!dir.exists()) dir.mkdirs()
        dir
    }

    fun saveMidi(name: String, bytes: ByteArray): File {
        val file = File(midiDir, name)
        file.writeBytes(bytes)
        return file
    }

    fun getSavedMidis(): List<File> {
        return midiDir.listFiles()?.filter { it.extension.lowercase() == "mid" || it.extension.lowercase() == "midi" } ?: emptyList()
    }

    fun getMidiFile(name: String): File {
        return File(midiDir, name)
    }
}
