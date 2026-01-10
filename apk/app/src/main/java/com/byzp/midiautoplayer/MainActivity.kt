package com.byzp.midiautoplayer

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import com.byzp.midiautoplayer.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        checkOverlayPermission()
        checkAccessibilityPermission()
        setupButtons()
    }

    private fun checkOverlayPermission() {
        if (!Settings.canDrawOverlays(this)) {
            val intent = Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:$packageName")
            )
            startActivityForResult(intent, OVERLAY_PERMISSION_REQUEST_CODE)
        }
    }

    private fun checkAccessibilityPermission() {
        if (!isAccessibilityServiceEnabled()) {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
            startActivity(intent)
        }
    }

    private fun isAccessibilityServiceEnabled(): Boolean {
        val enabledServices = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false

        return enabledServices.contains(packageName)
    }

    private fun setupButtons() {
        binding.btnStartFloating.setOnClickListener {
            if (Settings.canDrawOverlays(this)) {
                startFloatingWindowService()
            } else {
                Toast.makeText(this, "请先授予悬浮窗权限", Toast.LENGTH_SHORT).show()
            }
        }

        binding.btnStopFloating.setOnClickListener {
            stopService(Intent(this, FloatingWindowService::class.java))
        }
    }

    private fun startFloatingWindowService() {
        val intent = Intent(this, FloatingWindowService::class.java)
        startService(intent)
    }

    companion object {
        private const val OVERLAY_PERMISSION_REQUEST_CODE = 100
        const val ACTION_MIDI_FILE_SELECTED =
            "com.byzp.midiautoplayer.MIDI_FILE_SELECTED"
    }
}
