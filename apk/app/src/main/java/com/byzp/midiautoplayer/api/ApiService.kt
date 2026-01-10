package com.byzp.midiautoplayer.api

import com.google.gson.Gson
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.URL
import java.io.File
import java.io.FileOutputStream

data class MidiInfo(
    val name: str,
    val upload_by: str,
    val duration: Int,
    val file_size: Int,
    val hash: str
)

data class SongListResponse(
    val total_pages: Int,
    val count: Int,
    val midis: List<MidiInfo>
)

class ApiService(private val baseUrl: String = "http://139.196.113.128:1200") {
    private val gson = Gson()

    suspend fun getLatestSongs(page: Int = 1): SongListResponse? = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/latest_songs?page=$page")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            
            if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                val responseText = connection.inputStream.bufferedReader().use { it.readText() }
                gson.fromJson(responseText, SongListResponse::class.java)
            } else {
                null
            }
        } catch (e: Exception) {
            e.printStackTrace()
            null
        }
    }

    suspend fun downloadMidi(hash: String, saveFile: File): Boolean = withContext(Dispatchers.IO) {
        try {
            val url = URL("$baseUrl/download?hash=$hash")
            val connection = url.openConnection() as HttpURLConnection
            connection.requestMethod = "GET"
            
            if (connection.responseCode == HttpURLConnection.HTTP_OK) {
                connection.inputStream.use { input ->
                    FileOutputStream(saveFile).use { output ->
                        input.copyTo(output)
                    }
                }
                true
            } else {
                false
            }
        } catch (e: Exception) {
            e.printStackTrace()
            false
        }
    }
}

typealias str = String
