package com.byzp.midiautoplayer

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.byzp.midiautoplayer.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        checkPermissions()
        setupButtons()
    }

    private fun checkPermissions() {
        // 检查悬浮窗权限
        if (!Settings.canDrawOverlays(this)) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                android.net.Uri.parse("package:$packageName")
            )
            startActivityForResult(intent, OVERLAY_PERMISSION_REQUEST_CODE)
        }
    }

    private fun setupButtons() {
        // 启动悬浮窗
        binding.btnStartFloating.setOnClickListener {
            if (Settings.canDrawOverlays(this)) {
                startFloatingWindowService()
                //openFilePickerForMidi()
            } else {
                Toast.makeText(this, "请先授予悬浮窗权限", Toast.LENGTH_SHORT).show()
            }
        }

        // 停止服务
        binding.btnStopFloating.setOnClickListener {
            stopService(Intent(this, FloatingWindowService::class.java))
        }

        // 一个单独按钮仅用于选文件
        // binding.btnPickFile.setOnClickListener { openFilePickerForMidi() }
    }

    private fun startFloatingWindowService() {
        val intent = Intent(this, FloatingWindowService::class.java)
        startService(intent)
    }

    companion object {
        private const val OVERLAY_PERMISSION_REQUEST_CODE = 100
        const val ACTION_MIDI_FILE_SELECTED = "com.byzp.midiautoplayer.MIDI_FILE_SELECTED"
    }
}
