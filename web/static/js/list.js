// 上传列表管理模块 - 工厂函数
// 用法:
//   midiList = createSongList({ fileType: null, downloadEndpoint: '/download', ... })
//   xmlList  = createSongList({ fileType: 'musicxml', downloadEndpoint: '/download_xml?raw=true', ... })
function createSongList(config) {
    const { fileType, downloadEndpoint, elementIds } = config;
    const API_BASE = location.origin;

    // 列表状态
    const state = {
        currentPage: 1,
        pageSize: 50,
        isLoading: false,
        isEnd: false
    };

    // DOM元素缓存
    const elements = {
        get latestList() { return document.getElementById(elementIds.listId); },
        get loadingIndicator() { return document.getElementById(elementIds.loadingId); },
        get endIndicator() { return document.getElementById(elementIds.endId); },
        get tableContainer() { return document.getElementById(elementIds.containerId); }
    };

    // 构建下载 URL
    function buildDownloadUrl(hash) {
        return `${API_BASE}${downloadEndpoint}&hash=${encodeURIComponent(hash)}`;
    }

    // 格式化操作按钮
    function formatActions(song) {
        const deleteBtn = language.t('delete');
        const playBtn = language.t('play');
        const downloadBtn = language.t('download');
        const downloadUrl = buildDownloadUrl(song.hash);

        return `
            <div class="actions">
                <button onclick="midiApp.deleteSong('${song.hash}')" data-key="delete">${deleteBtn}</button>
                <button class="play" onclick="midiApp.playAudio('${song.hash}')" data-key="play">${playBtn}</button>
                <button onclick="window.open('${downloadUrl}','_blank')" data-key="download">${downloadBtn}</button>
            </div>
        `;
    }

    // 加载列表
    async function loadLatest(page = 1, append = false) {
        if (state.isLoading || (state.isEnd && append)) return;

        state.isLoading = true;
        elements.loadingIndicator.style.display = 'block';
        elements.endIndicator.style.display = 'none';

        try {
            let url = `${API_BASE}/latest_songs?page=${page}&page_size=${state.pageSize}`;
            if (fileType) {
                url += `&file_type=${encodeURIComponent(fileType)}`;
            }
            const res = await fetch(url);
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            const data = await res.json();

            if (!append) {
                elements.latestList.innerHTML = '';
            }

            const items = data.midis || data.results || [];

            items.forEach(song => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${utils.escapeHtml(song.name)}</td>
                    <td>${utils.escapeHtml(song.upload_by || '')}</td>
                    <td>${utils.formatDuration(song.duration)}</td>
                    <td>${utils.formatFileSize(song.midi_size || song.file_size)}</td>
                    <td>${utils.formatUploadTime(song.upload_time)}</td>
                    <td>${formatActions(song)}</td>
                `;
                elements.latestList.appendChild(tr);
            });

            if (items.length < state.pageSize) {
                state.isEnd = true;
                elements.endIndicator.style.display = items.length === 0 && !append ? 'none' : 'block';
            } else {
                state.isEnd = false;
            }

            state.currentPage = page;
        } catch (err) {
            console.error('加载失败', err);
            utils.showMessage('t-delete-failed', 'error');
        } finally {
            state.isLoading = false;
            elements.loadingIndicator.style.display = 'none';
        }
    }

    // 刷新列表
    function refreshList() {
        state.currentPage = 1;
        state.isEnd = false;
        loadLatest(1, false);
    }

    // 滚动加载
    function setupScrollLoad() {
        const onScroll = utils.debounce(() => {
            if (state.isLoading || state.isEnd) return;
            const { scrollTop, clientHeight, scrollHeight } = elements.tableContainer;
            if (scrollTop + clientHeight >= scrollHeight - 80) {
                loadLatest(state.currentPage + 1, true);
            }
        }, 150);

        elements.tableContainer.addEventListener('scroll', onScroll);
    }

    return {
        loadLatest,
        refreshList,
        setupScrollLoad,
        formatActions
    };
}

// 向后兼容：默认 songList 指向 MIDI 列表（由 app.js 初始化后设置）
let songList = null;
