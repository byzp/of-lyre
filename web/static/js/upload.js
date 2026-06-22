// 上传功能模块
const upload = (() => {
    const API_BASE = location.origin;

    const elements = {
        get fileInput() { return document.getElementById('file'); },
        get uploadByInput() { return document.getElementById('upload_by'); },
        get deletePasswordInput() { return document.getElementById('delete_password'); },
        get uploadResult() { return document.getElementById('upload_result'); }
    };

    async function handleUpload() {
        const file = elements.fileInput.files[0];
        const uploadBy = elements.uploadByInput.value;
        const deletePassword = elements.deletePasswordInput.value;

        if (!file) {
            utils.showMessage('t-please-select-file', 'warning');
            return;
        }

        const form = new FormData();
        form.append('file', file);
        form.append('upload_by', uploadBy);
        form.append('delete_password', deletePassword);

        try {
            const res = await fetch(`${API_BASE}/upload`, {
                method: 'POST',
                body: form
            });

            const data = await res.json();

            // 使用通用提示函数
            utils.showMessage(data.message || 't-upload-success', 'success');

            // 重置表单
            document.getElementById('upload-form').reset();

            // 清空原有的提示
            elements.uploadResult.innerText = '';

            // 刷新列表
            midiList.refreshList();
            xmlList.refreshList();
        } catch (err) {
            console.error('上传失败', err);
            utils.showMessage('t-upload-failed', 'error');
            elements.uploadResult.innerText = '';
        }
    }

    return { handleUpload };
})();
