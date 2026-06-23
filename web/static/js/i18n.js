// 多语言支持
const language = {
    // 当前语言
    currentLang: 'en',

    // 支持的语言列表
    supportedLangs: ['zh', 'en', 'ja', 'vi', 'ko'],

    // 翻译对象
    translations: {
        zh: {
            title: 'MIDI 管理页',
            'upload-midi': '上传 MIDI',
            'select-file': '选择文件',
            'upload-page': '上传',
            'latest-midi': 'MIDI',
            'latest-musicxml': 'MusicXML',
            'latest-midi-header': 'MIDI 上传',
            'latest-musicxml-header': 'MusicXML 上传',
            'search-songs': '搜索歌曲',
            'latest-uploads': '上传',
            'message-board': '留言板',
            'upload': '上传',
            'uploader-name': '上传者名称',
            'delete-password': '删除时需要的密码',
            'upload-result': '',
            'search-placeholder': '歌曲名（支持模糊 / * 随机）',
            'search': '搜索',
            'latest-uploads-header': '上传',
            'refresh': '刷新',
            'name': '名称',
            'uploader': '上传者',
            'duration': '时长',
            'size': '大小',
            'upload-time': '上传时间',
            'actions': '操作',
            'confidence': '置信度',
            'delete': '删除',
            'play': '试听',
            'download': '下载',
            'loading': '加载中...',
            'no-more-data': '没有更多数据',
            'please-select-file': '请选择MIDI文件',
            'upload-success': '上传完成',
            'upload-failed': '上传失败，请重试',
            'please-enter-search': '请输入搜索关键词',
            'no-results': '没有找到结果',
            'search-failed': '搜索失败，请重试',
            'confirm-delete': '确定要删除这个音乐文件吗？',
            'please-enter-delete-password': '请输入删除密码',
            'delete-success': '删除成功',
            'delete-failed': '删除失败，请重试',
            'message': '留言',
            'nickname': '您的昵称',
            'message-content': '请输入留言内容',
            'submit-message': '提交留言',
            'refresh-comments': '刷新',
            'no-comments': '暂无留言',
            'message-add-success': '留言添加成功',
            'message-add-failed': '留言添加失败',
            'please-fill-message': '请填写完整的留言信息',
            'message-delete-success': '留言删除成功',
            'message-delete-failed': '留言删除失败',
            'confirm-delete-message': '确定要删除这条留言吗？',
            'now-playing': '正在试听',
            'close': '关闭',
            'generating-audio': '正在生成音频，请稍候...',
            'start-playing': '开始播放',
            'play-failed': '播放失败，请重试',
            'audio-load-failed': '音频加载失败，请重试',
            'audio-load-timeout': '音频加载超时，请重试',
            'about-api': '有关此 API',
            'pause': '暂停',
            'play': '播放',
            'loading': '加载中...'
        },
        en: {
            title: 'MIDI Manager',
            'upload-midi': 'Upload MIDI',
            'select-file': 'Select File',
            'upload-page': 'Upload',
            'latest-midi': 'MIDI',
            'latest-musicxml': 'MusicXML',
            'latest-midi-header': 'MIDI Uploads',
            'latest-musicxml-header': 'MusicXML Uploads',
            'search-songs': 'Search Songs',
            'latest-uploads': 'Uploads',
            'message-board': 'Message Board',
            'upload': 'Upload',
            'uploader-name': 'Uploader Name',
            'delete-password': 'Delete Password',
            'upload-result': '',
            'search-placeholder': 'Song Name (supports fuzzy / * random)',
            'search': 'Search',
            'latest-uploads-header': 'Uploads',
            'refresh': 'Refresh',
            'name': 'Name',
            'uploader': 'Uploader',
            'duration': 'Duration',
            'size': 'Size',
            'upload-time': 'Upload Time',
            'actions': 'Actions',
            'confidence': 'Confidence',
            'delete': 'Delete',
            'play': 'Play',
            'download': 'Download',
            'loading': 'Loading...',
            'no-more-data': 'No more data',
            'please-select-file': 'Please select MIDI file',
            'upload-success': 'Upload completed',
            'upload-failed': 'Upload failed, please try again',
            'please-enter-search': 'Please enter search keyword',
            'no-results': 'No results found',
            'search-failed': 'Search failed, please try again',
            'confirm-delete': 'Are you sure you want to delete this music file?',
            'please-enter-delete-password': 'Please enter delete password',
            'delete-success': 'Delete successful',
            'delete-failed': 'Delete failed, please try again',
            'message': 'Message',
            'nickname': 'Your Nickname',
            'message-content': 'Please enter your message',
            'submit-message': 'Submit Message',
            'refresh-comments': 'Refresh',
            'no-comments': 'No messages yet',
            'message-add-success': 'Message added successfully',
            'message-add-failed': 'Message add failed',
            'please-fill-message': 'Please fill in complete message information',
            'message-delete-success': 'Message deleted successfully',
            'message-delete-failed': 'Message delete failed',
            'confirm-delete-message': 'Are you sure you want to delete this message?',
            'now-playing': 'Now Playing',
            'close': 'Close',
            'generating-audio': 'Generating audio, please wait...',
            'start-playing': 'Start playing',
            'play-failed': 'Playback failed, please try again',
            'audio-load-failed': 'Audio load failed, please try again',
            'audio-load-timeout': 'Audio load timeout, please try again',
            'about-api': 'About this API',
            'pause': 'Pause',
            'play': 'Play',
            'loading': 'Loading...'
        },
        ja: {
            title: 'MIDI 管理ページ',
            'upload-midi': 'MIDIをアップロード',
            'select-file': 'ファイルを選択',
            'upload-page': 'アップロード',
            'latest-midi': 'MIDI',
            'latest-musicxml': 'MusicXML',
            'latest-midi-header': 'MIDI アップロード',
            'latest-musicxml-header': 'MusicXML アップロード',
            'search-songs': '曲を検索',
            'latest-uploads': 'アップロード',
            'message-board': 'メッセージボード',
            'upload': 'アップロード',
            'uploader-name': 'アップローダー名',
            'delete-password': '削除パスワード',
            'upload-result': '',
            'search-placeholder': '曲名（あいまい検索 / * ランダム）',
            'search': '検索',
            'latest-uploads-header': 'アップロード',
            'refresh': '更新',
            'name': '名前',
            'uploader': 'アップローダー',
            'duration': '時間',
            'size': 'サイズ',
            'upload-time': 'アップロード時間',
            'actions': '操作',
            'confidence': '信頼度',
            'delete': '削除',
            'play': '試聴',
            'download': 'ダウンロード',
            'loading': '読み込み中...',
            'no-more-data': 'データはありません',
            'please-select-file': 'MIDIファイルを選択してください',
            'upload-success': 'アップロード完了',
            'upload-failed': 'アップロードに失敗しました',
            'please-enter-search': '検索キーワードを入力してください',
            'no-results': '結果が見つかりません',
            'search-failed': '検索に失敗しました',
            'confirm-delete': 'この音楽ファイルを削除してもよろしいですか？',
            'please-enter-delete-password': '削除パスワードを入力してください',
            'delete-success': '削除成功',
            'delete-failed': '削除に失敗しました',
            'message': 'メッセージ',
            'nickname': 'あなたのニックネーム',
            'message-content': 'メッセージを入力してください',
            'submit-message': 'メッセージを送信',
            'refresh-comments': '更新',
            'no-comments': 'メッセージはまだありません',
            'message-add-success': 'メッセージが追加されました',
            'message-add-failed': 'メッセージの追加に失敗しました',
            'please-fill-message': 'メッセージ情報をすべて入力してください',
            'message-delete-success': 'メッセージが削除されました',
            'message-delete-failed': 'メッセージの削除に失敗しました',
            'confirm-delete-message': 'このメッセージを削除してもよろしいですか？',
            'now-playing': '再生中',
            'close': '閉じる',
            'generating-audio': '音声を生成中、お待ちください...',
            'start-playing': '再生開始',
            'play-failed': '再生に失敗しました',
            'audio-load-failed': '音声の読み込みに失敗しました',
            'audio-load-timeout': '音声の読み込みがタイムアウトしました',
            'about-api': 'このAPIについて',
            'pause': '一時停止',
            'play': '再生',
            'loading': '読み込み中...'
        },
        vi: {
            title: 'Trang Quản lý MIDI',
            'upload-midi': 'Tải lên MIDI',
            'select-file': 'Chọn tệp',
            'upload-page': 'Tải lên',
            'latest-midi': 'MIDI',
            'latest-musicxml': 'MusicXML',
            'latest-midi-header': 'Tải lên MIDI',
            'latest-musicxml-header': 'Tải lên MusicXML',
            'search-songs': 'Tìm kiếm bài hát',
            'latest-uploads': 'Tải lên',
            'message-board': 'Sổ tin nhắn',
            'upload': 'Tải lên',
            'uploader-name': 'Tên người tải lên',
            'delete-password': 'Mật khẩu xóa',
            'upload-result': '',
            'search-placeholder': 'Tên bài hát (hỗ trợ mờ / * ngẫu nhiên)',
            'search': 'Tìm kiếm',
            'latest-uploads-header': 'Tải lên',
            'refresh': 'Làm mới',
            'name': 'Tên',
            'uploader': 'Người tải lên',
            'duration': 'Thời lượng',
            'size': 'Kích thước',
            'upload-time': 'Thời gian tải lên',
            'actions': 'Hành động',
            'confidence': 'Độ tin cậy',
            'delete': 'Xóa',
            'play': 'Nghe thử',
            'download': 'Tải xuống',
            'loading': 'Đang tải...',
            'no-more-data': 'Không còn dữ liệu',
            'please-select-file': 'Vui lòng chọn tệp MIDI',
            'upload-success': 'Tải lên thành công',
            'upload-failed': 'Tải lên thất bại',
            'please-enter-search': 'Vui lòng nhập từ khóa tìm kiếm',
            'no-results': 'Không tìm thấy kết quả',
            'search-failed': 'Tìm kiếm thất bại',
            'confirm-delete': 'Bạn có chắc chắn muốn xóa tệp nhạc này?',
            'please-enter-delete-password': 'Vui lòng nhập mật khẩu xóa',
            'delete-success': 'Xóa thành công',
            'delete-failed': 'Xóa thất bại',
            'message': 'Tin nhắn',
            'nickname': 'Biệt danh của bạn',
            'message-content': 'Vui lòng nhập nội dung tin nhắn',
            'submit-message': 'Gửi tin nhắn',
            'refresh-comments': 'Làm mới',
            'no-comments': 'Chưa có tin nhắn',
            'message-add-success': 'Tin nhắn đã được thêm',
            'message-add-failed': 'Thêm tin nhắn thất bại',
            'please-fill-message': 'Vui lòng điền đầy đủ thông tin tin nhắn',
            'message-delete-success': 'Tin nhắn đã được xóa',
            'message-delete-failed': 'Xóa tin nhắn thất bại',
            'confirm-delete-message': 'Bạn có chắc chắn muốn xóa tin nhắn này?',
            'now-playing': 'Đang phát',
            'close': 'Đóng',
            'generating-audio': 'Đang tạo âm thanh, vui lòng chờ...',
            'start-playing': 'Bắt đầu phát',
            'play-failed': 'Phát thất bại',
            'audio-load-failed': 'Tải âm thanh thất bại',
            'audio-load-timeout': 'Tải âm thanh hết giờ',
            'about-api': 'Về API này',
            'pause': 'Tạm dừng',
            'play': 'Phát',
            'loading': 'Đang tải...'
        },
        ko: {
            title: 'MIDI 관리 페이지',
            'upload-midi': 'MIDI 업로드',
            'select-file': '파일 선택',
            'upload-page': '업로드',
            'latest-midi': 'MIDI',
            'latest-musicxml': 'MusicXML',
            'latest-midi-header': 'MIDI 업로드',
            'latest-musicxml-header': 'MusicXML 업로드',
            'search-songs': '노래 검색',
            'latest-uploads': '업로드',
            'message-board': '메시지 보드',
            'upload': '업로드',
            'uploader-name': '업로더 이름',
            'delete-password': '삭제 비밀번호',
            'upload-result': '',
            'search-placeholder': '노래 이름 (모호 / * 랜덤 검색)',
            'search': '검색',
            'latest-uploads-header': '업로드',
            'refresh': '새로고침',
            'name': '이름',
            'uploader': '업로더',
            'duration': '시간',
            'size': '크기',
            'upload-time': '업로드 시간',
            'actions': '조작',
            'confidence': '신뢰도',
            'delete': '삭제',
            'play': '듣기',
            'download': '다운로드',
            'loading': '로딩 중...',
            'no-more-data': '더 이상 데이터 없음',
            'please-select-file': 'MIDI 파일을 선택하세요',
            'upload-success': '업로드 완료',
            'upload-failed': '업로드 실패',
            'please-enter-search': '검색 키워드를 입력하세요',
            'no-results': '결과를 찾을 수 없음',
            'search-failed': '검색 실패',
            'confirm-delete': '이 음악 파일을 삭제하시겠습니까?',
            'please-enter-delete-password': '삭제 비밀번호를 입력하세요',
            'delete-success': '삭제 성공',
            'delete-failed': '삭제 실패',
            'message': '메시지',
            'nickname': '닉네임',
            'message-content': '메시지 내용을 입력하세요',
            'submit-message': '메시지 전송',
            'refresh-comments': '새로고침',
            'no-comments': '아직 메시지가 없습니다',
            'message-add-success': '메시지 추가 성공',
            'message-add-failed': '메시지 추가 실패',
            'please-fill-message': '메시지 정보를 모두 입력하세요',
            'message-delete-success': '메시지 삭제 성공',
            'message-delete-failed': '메시지 삭제 실패',
            'confirm-delete-message': '이 메시지를 삭제하시겠습니까?',
            'now-playing': '지금 재생 중',
            'close': '닫기',
            'generating-audio': '오디오 생성 중, 잠시만 기다려주세요...',
            'start-playing': '재생 시작',
            'play-failed': '재생 실패',
            'audio-load-failed': '오디오 로딩 실패',
            'audio-load-timeout': '오디오 로딩 시간 초과',
            'about-api': '이 API에 대해',
            'pause': '일시정지',
            'play': '재생',
            'loading': '로딩 중...'
        }
    },

    // 初始化
    init() {
        // 从 localStorage 或浏览器语言获取
        const savedLang = localStorage.getItem('midi_app_lang');
        const browserLang = navigator.language || navigator.userLanguage;

        // 检测浏览器语言
        if (!savedLang) {
            const langCode = browserLang.split('-')[0].toLowerCase();
            this.currentLang = this.supportedLangs.includes(langCode) ? langCode : 'en';
        } else {
            this.currentLang = savedLang;
        }

        this.updateLanguage();
        this.updateDropdownButtons();
    },

    // 切换语言
    switch(lang) {
        if (!this.supportedLangs.includes(lang)) return;

        this.currentLang = lang;
        localStorage.setItem('midi_app_lang', lang);
        this.updateLanguage();
        this.updateDropdownButtons();
        this.updatePlayPauseText();
    },

    // 获取翻译文本
    t(key) {
        return this.translations[this.currentLang]?.[key] || key;
    },

    // 更新页面语言
    updateLanguage() {
        // 更新标题
        document.title = this.t('title');

        // 更新有 data-key 属性的元素
        document.querySelectorAll('[data-key]').forEach(element => {
            const key = element.getAttribute('data-key');
            if (this.t(key)) {
                // 处理表格标题
                if (element.tagName === 'TH') {
                    element.textContent = this.t(key);
                } else {
                    // 处理其他元素，包括按钮
                    element.textContent = this.t(key);
                }
            }
        });


        // 更新有 data-placeholder-key 属性的元素
        document.querySelectorAll('[data-placeholder-key]').forEach(element => {
            const key = element.getAttribute('data-placeholder-key');
            if (this.t(key)) {
                element.placeholder = this.t(key);
            }
        });

        // 更新所有操作按钮的翻译（重新加载翻译文本）
        this.updateAllButtons();

        // 更新当前语言按钮文本
        const langNames = {
            zh: '中文',
            en: 'English',
            ja: '日本語',
            vi: 'Tiếng Việt',
            ko: '한국어'
        };
        document.getElementById('currentLangBtn').textContent = `🌐 ${langNames[this.currentLang]}`;
    },

    // 更新按钮文本（简化版本）
    updateButtonText(key, originalText) {
        const buttons = document.querySelectorAll('button');
        buttons.forEach(button => {
            if (button.textContent.trim() === originalText) {
                button.textContent = this.t(key);
            }
        });
    },

    // 更新输入框占位符
    updatePlaceholder(key, originalText) {
        const input = document.querySelector(`input[placeholder*="${originalText.split(' ')[0]}"], textarea[placeholder*="${originalText.split(' ')[0]}"]`);
        if (input) {
            input.placeholder = this.t(key);
        }
    },

    // 更新文本内容
    updateText(key, originalText) {
        const elements = document.querySelectorAll(`th:contains("${originalText}")`);
        elements.forEach(element => {
            element.textContent = this.t(key);
        });
    },

    // 更新下拉按钮状态
    updateDropdownButtons() {
        const buttons = document.querySelectorAll('.language-dropdown button');
        buttons.forEach(button => {
            button.classList.remove('active');
            if (button.textContent.includes(this.getLangName(this.currentLang))) {
                button.classList.add('active');
            }
        });
    },

    // 获取语言名称
    getLangName(lang) {
        const names = {
            zh: '中文',
            en: 'English',
            ja: '日本語',
            vi: 'Tiếng Việt',
            ko: '한국어'
        };
        return names[lang];
    },

    // 显示/隐藏下拉菜单
    showDropdown() {
        const dropdown = document.getElementById('languageDropdown');
        dropdown.classList.toggle('show');

        // 点击外部关闭
        setTimeout(() => {
            document.addEventListener('click', this.hideDropdown.bind(this));
        }, 100);
    },

    hideDropdown(event) {
        if (!event.target.closest('.language-switcher')) {
            document.getElementById('languageDropdown').classList.remove('show');
            document.removeEventListener('click', this.hideDropdown.bind(this));
        }
    },

    // 更新播放/暂停按钮文本
    updatePlayPauseText() {
        const playPauseButton = document.getElementById('playPauseButton');
        if (playPauseButton && !playPauseButton.disabled) {
            const isPlaying = !window.audioPlayer.audio.paused;
            playPauseButton.textContent = isPlaying ? this.t('pause') : this.t('play');
        }
    },

    // 更新所有操作按钮的翻译
    updateAllButtons() {
        // 更新所有有 data-key 的按钮
        document.querySelectorAll('button[data-key]').forEach(button => {
            const key = button.getAttribute('data-key');
            if (this.t(key)) {
                button.textContent = this.t(key);
            }
        });
    }
};
