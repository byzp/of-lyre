// 音频播放器模块
const audioPlayer = (() => {
    // DOM引用 - 懒加载
    const dom = {
        get audio() { return document.getElementById('audioElement'); },
        get progressBar() { return document.getElementById('progressBar'); },
        get progressContainer() { return document.getElementById('progressContainer'); },
        get currentTimeEl() { return document.getElementById('currentTime'); },
        get durationEl() { return document.getElementById('duration'); },
        get playPauseButton() { return document.getElementById('playPauseButton'); },
        get playerTitle() { return document.getElementById('playerTitle'); },
        get audioPlayer() { return document.getElementById('audioPlayer'); },
        get waitingPlayer() { return document.getElementById('waitingPlayer'); },
        get playerOverlay() { return document.getElementById('playerOverlay'); }
    };

    let isDragging = false;
    let timeout = null;
    let handleLoadedMetadata = null;
    let handleCanPlay = null;
    let handleError = null;

    function formatTime(seconds) {
        // 处理各种无效值情况
        if (isNaN(seconds) || !isFinite(seconds) || seconds < 0) {
            return '0:00';
        }

        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.floor(seconds % 60);
        return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
    }

    function updateProgress() {
        // 如果正在拖动，不更新进度条显示
        if (isDragging) {
            return;
        }

        // 检查音频时长是否有效
        if (isNaN(dom.audio.duration) || !isFinite(dom.audio.duration)) {
            return;
        }

        const currentTime = dom.audio.currentTime;
        const duration = dom.audio.duration;
        const percent = (currentTime / duration) * 100;

        // 更新进度条
        dom.progressBar.style.width = percent + '%';
        dom.currentTimeEl.textContent = formatTime(currentTime);
    }

    function updateDuration() {
        // 检查 duration 是否为有效数字
        if (isNaN(dom.audio.duration) || !isFinite(dom.audio.duration)) {
            dom.durationEl.textContent = '0:00';
        } else {
            dom.durationEl.textContent = formatTime(dom.audio.duration);
        }
    }

    function seek(e) {
        // 阻止事件冒泡和默认行为
        e.preventDefault();
        e.stopPropagation();

        const rect = dom.progressContainer.getBoundingClientRect();
        const percent = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));

        // 检查 audio.duration 是否为有效数字
        if (isNaN(dom.audio.duration) || !isFinite(dom.audio.duration)) {
            console.warn('音频时长无效:', dom.audio.duration);
            return;
        }

        const time = percent * dom.audio.duration;
        // 检查计算出的 time 是否为有效数字
        if (isFinite(time)) {
            console.log('设置播放时间:', time, '百分比:', percent);
            try {
                dom.audio.currentTime = time;
                // 立即更新进度条显示
                dom.progressBar.style.width = (percent * 100) + '%';
                dom.currentTimeEl.textContent = formatTime(time);
            } catch (err) {
                console.error('设置播放时间失败:', err);
            }
        }
    }

    function onEnded() {
        dom.playPauseButton.textContent = language.t('play');
        dom.progressBar.style.width = '0%';
        dom.currentTimeEl.textContent = '0:00';
    }

    function showWaiting() {
        dom.waitingPlayer.classList.add('active');
        dom.playerOverlay.classList.add('active');
    }

    function showPlayer() {
        dom.waitingPlayer.classList.remove('active');
        dom.audioPlayer.classList.add('active');
        dom.playPauseButton.textContent = '播放';
        dom.playPauseButton.disabled = false;
    }

    function close() {
        // 清理超时
        if (timeout) {
            clearTimeout(timeout);
            timeout = null;
        }

        // 清理事件监听器
        if (handleLoadedMetadata) {
            dom.audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
            handleLoadedMetadata = null;
        }
        if (handleCanPlay) {
            dom.audio.removeEventListener('canplay', handleCanPlay);
            handleCanPlay = null;
        }
        if (handleError) {
            dom.audio.removeEventListener('error', handleError);
            handleError = null;
        }

        // 重置UI状态
        dom.audioPlayer.classList.remove('active');
        dom.waitingPlayer.classList.remove('active');
        dom.playerOverlay.classList.remove('active');
        dom.audio.pause();
        dom.audio.src = '';
        isDragging = false;
        dom.playPauseButton.textContent = '播放';
        dom.playPauseButton.disabled = true;
        dom.progressBar.style.width = '0%';
        dom.currentTimeEl.textContent = '0:00';
    }

    function togglePlayPause() {
        if (dom.audio.paused) {
            dom.audio.play();
        } else {
            dom.audio.pause();
        }
        language.updatePlayPauseText();
    }

    function playAudio(hash) {
        const url = `http://139.196.113.128:1220/wav?hash=${encodeURIComponent(hash)}`;
        dom.playerTitle.textContent = `${language.t('now-playing')}: ${hash.substring(0, 8)}...`;

        // 显示等待提示
        showWaiting();

        // 重置音频元素
        dom.audio.src = '';
        isDragging = false;

        // 设置音频源 - 针对AAC格式优化
        dom.audio.src = url;
        dom.audio.preload = 'metadata';
        // 对于AAC流，可能需要设置一些额外属性
        dom.audio.crossOrigin = 'anonymous';

        // 清理之前的事件监听器
        dom.audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
        dom.audio.removeEventListener('canplay', handleCanPlay);
        dom.audio.removeEventListener('error', handleError);

        // 定义事件处理器
        handleLoadedMetadata = () => {
            showPlayer();
            updateDuration();
            console.log('音频元数据加载完成，时长:', dom.audio.duration);
        };

        handleCanPlay = () => {
            clearTimeout(timeout);
            dom.audio.play().then(() => {
                dom.playPauseButton.textContent = language.t('pause');
                utils.showMessage('t-start-playing', 'success');
            }).catch(err => {
                console.error('播放失败:', err);
                utils.showMessage('t-play-failed', 'error');
                close();
            });
        };

        handleError = (e) => {
            clearTimeout(timeout);
            console.error('音频加载错误:', e);
            utils.showMessage('t-audio-load-failed', 'error');
            close();
        };

        // 添加事件监听器
        dom.audio.addEventListener('loadedmetadata', handleLoadedMetadata, { once: true });
        dom.audio.addEventListener('canplay', handleCanPlay, { once: true });
        dom.audio.addEventListener('error', handleError, { once: true });

        // 设置超时处理
        timeout = setTimeout(() => {
            utils.showMessage('t-audio-load-timeout', 'error');
            close();
        }, 15000);

        // 开始加载
        dom.audio.load();
    }

    function setupDrag() {
        let dragging = false;

        const startDrag = (e) => {
            dragging = true;
            isDragging = true;
            dom.progressContainer.style.cursor = 'grabbing';
            dom.progressBar.classList.add('dragging');
            seek(e);
        };

        const drag = (e) => {
            if (!dragging) return;
            e.preventDefault();
            seek(e);
        };

        const endDrag = () => {
            dragging = false;
            isDragging = false;
            dom.progressContainer.style.cursor = 'pointer';
            dom.progressBar.classList.remove('dragging');
        };

        // 鼠标事件
        dom.progressContainer.addEventListener('mousedown', startDrag);
        document.addEventListener('mousemove', drag);
        document.addEventListener('mouseup', endDrag);

        // 触摸事件（移动设备支持）
        dom.progressContainer.addEventListener('touchstart', (e) => {
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousedown', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            startDrag(mouseEvent);
        });

        document.addEventListener('touchmove', (e) => {
            if (!dragging) return;
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousemove', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            drag(mouseEvent);
        });

        document.addEventListener('touchend', endDrag);
    }

    function init() {
        dom.audio.addEventListener('timeupdate', () => updateProgress());
        dom.audio.addEventListener('loadedmetadata', () => updateDuration());
        dom.audio.addEventListener('ended', () => onEnded());
        // 添加错误处理，在音频加载失败时也能正确显示
        dom.audio.addEventListener('error', () => {
            updateDuration();
        });

        // 点击事件
        dom.progressContainer.addEventListener('click', (e) => seek(e));

        // 拖动功能
        setupDrag();
    }

    return {
        init,
        playAudio,
        close,
        togglePlayPause,
        get audio() { return dom.audio; }  // 供 language.updatePlayPauseText 使用
    };
})();
