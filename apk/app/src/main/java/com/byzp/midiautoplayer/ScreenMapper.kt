package com.byzp.midiautoplayer

import android.content.Context
import android.util.DisplayMetrics
import android.view.WindowManager
import com.byzp.midiautoplayer.models.MidiNote
import com.byzp.midiautoplayer.models.NoteMapping
import com.byzp.midiautoplayer.models.ScreenConfig
import com.google.gson.Gson
import com.google.gson.reflect.TypeToken
import java.io.InputStreamReader

class ScreenMapper(private val context: Context) {
    private val screenWidth: Int
    private val screenHeight: Int
    private val noteMappings: Map<Int, NoteMapping>
    
    init {
        val displayMetrics = DisplayMetrics()
        val windowManager = context.getSystemService(Context.WINDOW_SERVICE) as WindowManager
        windowManager.defaultDisplay.getMetrics(displayMetrics)
        
        screenWidth = displayMetrics.widthPixels
        screenHeight = displayMetrics.heightPixels
        
        noteMappings = loadMappings()
    }
    
    private fun loadMappings(): Map<Int, NoteMapping> {
        return try {
            val inputStream = context.resources.openRawResource(R.raw.note_mappings)
            val reader = InputStreamReader(inputStream)
            
            val type = object : TypeToken<ScreenConfig>() {}.type
            val config: ScreenConfig = Gson().fromJson(reader, type)
            
            // 根据屏幕分辨率选择最合适的配置
            val mappings = if (config.screenWidth == screenWidth && 
                               config.screenHeight == screenHeight) {
                config.mappings
            } else {
                // 如果没有完全匹配，进行缩放
                config.mappings.map { mapping ->
                    if (mapping.isPercentage) {
                        mapping
                    } else {
                        NoteMapping(
                            note = mapping.note,
                            x = mapping.x * screenWidth / config.screenWidth,
                            y = mapping.y * screenHeight / config.screenHeight,
                            isPercentage = false
                        )
                    }
                }
            }
            
            mappings.associateBy { it.note }
        } catch (e: Exception) {
            e.printStackTrace()
            emptyMap()
        }
    }
    
    fun getScreenPoint(note: Int): Pair<Float, Float>? {
        val mapping = noteMappings[note] ?: return null
        
        return if (mapping.isPercentage) {
            Pair(
                mapping.x * screenWidth / 100f,
                mapping.y * screenHeight / 100f
            )
        } else {
            Pair(mapping.x, mapping.y)
        }
    }
}