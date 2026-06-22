// 留言功能模块
const comments = (() => {
    const API_BASE = location.origin;

    const elements = {
        get commentNameInput() { return document.getElementById('comment_name'); },
        get commentContentInput() { return document.getElementById('comment_content'); },
        get commentsList() { return document.getElementById('comments_list'); }
    };

    // 添加留言
    async function addComment() {
        const name = elements.commentNameInput.value;
        const content = elements.commentContentInput.value;

        if (!name.trim() || !content.trim()) {
            utils.showMessage('t-please-fill-message', 'warning');
            return;
        }

        const form = new FormData();
        form.append('name', name);
        form.append('content', content);
        form.append('device_id', utils.getDeviceId());

        try {
            const res = await fetch(`${API_BASE}/add_comment`, {
                method: 'POST',
                body: form
            });

            const data = await res.json();

            if (data.succeed) {
                utils.showMessage('t-message-add-success', 'success');

                // 重置表单
                document.getElementById('comment-form').reset();

                // 刷新留言列表
                loadComments();
            } else {
                utils.showMessage(data.message || 't-message-add-failed', 'error');
            }
        } catch (err) {
            console.error('添加留言失败', err);
            utils.showMessage('t-message-add-failed', 'error');
        }
    }

    // 加载留言列表
    async function loadComments() {
        try {
            const res = await fetch(`${API_BASE}/comments`);
            const data = await res.json();

            if (data.succeed) {
                renderComments(data.comments);
            } else {
                utils.showMessage(data.message || 't-message-add-failed', 'error');
            }
        } catch (err) {
            console.error('加载留言失败', err);
            utils.showMessage('t-message-add-failed', 'error');
        }
    }

    // 渲染留言列表
    function renderComments(commentsList) {
        if (!commentsList || commentsList.length === 0) {
            elements.commentsList.innerHTML = `<p class="small" style="text-align: center;">${language.t('t-no-comments')}</p>`;
            return;
        }

        const currentDeviceId = utils.getDeviceId();
        let html = '';
        commentsList.forEach(comment => {
            // 格式化时间
            const formattedTime = utils.formatUploadTime(comment.created_at);

            // 管理员或当前设备的留言才显示删除按钮
            const showDelete = appState.isAdmin || comment.device_id === currentDeviceId;
            const deleteButton = showDelete ? `
                <div class="comment-actions">
                    <button onclick="midiApp.deleteComment('${comment.id}')">删除</button>
                </div>
            ` : '';

            html += `
                <div class="comment-item">
                    <div class="comment-header">
                        <span class="comment-author">${utils.escapeHtml(comment.name)}</span>
                        <span class="comment-time">${formattedTime}</span>
                    </div>
                    <div class="comment-content">${utils.escapeHtml(comment.content)}</div>
                    ${deleteButton}
                </div>
            `;
        });

        elements.commentsList.innerHTML = html;
    }

    // 删除留言
    async function deleteComment(commentId) {
        if (!confirm(language.t('confirm-delete-message'))) return;

        const form = new FormData();
        form.append('comment_id', commentId);
        form.append('device_id', utils.getDeviceId());

        // 如果是管理员状态，传递密码参数
        if (appState.isAdmin && appState.routeAdmin) {
            form.append('admin_password', appState.routeAdmin);
        }

        try {
            const res = await fetch(`${API_BASE}/delete_comment${appState.routeAdmin ? `?admin=${encodeURIComponent(appState.routeAdmin)}` : ''}`, {
                method: 'POST',
                body: form
            });

            const data = await res.json();

            if (data.succeed) {
                utils.showMessage('t-message-delete-success', 'success');
                loadComments();
            } else {
                utils.showMessage(data.message || 't-message-delete-failed', 'error');
            }
        } catch (err) {
            console.error('删除留言失败', err);
            utils.showMessage('t-message-delete-failed', 'error');
        }
    }

    return {
        addComment,
        loadComments,
        deleteComment
    };
})();
