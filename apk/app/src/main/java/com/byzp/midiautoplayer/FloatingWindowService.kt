package com.byzp.midiautoplayer

import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.Toast
import com.byzp.midiautoplayer.models.*
import kotlinx.coroutines.*
import android.util.Log
import kotlin.coroutines.resume
import kotlin.coroutines.suspendCoroutine
import java.util.concurrent.atomic.AtomicBoolean
import android.os.SystemClock
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext



class FloatingWindowService : Service() {
    private lateinit var windowManager: WindowManager
    private lateinit var floatingView: View
    private var midiParser: MidiParser? = null
    private var screenMapper: ScreenMapper? = null
    private var playJob: Job? = null
    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager

        midiParser = MidiParser(this)
        screenMapper = ScreenMapper(this)
        createFloatingWindow()
    }

    // 重写onStartCommand来接收来自MidiPickerActivity的Intent
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == MidiPickerActivity.ACTION_MIDI_FILE_SELECTED) {
            intent.data?.let { uri ->
                handleMidiFileSelection(uri)
            }
        }
        return START_STICKY
    }

    private fun handleMidiFileSelection(uri: Uri) {
        // 使用协程在后台解析文件
        serviceScope.launch(Dispatchers.IO) {
            try {
                // 持久化URI权限，以防设备重启后权限丢失
                contentResolver.takePersistableUriPermission(
                    uri,
                    Intent.FLAG_GRANT_READ_URI_PERMISSION
                )
                
                // 调用 midiParser 处理 URI
                val notes = midiParser?.parseMidiFile(uri)
                withContext(Dispatchers.Main) {
                    if (notes != null && notes.isNotEmpty()) {
                        Toast.makeText(this@FloatingWindowService, "MIDI文件加载成功", Toast.LENGTH_SHORT).show()
                    } else {
                        Toast.makeText(this@FloatingWindowService, "加载失败或文件为空", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@FloatingWindowService, "解析文件出错: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun createFloatingWindow() {
        floatingView = LayoutInflater.from(this).inflate(R.layout.floating_window, null)

        val layoutParams = WindowManager.LayoutParams().apply {
            type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                WindowManager.LayoutParams.TYPE_PHONE
            }
            format = PixelFormat.TRANSLUCENT
            flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
            width = WindowManager.LayoutParams.WRAP_CONTENT
            height = WindowManager.LayoutParams.WRAP_CONTENT
            gravity = Gravity.TOP or Gravity.START
            x = 100
            y = 100
        }

        setupButtons()
        windowManager.addView(floatingView, layoutParams)
        makeDraggable(floatingView, layoutParams)
    }

    private fun setupButtons() {
        floatingView.findViewById<Button>(R.id.btnSelectMidi).setOnClickListener {
            selectMidiFile()
        }

        floatingView.findViewById<Button>(R.id.btnPlay).setOnClickListener {
            startPlaying()
        }

        floatingView.findViewById<Button>(R.id.btnStop).setOnClickListener {
            stopPlaying()
        }

        floatingView.findViewById<Button>(R.id.btnClose).setOnClickListener {
            stopSelf()
        }
    }

    private fun makeDraggable(view: View, params: WindowManager.LayoutParams) {
        var initialX = 0
        var initialY = 0
        var initialTouchX = 0f
        var initialTouchY = 0f

        view.setOnTouchListener { _, event ->
            when (event.action) {
                android.view.MotionEvent.ACTION_DOWN -> {
                    initialX = params.x
                    initialY = params.y
                    initialTouchX = event.rawX
                    initialTouchY = event.rawY
                    true
                }
                android.view.MotionEvent.ACTION_MOVE -> {
                    params.x = initialX + (event.rawX - initialTouchX).toInt()
                    params.y = initialY + (event.rawY - initialTouchY).toInt()
                    windowManager.updateViewLayout(view, params)
                    true
                }
                else -> false
            }
        }
    }
    
    private fun selectMidiFile() {
        // 启动中间Activity来处理文件选择
        val intent = Intent(this, MidiPickerActivity::class.java).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        startActivity(intent)
    }
    
    private fun startPlaying() {
        if (playJob?.isActive == true) {
            Toast.makeText(this, "正在演奏", Toast.LENGTH_SHORT).show()
            return
        }

        playJob = serviceScope.launch {
            try {
                // midiParser?.parsedNotes 应该在 handleMidiFileSelection 中被赋值
                val notes = midiParser?.parsedNotes ?: emptyList()
                if (notes.isEmpty()) {
                    withContext(Dispatchers.Main) {
                        Toast.makeText(
                            this@FloatingWindowService,
                            "请先选择并成功加载MIDI文件", Toast.LENGTH_SHORT
                        ).show()
                    }
                    return@launch
                }
                playNotes(notes)
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(
                        this@FloatingWindowService,
                        "演奏出错: ${e.message}", Toast.LENGTH_SHORT
                    ).show()
                }
                Log.w("演奏出错: ","${e.message}")
            }
        }
    }

    


    
private suspend fun playNotes(notes: List<MidiNote>) {
    withContext(Dispatchers.Main) {
        Toast.makeText(this@FloatingWindowService, "开始演奏", Toast.LENGTH_SHORT).show()
    }

    val sorted = notes.sortedBy { it.startTime }
    var lastNoteTime = 0L

    // 按 startTime 分组（保留原顺序）
    val groups = sorted.groupBy { it.startTime }.toSortedMap()

    for ((startTime, groupNotes) in groups) {
        val delayTime = startTime - lastNoteTime
        if (delayTime > 0) delay(delayTime)

        // 构建要传给服务的一组点 (x, y, duration)
        val points = mutableListOf<Triple<Float, Float, Long>>()
        for (note in groupNotes) {
            val point = screenMapper?.getScreenPoint(note.pitch)
            if (point != null) {
                points += Triple(point.first, point.second, note.duration)
            }
        }

        if (points.isNotEmpty()) {
            // 一次性发送该时间点的所有触点
            AutoClickService.getInstance()?.performMultiClickFromClient(points)
                ?: Log.w("FloatingWindow", "AutoClickService not connected or not enabled")
        }

        lastNoteTime = startTime
    }

    withContext(Dispatchers.Main) {
        Toast.makeText(this@FloatingWindowService, "演奏结束", Toast.LENGTH_SHORT).show()
    }
}

    private fun sendClickEvent(x: Float, y: Float, duration: Long) {
    // FloatingWindowService.kt 或其他同进程组件
    AutoClickService.getInstance()?.performClickFromClient(x, y, duration)
    ?: Log.w("FloatingWindow", "AutoClickService not connected or not enabled")
    }



    private fun stopPlaying() {
        playJob?.cancel()
        Toast.makeText(this, "已停止", Toast.LENGTH_SHORT).show()
    }

    override fun onDestroy() {
        super.onDestroy()
        serviceScope.cancel()
        if (::floatingView.isInitialized) {
            windowManager.removeView(floatingView)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_PERFORM_CLICK = "com.byzp.midiautoplayer.PERFORM_CLICK"
    }
}