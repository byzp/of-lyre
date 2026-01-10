package com.byzp.midiautoplayer

import android.app.Service
import android.content.Intent
import android.graphics.PixelFormat
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.provider.OpenableColumns
import android.view.Gravity
import android.view.LayoutInflater
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import com.byzp.midiautoplayer.models.*
import com.byzp.midiautoplayer.utils.*
import kotlinx.coroutines.*
import android.util.Log
import java.io.File

class FloatingWindowService : Service() {
    private lateinit var windowManager: WindowManager
    private lateinit var floatingView: View
    private var midiParser: MidiParser? = null
    private var screenMapper: ScreenMapper? = null
    private var playJob: Job? = null
    private val serviceScope = CoroutineScope(Dispatchers.Main + SupervisorJob())
    private lateinit var midiStorage: MidiStorage
    private var currentMidiUri: Uri? = null
    private var currentMidiName: String? = null
    
    // 确认对话框相关
    private var confirmDialog: View? = null

    override fun onCreate() {
        super.onCreate()
        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager

        midiParser = MidiParser(this)
        screenMapper = ScreenMapper(this)
        midiStorage = MidiStorage(this)
        createFloatingWindow()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == MidiPickerActivity.ACTION_MIDI_FILE_SELECTED) {
            intent.data?.let { uri ->
                handleMidiFileSelection(uri)
            }
        }
        return START_STICKY
    }

    /**
     * 从URI正确提取文件名
     */
    private fun extractFileName(uri: Uri): String {
        // 方法1: 从ContentResolver查询显示名称（适用于content:// URI）
        try {
            contentResolver.query(uri, null, null, null, null)?.use { cursor ->
                if (cursor.moveToFirst()) {
                    val displayNameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (displayNameIndex >= 0) {
                        val displayName = cursor.getString(displayNameIndex)
                        if (!displayName.isNullOrBlank()) {
                            return displayName
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.d("FloatingWindow", "Could not query display name: ${e.message}")
        }

        // 方法2: 从路径中提取（适用于file:// URI或其他情况）
        val path = uri.path ?: uri.lastPathSegment ?: return "unknown_${System.currentTimeMillis()}.mid"
        
        // 处理各种路径格式
        var fileName = path
            .substringAfterLast("/")  // 取最后一个/后面的部分
            .substringAfterLast(":")   // 处理类似 "primary:Download/xxx.mid" 的格式
        
        // 如果文件名为空或只有扩展名，生成默认名称
        if (fileName.isBlank() || fileName.startsWith(".")) {
            fileName = "midi_${System.currentTimeMillis()}.mid"
        }
        
        // 确保有.mid扩展名
        if (!fileName.lowercase().endsWith(".mid") && !fileName.lowercase().endsWith(".midi")) {
            fileName = "$fileName.mid"
        }
        
        return fileName
    }

    /**
     * 获取唯一文件名，避免覆盖已存在的文件
     */
    private fun getUniqueFileName(baseName: String): String {
        val existingFiles = midiStorage.getSavedMidis()
        val existingNames = existingFiles.map { it.name }.toSet()

        // 如果不存在同名文件，直接返回
        if (baseName !in existingNames) {
            return baseName
        }

        // 分离文件名和扩展名
        val lastDotIndex = baseName.lastIndexOf(".")
        val nameWithoutExt: String
        val ext: String
        
        if (lastDotIndex > 0) {
            nameWithoutExt = baseName.substring(0, lastDotIndex)
            ext = baseName.substring(lastDotIndex)
        } else {
            nameWithoutExt = baseName
            ext = ".mid"
        }

        // 查找可用的数字后缀
        var counter = 1
        var newName = "${nameWithoutExt}_$counter$ext"
        while (newName in existingNames) {
            counter++
            newName = "${nameWithoutExt}_$counter$ext"
        }
        
        return newName
    }

    private fun handleMidiFileSelection(uri: Uri) {
        currentMidiUri = uri
        currentMidiName = extractFileName(uri)
        
        serviceScope.launch(Dispatchers.IO) {
            try {
                try {
                    contentResolver.takePersistableUriPermission(
                        uri,
                        Intent.FLAG_GRANT_READ_URI_PERMISSION
                    )
                } catch (e: Exception) {
                    Log.d("FloatingWindow", "Could not take persistable permission: ${e.message}")
                }
                
                val notes = midiParser?.parseMidiFile(uri)
                withContext(Dispatchers.Main) {
                    if (notes != null && notes.isNotEmpty()) {
                        Toast.makeText(this@FloatingWindowService, "MIDI文件加载成功: $currentMidiName", Toast.LENGTH_SHORT).show()
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
                @Suppress("DEPRECATION")
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

        floatingView.findViewById<Button>(R.id.btnSaveMidi).setOnClickListener {
            saveCurrentMidi()
        }

        val rvSavedMidis = floatingView.findViewById<androidx.recyclerview.widget.RecyclerView>(R.id.rvSavedMidis)
        floatingView.findViewById<Button>(R.id.btnShowList).setOnClickListener {
            if (rvSavedMidis.visibility == View.VISIBLE) {
                rvSavedMidis.visibility = View.GONE
            } else {
                showSavedMidisList(rvSavedMidis)
            }
        }
    }

    private fun saveCurrentMidi() {
        val uri = currentMidiUri
        if (uri == null) {
            Toast.makeText(this, "没有加载中的MIDI", Toast.LENGTH_SHORT).show()
            return
        }
        
        serviceScope.launch(Dispatchers.IO) {
            try {
                contentResolver.openInputStream(uri)?.use { input ->
                    val bytes = input.readBytes()
                    val baseName = currentMidiName ?: "saved_${System.currentTimeMillis()}.mid"
                    // 获取唯一文件名
                    val uniqueName = getUniqueFileName(baseName)
                    midiStorage.saveMidi(uniqueName, bytes)
                    
                    withContext(Dispatchers.Main) {
                        Toast.makeText(this@FloatingWindowService, "保存成功: $uniqueName", Toast.LENGTH_SHORT).show()
                        // 刷新列表（如果可见）
                        val rvSavedMidis = floatingView.findViewById<androidx.recyclerview.widget.RecyclerView>(R.id.rvSavedMidis)
                        if (rvSavedMidis.visibility == View.VISIBLE) {
                            showSavedMidisList(rvSavedMidis)
                        }
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@FloatingWindowService, "保存失败: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    private fun showSavedMidisList(recyclerView: androidx.recyclerview.widget.RecyclerView) {
        val files = midiStorage.getSavedMidis()
        if (files.isEmpty()) {
            Toast.makeText(this, "没有已保存的MIDI", Toast.LENGTH_SHORT).show()
            recyclerView.visibility = View.GONE
            return
        }
        recyclerView.visibility = View.VISIBLE
        recyclerView.layoutManager = androidx.recyclerview.widget.LinearLayoutManager(this)
        recyclerView.adapter = SavedMidiAdapter(
            files.toMutableList(),
            onItemClick = { file ->
                handleMidiFileSelection(Uri.fromFile(file))
                recyclerView.visibility = View.GONE
            },
            onDeleteClick = { file, adapter ->
                showDeleteConfirmDialog(file) {
                    // 确认删除
                    deleteMidiFile(file, adapter, recyclerView)
                }
            }
        )
    }

    /**
     * 显示删除确认对话框
     */
    private fun showDeleteConfirmDialog(file: File, onConfirm: () -> Unit) {
        // 如果已有对话框，先移除
        dismissConfirmDialog()

        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_confirm, null)
        
        val layoutParams = WindowManager.LayoutParams().apply {
            type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
            } else {
                @Suppress("DEPRECATION")
                WindowManager.LayoutParams.TYPE_PHONE
            }
            format = PixelFormat.TRANSLUCENT
            flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
            width = WindowManager.LayoutParams.WRAP_CONTENT
            height = WindowManager.LayoutParams.WRAP_CONTENT
            gravity = Gravity.CENTER
        }

        // 设置对话框内容
        dialogView.findViewById<TextView>(R.id.tvDialogMessage).text = 
            "确定要删除文件 \"${file.name}\" 吗？"

        dialogView.findViewById<Button>(R.id.btnCancel).setOnClickListener {
            dismissConfirmDialog()
        }

        dialogView.findViewById<Button>(R.id.btnConfirm).setOnClickListener {
            dismissConfirmDialog()
            onConfirm()
        }

        confirmDialog = dialogView
        windowManager.addView(dialogView, layoutParams)
    }

    /**
     * 关闭确认对话框
     */
    private fun dismissConfirmDialog() {
        confirmDialog?.let {
            try {
                windowManager.removeView(it)
            } catch (e: Exception) {
                Log.e("FloatingWindow", "Error removing dialog: ${e.message}")
            }
        }
        confirmDialog = null
    }

    /**
     * 删除MIDI文件
     */
    private fun deleteMidiFile(
        file: File, 
        adapter: SavedMidiAdapter, 
        recyclerView: androidx.recyclerview.widget.RecyclerView
    ) {
        serviceScope.launch(Dispatchers.IO) {
            try {
                val deleted = file.delete()
                withContext(Dispatchers.Main) {
                    if (deleted) {
                        Toast.makeText(this@FloatingWindowService, "已删除: ${file.name}", Toast.LENGTH_SHORT).show()
                        // 更新列表
                        adapter.removeItem(file)
                        if (adapter.itemCount == 0) {
                            recyclerView.visibility = View.GONE
                        }
                    } else {
                        Toast.makeText(this@FloatingWindowService, "删除失败", Toast.LENGTH_SHORT).show()
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Toast.makeText(this@FloatingWindowService, "删除出错: ${e.message}", Toast.LENGTH_SHORT).show()
                }
            }
        }
    }

    /**
     * 已保存MIDI文件列表适配器
     */
    inner class SavedMidiAdapter(
        private val items: MutableList<File>,
        private val onItemClick: (File) -> Unit,
        private val onDeleteClick: (File, SavedMidiAdapter) -> Unit
    ) : androidx.recyclerview.widget.RecyclerView.Adapter<SavedMidiAdapter.ViewHolder>() {

        inner class ViewHolder(view: View) : androidx.recyclerview.widget.RecyclerView.ViewHolder(view) {
            val tvName: TextView = view.findViewById(R.id.tvMidiName)
            val btnDelete: Button = view.findViewById(R.id.btnDelete)
        }

        override fun onCreateViewHolder(parent: android.view.ViewGroup, viewType: Int): ViewHolder {
            val view = LayoutInflater.from(parent.context)
                .inflate(R.layout.item_saved_midi, parent, false)
            return ViewHolder(view)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            val item = items[position]
            holder.tvName.text = item.name
            
            holder.itemView.setOnClickListener { 
                onItemClick(item) 
            }
            
            holder.btnDelete.setOnClickListener { 
                onDeleteClick(item, this) 
            }
        }

        override fun getItemCount() = items.size

        fun removeItem(file: File) {
            val position = items.indexOf(file)
            if (position >= 0) {
                items.removeAt(position)
                notifyItemRemoved(position)
            }
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

        val groups = sorted.groupBy { it.startTime }.toSortedMap()

        for ((startTime, groupNotes) in groups) {
            val delayTime = startTime - lastNoteTime
            if (delayTime > 0) delay(delayTime)

            val points = mutableListOf<Triple<Float, Float, Long>>()
            for (note in groupNotes) {
                val point = screenMapper?.getScreenPoint(note.pitch)
                if (point != null) {
                    points += Triple(point.first, point.second, note.duration)
                }
            }

            if (points.isNotEmpty()) {
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
        dismissConfirmDialog()
        if (::floatingView.isInitialized) {
            windowManager.removeView(floatingView)
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        const val ACTION_PERFORM_CLICK = "com.byzp.midiautoplayer.PERFORM_CLICK"
    }
}