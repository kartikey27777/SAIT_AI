(function () {
    'use strict';

    var API_BASE = 'http://localhost:8083';
    var API_KEY = '';

    var els = {
        sidebar: document.getElementById('sidebar'),
        sidebarToggle: document.getElementById('sidebarToggle'),
        newChatBtn: document.getElementById('newChatBtn'),
        docList: document.getElementById('docList'),
        fileInput: document.getElementById('fileInput'),
        tagInput: document.getElementById('tagInput'),
        statusPill: document.getElementById('statusPill'),
        chatArea: document.getElementById('chatArea'),
        welcome: document.getElementById('welcome'),
        messages: document.getElementById('messages'),
        chatInput: document.getElementById('chatInput'),
        sendBtn: document.getElementById('sendBtn'),
        activeDocRow: document.getElementById('activeDocRow'),
        activeDocName: document.getElementById('activeDocName'),
        clearDocBtn: document.getElementById('clearDocBtn'),
        toast: document.getElementById('toast'),
        overlay: document.getElementById('uploadOverlay'),
        uploadStatusText: document.getElementById('uploadStatusText'),
        chips: document.querySelectorAll('.welcome-chips .chip'),
        websiteMode: document.getElementById('websiteMode'),
        websiteToggle: document.querySelector('.website-toggle'),
        websiteSyncBtn: document.getElementById('websiteSyncBtn'),
        websiteSyncStatus: document.getElementById('websiteSyncStatus'),
        historyList: document.getElementById('historyList')
    };

    var activeDoc = null;
    var streaming = false;
    var toastTimer = null;
    var websiteMode = localStorage.getItem('saitWebsiteMode') === '1';
    var currentSession = null;
    var loadedSession = null;

    function apiHeaders(extra) {
        var h = { 'Content-Type': 'application/json' };
        if (API_KEY) h['X-API-Key'] = API_KEY;
        return extend(h, extra || {});
    }

    function extend(a, b) {
        for (var k in b) if (b.hasOwnProperty(k)) a[k] = b[k];
        return a;
    }

    function toast(msg, isError) {
        els.toast.textContent = msg;
        els.toast.className = 'toast' + (isError ? ' error' : '');
        clearTimeout(toastTimer);
        toastTimer = setTimeout(function () {
            els.toast.className = 'toast hidden';
        }, 3200);
    }

    function showOverlay(text) {
        els.uploadStatusText.textContent = text || 'Working…';
        els.overlay.classList.remove('hidden');
    }

    function hideOverlay() {
        els.overlay.classList.add('hidden');
    }

    function checkWebsiteStatus() {
        fetch(API_BASE + '/website/status')
            .then(function (r) { return r.json(); })
            .then(function (s) {
                var el = els.websiteSyncStatus;
                if (s.status === 'done') {
                    var pages = (s.pages || []);
                    el.textContent = 'College data: ' + pages.length + ' pages ✓';
                    el.className = 'website-sync-status ok';
                    els.websiteSyncBtn.disabled = false;
                } else if (s.status === 'running') {
                    el.textContent = 'Syncing: ' + (s.progress || '…') + '…';
                    el.className = 'website-sync-status';
                    els.websiteSyncBtn.disabled = true;
                } else if (s.status === 'error') {
                    el.textContent = 'College sync failed';
                    el.className = 'website-sync-status bad';
                    els.websiteSyncBtn.disabled = false;
                } else {
                    el.textContent = 'College data: not loaded';
                    el.className = 'website-sync-status';
                    els.websiteSyncBtn.disabled = false;
                }
            })
            .catch(function () {
                els.websiteSyncStatus.textContent = 'College data: offline';
                els.websiteSyncStatus.className = 'website-sync-status bad';
            });
    }

    function startWebsiteSync() {
        els.websiteSyncStatus.textContent = 'Syncing…';
        els.websiteSyncBtn.disabled = true;
        fetch(API_BASE + '/website/sync', { method: 'POST', headers: apiHeaders() })
            .then(function () { els.websiteSyncStatus.textContent = 'Waiting for backend…'; })
            .then(checkWebsiteStatus)
            .catch(function (e) {
                els.websiteSyncStatus.textContent = 'Sync failed: ' + e.message;
                els.websiteSyncStatus.className = 'website-sync-status bad';
                els.websiteSyncBtn.disabled = false;
            });
    }

    function applyWebsiteMode() {
        websiteMode = els.websiteMode.checked;
        localStorage.setItem('saitWebsiteMode', websiteMode ? '1' : '0');
        els.websiteToggle.classList.toggle('on', websiteMode);
        els.chatInput.placeholder = websiteMode ? 'Ask about the college (courses, fees, admissions, placements)…' : 'Message SAIT AI…';
        if (websiteMode) {
            activeDoc = null;
            els.activeDocRow.classList.add('hidden');
            loadDocs();
        }
    }

    function checkStatus() {
        fetch(API_BASE + '/', { timeout: 5000 })
            .then(function (r) {
                if (r.ok) {
                    els.statusPill.className = 'status-pill ok';
                    els.statusPill.innerHTML = '<span class="dot"></span>Connected';
                } else {
                    els.statusPill.className = 'status-pill bad';
                    els.statusPill.innerHTML = '<span class="dot"></span>Backend error';
                }
            })
            .catch(function () {
                els.statusPill.className = 'status-pill bad';
                els.statusPill.innerHTML = '<span class="dot"></span>Offline';
            });
    }

    function fileIcon(name) {
        var ext = name.split('.').pop().toLowerCase();
        if (ext === 'pdf') return '📕';
        if (ext === 'docx' || ext === 'doc') return '📘';
        if (ext === 'txt' || ext === 'md') return '📄';
        if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp'].indexOf(ext) > -1) return '🖼️';
        return '📁';
    }

    function loadDocs() {
        fetch(API_BASE + '/documents')
            .then(function (r) { return r.json(); })
            .then(function (j) {
                renderDocs(j.documents || []);
            })
            .catch(function () {
                els.docList.innerHTML = '<div class="doc-empty"><div class="empty-icon">⚠️</div>' +
                    '<span>Cannot reach backend.<br>Is it running on ' + API_BASE + '?</span></div>';
            });
    }

    function renderDocs(docs) {
        docs = (docs || []).filter(function (d) {
            return (d.tags || []).indexOf('website') === -1;
        });

        var totalChunks = 0;
        (docs || []).forEach(function (d) { totalChunks += d.chunks || 0; });

        if (!docs || docs.length === 0) {
            els.docList.innerHTML = '<div class="doc-empty"><div class="empty-icon">📚</div>' +
                '<span>No documents yet.<br>Upload a PDF and SAIT AI will answer from it.</span></div>';
            return;
        }

        var card = document.createElement('div');
        card.className = 'kb-card';
        card.innerHTML =
            '<div class="kb-info"><div class="kb-title">📚 Knowledge Base</div>' +
            '<div class="kb-sub">' + docs.length + ' document(s) indexed</div>' +
            '<div class="kb-sub">' + totalChunks + ' chunks stored locally</div></div>' +
            '<div class="kb-badge">Auto</div>';
        els.docList.innerHTML = '';
        els.docList.appendChild(card);
    }

    function deleteDoc(fileName) {
        if (!confirm('Delete "' + fileName + '"?')) return;
        fetch(API_BASE + '/documents/' + encodeURIComponent(fileName), {
            method: 'DELETE',
            headers: apiHeaders()
        })
            .then(function () {
                if (activeDoc === fileName) {
                    activeDoc = null;
                    els.activeDocRow.classList.add('hidden');
                }
                toast('Document deleted');
                loadDocs();
            })
            .catch(function (e) {
                toast('Failed to delete: ' + e.message, true);
            });
    }

    function loadHistoryList() {
        fetch(API_BASE + '/chat/sessions')
            .then(function (r) { return r.json(); })
            .then(function (j) {
                renderHistoryList(j.sessions || []);
            })
            .catch(function () {
                els.historyList.innerHTML = '<div class="doc-empty"><span>Cannot reach backend.</span></div>';
            });
    }

    function timeAgo(iso) {
        var then = new Date(iso).getTime();
        var diff = Date.now() - then;
        if (diff < 0) return 'just now';
        var mins = Math.floor(diff / 60000);
        if (mins < 1) return 'just now';
        if (mins < 60) return mins + 'm ago';
        var hrs = Math.floor(mins / 60);
        if (hrs < 24) return hrs + 'h ago';
        return Math.floor(hrs / 24) + 'd ago';
    }

    function renderHistoryList(sessions) {
        if (!sessions || sessions.length === 0) {
            els.historyList.innerHTML = '<div class="doc-empty"><span>No chats yet.</span></div>';
            return;
        }
        els.historyList.innerHTML = '';
        sessions.forEach(function (s) {
            var item = document.createElement('div');
            item.className = 'history-item' + (loadedSession === s.session_id ? ' active' : '');

            var info = document.createElement('div');
            info.className = 'history-info';

            var title = document.createElement('div');
            title.className = 'history-title';
            title.textContent = s.title || 'Chat';
            title.title = s.title || 'Chat';

            var meta = document.createElement('div');
            meta.className = 'history-meta';
            meta.textContent = timeAgo(s.last_message);

            info.appendChild(title);
            info.appendChild(meta);

            var del = document.createElement('button');
            del.className = 'history-delete';
            del.textContent = '✕';
            del.title = 'Delete chat';
            del.addEventListener('click', function (ev) {
                ev.stopPropagation();
                deleteSession(s.session_id);
            });

            item.addEventListener('click', function () {
                loadSession(s.session_id);
            });

            item.appendChild(info);
            item.appendChild(del);
            els.historyList.appendChild(item);
        });
    }

    function loadSession(sessionId) {
        fetch(API_BASE + '/chat/history/' + encodeURIComponent(sessionId))
            .then(function (r) { return r.json(); })
            .then(function (j) {
                currentSession = sessionId;
                loadedSession = sessionId;
                els.messages.innerHTML = '';
                els.welcome.style.display = 'none';
                (j.messages || []).forEach(function (m) {
                    if (m.role === 'user') {
                        addMessage('user', m.content);
                    } else if (m.role === 'assistant') {
                        var bubble = addMessage('ai', '');
                        renderAnswer(bubble, m.content, null);
                    }
                });
                renderHistoryList([]);
                loadHistoryList();
                scrollToBottom();
            })
            .catch(function (e) {
                toast('Failed to load chat: ' + e.message, true);
            });
    }

    function deleteSession(sessionId) {
        if (!confirm('Delete this chat?')) return;
        fetch(API_BASE + '/chat/session/' + encodeURIComponent(sessionId), {
            method: 'DELETE',
            headers: apiHeaders()
        })
            .then(function () {
                if (currentSession === sessionId) {
                    currentSession = null;
                    loadedSession = null;
                }
                els.messages.innerHTML = '';
                els.welcome.style.display = 'block';
                loadHistoryList();
            })
            .catch(function (e) {
                toast('Failed to delete chat: ' + e.message, true);
            });
    }

    function handleFiles(files) {
        var tags = els.tagInput.value.trim();
        var total = files.length;
        if (!total) return;

        var done = 0;
        showOverlay('Uploading…');
        Array.prototype.forEach.call(files, function (file) {
            var fd = new FormData();
            fd.append('file', file);
            if (tags) fd.append('tags', tags);

            fetch(API_BASE + '/upload', {
                method: 'POST',
                body: fd,
                headers: API_KEY ? { 'X-API-Key': API_KEY } : {}
            })
                .then(function (r) { return r.json(); })
                .then(function (j) {
                    if (j.error) throw new Error(j.error);
                    els.uploadStatusText.textContent = 'Processing ' + file.name + '…';
                    return pollStatus(file.name);
                })
                .then(function () {
                    done++;
                    if (done >= total) {
                        hideOverlay();
                        toast('Upload complete');
                        loadDocs();
                    }
                })
                .catch(function (err) {
                    done++;
                    toast('Upload failed: ' + err.message, true);
                    if (done >= total) hideOverlay();
                });
        });
        els.fileInput.value = '';
    }

    function pollStatus(name) {
        return new Promise(function (resolve, reject) {
            var tries = 0;
            (function tick() {
                fetch(API_BASE + '/upload/status/' + encodeURIComponent(name))
                    .then(function (r) { return r.json(); })
                    .then(function (s) {
                        tries++;
                        if (s.status === 'done') {
                            resolve();
                        } else if (s.status === 'error') {
                            reject(new Error(s.error || 'processing failed'));
                        } else {
                            if (tries % 3 === 0) els.uploadStatusText.textContent = 'Still processing ' + name + '…';
                            setTimeout(tick, 2000);
                        }
                    })
                    .catch(function () {
                        if (++tries > 15) reject(new Error('status timeout'));
                        else setTimeout(tick, 2000);
                    });
            })();
        });
    }

    function addMessage(role, text) {
        els.welcome.style.display = 'none';

        var msg = document.createElement('div');
        msg.className = 'msg msg-' + role;

        var avatarWrap = document.createElement('div');
        avatarWrap.className = 'msg-avatar-wrap';
        if (role === 'ai') {
            var img = document.createElement('img');
            img.className = 'msg-avatar';
            img.src = 'logo.png';
            img.alt = 'SAIT AI';
            avatarWrap.appendChild(img);
        } else {
            avatarWrap.textContent = '👤';
        }

        var bubble = document.createElement('div');
        bubble.className = 'msg-bubble';
        bubble.textContent = text !== undefined ? text : '';

        msg.appendChild(avatarWrap);
        msg.appendChild(bubble);
        els.messages.appendChild(msg);
        scrollToBottom();
        return bubble;
    }

    function scrollToBottom() {
        els.chatArea.scrollTop = els.chatArea.scrollHeight;
    }

    function escapeHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function renderInline(text) {
        return escapeHtml(text)
            .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.+?)\*/g, '<em>$1</em>')
            .replace(/`([^`]+)`/g, '<code>$1</code>');
    }

    function renderAnswer(bubble, rawText, sources) {
        var html = '';
        var lines = rawText.split('\n');
        var inList = false;
        var inCode = false;
        var listType = 'ul';

        lines.forEach(function (line) {
            var t = line.trim();

            if (t.indexOf('```') === 0) {
                if (!inCode) {
                    inCode = true;
                    html += '<pre><code>';
                } else {
                    inCode = false;
                    html += '</code></pre>\n';
                }
                return;
            }
            if (inCode) {
                html += escapeHtml(line) + '\n';
                return;
            }

            var ol = t.match(/^\d+[.)]\s/);
            if (/^[-*•]\s/.test(t)) {
                if (!inList) { html += '<ul>'; inList = true; listType = 'ul'; }
                html += '<li>' + renderInline(t.replace(/^[-*•]\s/, '')) + '</li>';
                return;
            }
            if (ol) {
                if (!inList) { html += '<ol>'; inList = true; listType = 'ol'; }
                html += '<li>' + renderInline(t.replace(/^\d+[.)]\s/, '')) + '</li>';
                return;
            }
            if (inList) { html += '</' + listType + '>'; inList = false; }

            var heading = t.match(/^(#{1,4})\s/);
            if (heading) {
                var lvl = heading[1].length;
                html += '<h' + lvl + '>' + renderInline(t.replace(/^#+\s/, '')) + '</h' + lvl + '>';
                return;
            }
            if (t === '') {
                html += '<br>';
                return;
            }
            html += '<p>' + renderInline(line) + '</p>';
        });

        if (inList) html += '</' + listType + '>';
        if (inCode) html += '</code></pre>';

        bubble.style.whiteSpace = 'normal';
        bubble.innerHTML = html;

        if (sources && sources.length) {
            var sbox = document.createElement('div');
            sbox.className = 'sources-box';
            var st = document.createElement('div');
            st.className = 'sources-title';
            st.textContent = 'Sources';
            sbox.appendChild(st);
            var seen = {};
            sources.forEach(function (s) {
                var fn = s.file_name || s || '';
                if (!fn || seen[fn]) return;
                seen[fn] = 1;
                var si = document.createElement('div');
                si.className = 'src-item';
                var label = '📄 ' + fn;
                if (s.chunk_id !== undefined) label += ' · part ' + (s.chunk_id + 1);
                si.textContent = label;
                sbox.appendChild(si);
            });
            bubble.appendChild(sbox);
        }
        scrollToBottom();
    }

    function addTypingIndicator() {
        var bubble = addMessage('ai', '');
        var dots = document.createElement('span');
        dots.className = 'typing-dots';
        dots.innerHTML = '<span></span><span></span><span></span>';
        bubble.appendChild(dots);
        scrollToBottom();
        return bubble;
    }

    function sendMessage(question) {
        if (streaming) return;
        var q = (question !== undefined ? String(question) : els.chatInput.value).trim();
        if (!q) return;

        addMessage('user', q);
        els.chatInput.value = '';
        autoResize();
        els.sendBtn.disabled = true;

        var bubble = addTypingIndicator();
        streaming = true;

        var body = { question: q };
        if (currentSession) body.session_id = currentSession;
        if (websiteMode) {
            body.tags = ['website'];
        } else {
            body.exclude_tags = ['website'];
        }

        fetch(API_BASE + '/chat/stream', {
            method: 'POST',
            headers: apiHeaders(),
            body: JSON.stringify(body)
        })
            .then(function (r) {
                if (!r.ok || !r.body) throw new Error('HTTP ' + r.status);
                var sid = r.headers.get('X-Session-Id');
                if (sid) currentSession = sid;

                var reader = r.body.getReader();
                var decoder = new TextDecoder();
                var full = '';
                var sources = [];
                var buffer = '';

                function pump() {
                    return reader.read().then(function (res) {
                        if (res.done) {
                            buffer += decoder.decode();
                            if (!buffer.trim()) {
                                finalize(full, sources);
                                return;
                            }
                            processLines(buffer);
                            finalize(full, sources);
                            return;
                        }
                        buffer += decoder.decode(res.value, { stream: true });
                        processLines(buffer);
                        return pump();
                    });
                }

                function processLines(buff) {
                    var lines = buff.split('\n');
                    buffer = lines.pop();
                    lines.forEach(function (line) {
                        line = line.trim();
                        if (!line) return;
                        try {
                            var obj = JSON.parse(line);
                            if (obj.t === 's') {
                                sources = obj.sources || [];
                            } else if (obj.t === 't' && obj.c !== undefined) {
                                full += obj.c;
                                bubble.textContent = full;
                                scrollToBottom();
                            }
                        } catch (e) { /* ignore partial lines */ }
                    });
                }

                return pump();
            })
            .catch(function (e) {
                streaming = false;
                els.sendBtn.disabled = false;
                bubble.textContent = '';
                renderAnswer(bubble, '⚠️ Sorry, something went wrong:\n' + e.message, null);
            });

        function finalize(full, sources) {
            streaming = false;
            els.sendBtn.disabled = false;
            if (!full || !full.trim()) {
                bubble.textContent = '⚠️ No response received.';
            } else {
                renderAnswer(bubble, full, sources);
            }
            checkStatus();
            loadHistoryList();
        }
    }

    function autoResize() {
        els.chatInput.style.height = 'auto';
        els.chatInput.style.height = Math.min(els.chatInput.scrollHeight, 140) + 'px';
    }

    els.sendBtn.addEventListener('click', function () { sendMessage(); });

    els.chatInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    els.chatInput.addEventListener('input', autoResize);

    els.newChatBtn.addEventListener('click', function () {
        els.messages.innerHTML = '';
        els.welcome.style.display = 'block';
        els.chatInput.focus();
        currentSession = null;
        loadedSession = null;
        loadHistoryList();
    });

    els.sidebarToggle.addEventListener('click', function () {
        els.sidebar.classList.toggle('hidden-sidebar');
    });

    els.clearDocBtn.addEventListener('click', function () {
        activeDoc = null;
        els.activeDocRow.classList.add('hidden');
        loadDocs();
    });

    els.fileInput.addEventListener('change', function () {
        handleFiles(els.fileInput.files);
    });

    Array.prototype.forEach.call(els.chips, function (chip) {
        chip.addEventListener('click', function () {
            els.chatInput.value = chip.getAttribute('data-prompt') || chip.textContent.trim();
            autoResize();
            els.chatInput.focus();
        });
    });

    document.getElementById('uploadOverlay').addEventListener('click', function () {
        hideOverlay();
    });

    els.websiteMode.addEventListener('change', applyWebsiteMode);
    els.websiteSyncBtn.addEventListener('click', startWebsiteSync);

    els.websiteMode.checked = websiteMode;
    applyWebsiteMode();
    checkStatus();
    checkWebsiteStatus();
    loadDocs();
    loadHistoryList();
    setInterval(checkStatus, 20000);
    setInterval(checkWebsiteStatus, 15000);
})();