// 应用全局状态
const appState = {
    isAdmin: false,
    routeAdmin: null
};

// 创建两个独立的列表实例
// MIDI 列表：默认只显示 MIDI 文件，下载为 MIDI 格式
const midiList = createSongList({
    fileType: 'midi',
    downloadEndpoint: '/download?',
    elementIds: {
        listId: 'midi_list',
        loadingId: 'midi_loading',
        endId: 'midi_end',
        containerId: 'midi_table_container'
    }
});

// MusicXML 列表：默认只显示 MusicXML 文件，下载为 MusicXML 格式（MIDI 自动转换）
const xmlList = createSongList({
    fileType: 'musicxml',
    downloadEndpoint: '/download_xml?',
    sizeField: 'file_size',
    elementIds: {
        listId: 'xml_list',
        loadingId: 'xml_loading',
        endId: 'xml_end',
        containerId: 'xml_table_container'
    }
});

// 默认 songList 指向 MIDI 列表（向后兼容其他模块引用）
songList = midiList;

// 复选框切换：MIDI 列表是否包含 MusicXML
function toggleMidiOther() {
    const checked = document.getElementById('midi_include_other').checked;
    midiList.setFileType(checked ? null : 'midi');
    midiList.refreshList();
}

// 复选框切换：MusicXML 列表是否包含 MIDI
function toggleXmlOther() {
    const checked = document.getElementById('xml_include_other').checked;
    xmlList.setFileType(checked ? null : 'musicxml');
    xmlList.refreshList();
}

// 歌曲操作模块
const songActions = (() => {
    const API_BASE = location.origin;

    // 下载歌曲
    function download(hash) {
        window.open(`${API_BASE}/download?hash=${encodeURIComponent(hash)}`, '_blank');
    }

    // 删除歌曲
    async function deleteSong(hash) {
        let pwd = '';
        // 管理员模式下不需要输入密码
        if (appState.isAdmin) {
            const confirmDelete = confirm(language.t('confirm-delete'));
            if (!confirmDelete) return;
        } else {
            pwd = prompt(language.t('please-enter-delete-password'));
            if (pwd === null) return;
        }

        const form = new FormData();
        form.append('hash', hash);
        form.append('delete_password', appState.isAdmin ? '' : pwd);

        // 如果是管理员状态，传递密码参数
        if (appState.isAdmin && appState.routeAdmin) {
            form.append('admin_password', appState.routeAdmin);
        }

        try {
            const res = await fetch(`${API_BASE}/delete${appState.routeAdmin ? `?admin=${encodeURIComponent(appState.routeAdmin)}` : ''}`, {
                method: 'POST',
                body: form
            });

            const data = await res.json();

            // 使用通用提示函数
            utils.showMessage(data.message || language.t('delete-success'), 'success');

            // 刷新两个列表
            midiList.refreshList();
            xmlList.refreshList();
        } catch (err) {
            console.error('删除失败', err);
            utils.showMessage('t-delete-failed', 'error');
        }
    }

    return { download, deleteSong };
})();

// 解析URL中的路由参数
function parseUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);
    appState.routeAdmin = urlParams.get('admin');
    if (appState.routeAdmin) {
        appState.isAdmin = true;
    }
}

// 初始化应用
function init() {
    // 解析路由参数
    parseUrlParams();

    // 初始化语言系统
    language.init();

    // 设置两个列表的滚动加载
    midiList.setupScrollLoad();
    xmlList.setupScrollLoad();

    // 初始化音频播放器
    audioPlayer.init();

    // 首次加载（默认显示上传页，MIDI列表会在切换到对应tab时加载）
    midiList.loadLatest(1, false);
}

// 暴露全局API（仅用于按钮点击事件）
window.midiApp = {
    switchTab: tabs.switchTab,
    upload: upload.handleUpload,
    search: search.handleSearch,
    refreshMidiList: midiList.refreshList,
    refreshXmlList: xmlList.refreshList,
    refreshList: midiList.refreshList,  // 向后兼容
    toggleMidiOther: toggleMidiOther,
    toggleXmlOther: toggleXmlOther,
    download: songActions.download,
    deleteSong: songActions.deleteSong,
    playAudio: audioPlayer.playAudio,
    addComment: comments.addComment,
    loadComments: comments.loadComments,
    deleteComment: comments.deleteComment
};

// 暴露音频播放器函数到全局
window.audioPlayer = {
    togglePlayPause: audioPlayer.togglePlayPause,
    close: audioPlayer.close,
    get audio() { return document.getElementById('audioElement'); }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
