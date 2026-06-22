// 搜索功能模块
const search = (() => {
    const API_BASE = location.origin;

    const elements = {
        get searchNameInput() { return document.getElementById('search_name'); },
        get searchResults() { return document.getElementById('search_results'); }
    };

    async function handleSearch() {
        const name = elements.searchNameInput.value;
        if (!name.trim()) {
            utils.showMessage('t-please-enter-search', 'warning');
            elements.searchResults.innerHTML = '';
            return;
        }

        try {
            const res = await fetch(`${API_BASE}/search?name=${encodeURIComponent(name)}`);
            const data = await res.json();

            if (!data.results || data.results.length === 0) {
                utils.showMessage('t-no-results', 'info');
                elements.searchResults.innerHTML = '';
                return;
            }

            let html = `
                <div class="table-container" style="max-height:300px;">
                <table>
                    <thead>
                        <tr>
                            <th data-key="name">名称</th>
                            <th data-key="uploader">上传者</th>
                            <th data-key="confidence">置信度</th>
                            <th data-key="upload-time">上传时间</th>
                            <th data-key="actions">操作</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            data.results.forEach(song => {
                html += `
                    <tr>
                        <td>${utils.escapeHtml(song.name)}</td>
                        <td>${utils.escapeHtml(song.upload_by || '')}</td>
                        <td>${song.confidence ? (song.confidence * 100).toFixed(1) + '%' : '-'}</td>
                        <td>${utils.formatUploadTime(song.upload_time)}</td>
                        <td>${songList.formatActions(song)}</td>
                    </tr>
                `;
            });

            html += `
                    </tbody>
                </table>
                </div>
            `;

            elements.searchResults.innerHTML = html;

            // 更新搜索结果表格的语言
            language.updateLanguage();
        } catch (err) {
            console.error('搜索失败', err);
            utils.showMessage('t-search-failed', 'error');
            elements.searchResults.innerHTML = '';
        }
    }

    return { handleSearch };
})();
