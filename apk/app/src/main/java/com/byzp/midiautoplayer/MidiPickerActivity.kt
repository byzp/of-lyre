package com.byzp.midiautoplayer

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity

/**
 * 一个透明的Activity，用于处理文件选择，并将结果URI传递给FloatingWindowService。
 */
class MidiPickerActivity : AppCompatActivity() {

    private val filePickerLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? ->
        // 当用户选择文件（或取消）后，这里会被调用
        uri?.let {
            // 将选择的URI通过Intent发送给Service
            val serviceIntent = Intent(this, FloatingWindowService::class.java).apply {
                action = ACTION_MIDI_FILE_SELECTED
                data = it
            }
            startService(serviceIntent)
        }
        // 无论用户是否选择了文件，都关闭这个透明的Activity
        finish()
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        // **OpenDocument 的 launch 方法需要一个MIME类型数组**
        filePickerLauncher.launch(arrayOf("*/*"))
    }

    companion object {
        const val ACTION_MIDI_FILE_SELECTED = "com.byzp.midiautoplayer.MIDI_FILE_SELECTED"
    }
}