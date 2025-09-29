package com.byzp.midiautoplayer

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import java.lang.ref.WeakReference
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicInteger

class AutoClickService : AccessibilityService() {

    companion object {
        private var instanceRef: WeakReference<AutoClickService>? = null
        fun getInstance(): AutoClickService? = instanceRef?.get()
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instanceRef = WeakReference(this)
    }

    override fun onDestroy() {
        super.onDestroy()
        instanceRef?.clear()
        instanceRef = null
    }

    /**
     * points: List<Triple<x, y, durationMs>>.
     * 同一列表中各触点会被作为同一 gesture 的多个 strokes 添加，从而实现多点同时按下。
     */
    fun performMultiClickFromClient(points: List<Triple<Float, Float, Long>>) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.N) return

        val builder = GestureDescription.Builder()
        for ((x, y, duration) in points) {
            val path = Path().apply { moveTo(x, y) }
            // startTime 为 0 表示与 gesture 开始同时按下；也可以用不同的偏移来模拟不同的相对开始时间
            val stroke = GestureDescription.StrokeDescription(path, 0, duration)
            builder.addStroke(stroke)
        }
        val gesture = builder.build()

        // dispatchGesture 在主线程调用(post 到主Looper）
        Handler(Looper.getMainLooper()).post {
            dispatchGesture(gesture, object : GestureResultCallback() {
                override fun onCompleted(gestureDescription: GestureDescription?) {
                    super.onCompleted(gestureDescription)
                    Log.d("AutoClickService", "Multi gesture completed")
                }

                override fun onCancelled(gestureDescription: GestureDescription?) {
                    super.onCancelled(gestureDescription)
                    Log.w("AutoClickService", "Multi gesture cancelled")
                }
            }, null)
        }
    }

    // 单点方法
    fun performClickFromClient(x: Float, y: Float, duration: Long) {
        performMultiClickFromClient(listOf(Triple(x, y, duration)))
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) { /* ... */ }
    override fun onInterrupt() { /* ... */ }
}
