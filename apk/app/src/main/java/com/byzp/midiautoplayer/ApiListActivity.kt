package com.byzp.midiautoplayer

import android.net.Uri
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.byzp.midiautoplayer.api.ApiService
import com.byzp.midiautoplayer.api.MidiInfo
import com.byzp.midiautoplayer.utils.MidiStorage
import kotlinx.coroutines.launch
import java.io.File

class ApiListActivity : AppCompatActivity() {
    private lateinit var apiService: ApiService
    private lateinit var midiStorage: MidiStorage
    private lateinit var rvApiList: RecyclerView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_api_list)

        apiService = ApiService() // 实际使用时需替换为正确的服务器地址
        midiStorage = MidiStorage(this)
        rvApiList = findViewById(R.id.rvApiList)
        rvApiList.layoutManager = LinearLayoutManager(this)

        loadSongs()
    }

    private fun loadSongs() {
        lifecycleScope.launch {
            val response = apiService.getLatestSongs()
            if (response != null) {
                rvApiList.adapter = ApiListAdapter(response.midis) { midiInfo ->
                    downloadAndImport(midiInfo)
                }
            } else {
                Toast.makeText(this@ApiListActivity, "加载失败", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun downloadAndImport(midiInfo: MidiInfo) {
        lifecycleScope.launch {
            val file = File(getExternalFilesDir(null), "temp_${midiInfo.hash}.mid")
            val success = apiService.downloadMidi(midiInfo.hash, file)
            if (success) {
                val savedFile = midiStorage.saveMidi(midiInfo.name, file.readBytes())
                file.delete()
                Toast.makeText(this@ApiListActivity, "下载并导入成功: ${midiInfo.name}", Toast.LENGTH_SHORT).show()
                
                // 自动加载到悬浮窗
                val intent = android.content.Intent(this@ApiListActivity, FloatingWindowService::class.java).apply {
                    action = MidiPickerActivity.ACTION_MIDI_FILE_SELECTED
                    data = Uri.fromFile(savedFile)
                }
                startService(intent)
            } else {
                Toast.makeText(this@ApiListActivity, "下载失败", Toast.LENGTH_SHORT).show()
            }
        }
    }

    inner class ApiListAdapter(
        private val items: List<MidiInfo>,
        private val onItemClick: (MidiInfo) -> Unit
    ) : RecyclerView.Adapter<ApiListAdapter.ViewHolder>() {

        inner class ViewHolder(view: View) : RecyclerView.ViewHolder(view) {
            val tvName: TextView = view.findViewById(android.R.id.text1)
        }

        override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): ViewHolder {
            val view = LayoutInflater.from(parent.context)
                .inflate(android.R.layout.simple_list_item_1, parent, false)
            return ViewHolder(view)
        }

        override fun onBindViewHolder(holder: ViewHolder, position: Int) {
            val item = items[position]
            holder.tvName.text = item.name
            holder.itemView.setOnClickListener { onItemClick(item) }
        }

        override fun getItemCount() = items.size
    }
}
