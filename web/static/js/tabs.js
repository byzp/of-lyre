// 标签页管理模块
const tabs = (() => {
    function switchTab(tabId, event) {
        // 更新导航按钮状态
        document.querySelectorAll('.tab-nav button').forEach(btn => btn.classList.remove('active'));
        event.target.classList.add('active');

        // 更新内容面板显示
        document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.remove('active'));
        document.getElementById(tabId).classList.add('active');

        // 当切换到留言标签页时，加载留言列表
        if (tabId === 'comments') {
            comments.loadComments();
        }
        // 切换到 MIDI 列表时加载
        if (tabId === 'list-midi') {
            midiList.loadLatest(1, false);
        }
        // 切换到 MusicXML 列表时加载
        if (tabId === 'list-xml') {
            xmlList.loadLatest(1, false);
        }
    }

    return { switchTab };
})();
