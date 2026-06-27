#!/usr/bin/env python3
"""API Key Validator - Mac Web App (Glassmorphism UI)"""

from flask import Flask, render_template_string, request, jsonify
from api_validator import ApiKeyValidator
import webbrowser
import threading
import os

app = Flask(__name__)
validator = ApiKeyValidator()

JS_CODE = r"""
function showToast(msg) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(function(){ t.classList.remove('show'); }, 2000);
}

function copyText(text) {
    navigator.clipboard.writeText(text);
    showToast('已复制: ' + text.substring(0, 40) + '...');
}

function apiCall(action, data) {
    return fetch('/api/' + action, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(data || {})
    }).then(function(r){ return r.json(); });
}

function loadUrls() {
    apiCall('urls').then(function(data) {
        var html = '';
        data.urls.forEach(function(u) {
            html += '<div class="url-chip" onclick="copyText(\'' + u.url + '\')">';
            html += '<span class="region region-' + u.region + '">' + u.region.toUpperCase() + '</span>';
            html += u.url;
            html += ' <span onclick="event.stopPropagation();removeUrl(\'' + u.region + '\')" class="url-remove">x</span>';
            html += '</div>';
        });
        document.getElementById('urlList').innerHTML = html;
    });
}

function pasteValidate() {
    var text = document.getElementById('pasteArea').value.trim();
    if (!text) return;
    apiCall('paste', {text: text}).then(function(data) {
        showToast('提取到 ' + data.count + ' 个Key');
        refreshList();
    });
}

function refreshList() {
    apiCall('list').then(function(data) {
        var keys = data.keys;
        var stats = {available: 0, rate_limited: 0, unavailable: 0, in_use: 0};
        keys.forEach(function(k){ stats[k.status] = (stats[k.status] || 0) + 1; });

        document.getElementById('stats').innerHTML =
            '<div class="stat-card stat-total"><div class="stat-num">' + keys.length + '</div><div class="stat-label">总计</div></div>' +
            '<div class="stat-card stat-available"><div class="stat-num">' + stats.available + '</div><div class="stat-label">可用</div></div>' +
            '<div class="stat-card stat-rate_limited"><div class="stat-num">' + stats.rate_limited + '</div><div class="stat-label">限流中</div></div>' +
            '<div class="stat-card stat-unavailable"><div class="stat-num">' + stats.unavailable + '</div><div class="stat-label">不可用</div></div>';

        if (!keys.length) {
            document.getElementById('keyTable').innerHTML = '<tr><td colspan="7" class="empty">暂无数据</td></tr>';
            return;
        }

        var statusLabel = {available: '可用', rate_limited: '限流中', unavailable: '不可用', in_use: '使用中'};
        var regionLabel = {sgp: '新加坡', cn: '国内', 'sgp-anthropic': '新加坡A', 'cn-anthropic': '国内A', unknown: '-'};
        var html = '';
        keys.forEach(function(k, i) {
            // 计算入库时长
            var duration = '';
            if (k.added_at) {
                var added = new Date(k.added_at);
                var now = new Date();
                var diff = Math.floor((now - added) / 1000);
                if (diff < 60) duration = diff + '秒';
                else if (diff < 3600) duration = Math.floor(diff/60) + '分钟';
                else if (diff < 86400) duration = Math.floor(diff/3600) + '小时';
                else duration = Math.floor(diff/86400) + '天';
            }
            
            // 延迟显示
            var latencyStr = k.latency > 0 ? k.latency + 'ms' : '-';
            
            var urlBtn = k.url ? '<button class="btn-sm" onclick="copyText(\'' + k.key + '\\n' + k.url + '\')">Key+URL</button>' : '';
            html += '<tr>';
            html += '<td style="color:rgba(255,255,255,0.25)">' + (i + 1) + '</td>';
            html += '<td><span class="key-text" title="' + k.key + '">' + k.key + '</span></td>';
            html += '<td><span class="region-tag region-' + k.region + '">' + (regionLabel[k.region] || k.region) + '</span></td>';
            html += '<td><span class="badge badge-' + k.status + '">' + (statusLabel[k.status] || k.status) + '</span></td>';
            html += '<td><span class="cell-time">' + latencyStr + '</span></td>';
            html += '<td><span class="cell-url" title="' + (k.url||'') + '">' + (k.url||'-') + '</span></td>';
            html += '<td><span class="cell-time">' + (k.added_at ? new Date(k.added_at).toLocaleString() : '-') + '</span></td>';
            html += '<td><span class="cell-time">' + duration + '</span></td>';
            html += '<td><button class="btn-sm" onclick="copyText(\'' + k.key + '\')">复制Key</button>' + urlBtn;
            html += '<button class="btn-sm" onclick="retestOne(\'' + k.key + '\')">重测</button>';
            html += '<button class="btn-sm btn-danger" onclick="deleteKey(\'' + k.key + '\')">删除</button></td>';
            html += '</tr>';
        });
        document.getElementById('keyTable').innerHTML = html;
    });
}

function retestOne(key) {
    apiCall('retest', {key: key}).then(function() {
        refreshList();
        showToast('重测完成');
    });
}

function retestAll() {
    apiCall('retest', {}).then(function() {
        refreshList();
        showToast('重测完成');
    });
}

function toggleAuto() {
    var on = document.getElementById('autoToggle').checked;
    apiCall('auto', {on: on, interval: 180}).then(function() {
        showToast(on ? '自动重测已开启（2-5分钟随机）' : '自动重测已关闭');
    });
}

function initApp() {
    loadUrls();
    refreshList();
    // 默认开启自动重测
    document.getElementById('autoToggle').checked = true;
    apiCall('auto', {on: true, interval: 180});
}

initApp();

function exportAll() {
    apiCall('list').then(function(data) {
        var usable = data.keys.filter(function(k){ return k.status === 'available'; });
        if (!usable.length) { showToast('没有可用的Key（不含限流）'); return; }
        var lines = usable.map(function(k){ return k.key + (k.url ? '\n' + k.url : ''); });
        copyText(lines.join('\n\n'));
        showToast('已复制 ' + usable.length + ' 个可用Key');
    });
}

function exportJson() {
    apiCall('list').then(function(data) {
        copyText(JSON.stringify(data.keys, null, 2));
        showToast('JSON已复制');
    });
}

function addUrl() {
    var url = document.getElementById('newUrl').value.trim();
    var region = document.getElementById('newRegion').value.trim();
    if (!url) return;
    if (!region) region = 'custom_' + Date.now();
    apiCall('add_url', {url: url, region: region}).then(function() {
        document.getElementById('newUrl').value = '';
        document.getElementById('newRegion').value = '';
        loadUrls();
        showToast('已添加: ' + region);
    });
}

function removeUrl(region) {
    apiCall('del_url', {region: region}).then(function() {
        loadUrls();
        showToast('已删除');
    });
}

function deleteKey(key) {
    if (!confirm('确定删除这个Key？')) return;
    apiCall('delete_key', {key: key}).then(function() {
        refreshList();
        showToast('已删除');
    });
}

function clearAll() {
    if (!confirm('确定清空所有Key？此操作不可恢复。')) return;
    apiCall('clear_all', {}).then(function(data) {
        refreshList();
        showToast('已清空 ' + data.count + ' 个Key');
    });
}

function clearUnavailable() {
    if (!confirm('确定清除所有不可用的Key？')) return;
    apiCall('clear_unavailable', {}).then(function(data) {
        refreshList();
        showToast('已清除 ' + data.count + ' 个不可用Key');
    });
}
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API Key 管理器</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'SF Pro Display',sans-serif;min-height:100vh;background:linear-gradient(135deg,#0c0c1d 0%,#1a1a3e 25%,#0d1b2a 50%,#1b2838 75%,#0c0c1d 100%);color:#e0e0e0;padding:30px}
body::before{content:'';position:fixed;top:-50%;left:-50%;width:200%;height:200%;background:radial-gradient(circle at 20% 50%,rgba(120,80,200,0.08) 0%,transparent 50%),radial-gradient(circle at 80% 20%,rgba(60,140,220,0.06) 0%,transparent 50%),radial-gradient(circle at 50% 80%,rgba(200,60,100,0.05) 0%,transparent 50%);pointer-events:none;z-index:0}
.container{max-width:1200px;margin:0 auto;position:relative;z-index:1}
h1{text-align:center;font-size:28px;font-weight:700;letter-spacing:2px;margin-bottom:30px;background:linear-gradient(135deg,#a78bfa,#60a5fa,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.glass{background:rgba(255,255,255,0.04);backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.08);border-radius:16px;padding:24px;margin-bottom:20px;box-shadow:0 8px 32px rgba(0,0,0,0.3),inset 0 1px 0 rgba(255,255,255,0.05);transition:all 0.3s}
.glass:hover{border-color:rgba(255,255,255,0.12);box-shadow:0 12px 40px rgba(0,0,0,0.4),inset 0 1px 0 rgba(255,255,255,0.08)}
.glass h2{font-size:14px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:rgba(255,255,255,0.5);margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid rgba(255,255,255,0.06)}
.url-grid{display:flex;gap:10px;flex-wrap:wrap}
.url-chip{background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.2);padding:8px 16px;border-radius:10px;font-size:13px;cursor:pointer;transition:all 0.2s;font-family:'SF Mono',monospace}
.url-chip:hover{background:rgba(99,102,241,0.25);border-color:rgba(99,102,241,0.4);transform:translateY(-1px)}
.url-chip .region{font-weight:700;margin-right:8px;font-family:-apple-system,sans-serif}
.url-remove{margin-left:8px;cursor:pointer;opacity:0.4;font-size:11px}
.url-remove:hover{opacity:1}
.region-sgp{color:#818cf8}.region-cn{color:#34d399}.region-unknown{color:rgba(255,255,255,0.3)}
textarea{width:100%;height:120px;background:rgba(0,0,0,0.2);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#e0e0e0;padding:14px;font-family:'SF Mono',monospace;font-size:13px;resize:vertical;transition:border-color 0.2s}
textarea:focus{outline:none;border-color:rgba(139,92,246,0.5);box-shadow:0 0 0 3px rgba(139,92,246,0.1)}
textarea::placeholder{color:rgba(255,255,255,0.2)}
input[type=text]{background:rgba(0,0,0,0.2);border:1px solid rgba(255,255,255,0.08);border-radius:10px;color:#e0e0e0;padding:10px 14px;font-family:'SF Mono',monospace;font-size:13px;transition:border-color 0.2s}
input[type=text]:focus{outline:none;border-color:rgba(139,92,246,0.5)}
input[type=text]::placeholder{color:rgba(255,255,255,0.2)}
.btn-row{display:flex;gap:10px;margin-top:14px;flex-wrap:wrap;align-items:center}
.btn{padding:10px 22px;border:none;border-radius:10px;cursor:pointer;font-size:13px;font-weight:600;letter-spacing:0.5px;transition:all 0.2s}
.btn:active{transform:scale(0.97)}
.btn-primary{background:linear-gradient(135deg,rgba(139,92,246,0.4),rgba(99,102,241,0.4));border:1px solid rgba(139,92,246,0.3);color:#c4b5fd}
.btn-primary:hover{background:linear-gradient(135deg,rgba(139,92,246,0.6),rgba(99,102,241,0.6));color:#fff}
.btn-success{background:rgba(52,211,153,0.15);border:1px solid rgba(52,211,153,0.25);color:#6ee7b7}
.btn-success:hover{background:rgba(52,211,153,0.3);color:#fff}
.btn-warning{background:rgba(251,191,36,0.15);border:1px solid rgba(251,191,36,0.25);color:#fcd34d}
.btn-warning:hover{background:rgba(251,191,36,0.3);color:#fff}
.btn-ghost{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);color:rgba(255,255,255,0.5)}
.btn-ghost:hover{background:rgba(255,255,255,0.08);color:rgba(255,255,255,0.8)}
.control-row{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.toggle-wrap{display:flex;align-items:center;gap:12px}
.toggle{position:relative;width:44px;height:24px}
.toggle input{opacity:0;width:0;height:0}
.toggle .track{position:absolute;cursor:pointer;top:0;left:0;right:0;bottom:0;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);border-radius:24px;transition:0.3s}
.toggle .track::before{content:"";position:absolute;height:18px;width:18px;left:2px;bottom:2px;background:rgba(255,255,255,0.4);border-radius:50%;transition:0.3s}
.toggle input:checked+.track{background:rgba(52,211,153,0.25);border-color:rgba(52,211,153,0.4)}
.toggle input:checked+.track::before{transform:translateX(20px);background:#34d399}
.toggle-label{font-size:13px;color:rgba(255,255,255,0.5)}
.stats-grid{display:flex;gap:12px;flex-wrap:wrap}
.stat-card{flex:1;min-width:100px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;padding:16px;text-align:center}
.stat-num{font-size:28px;font-weight:700;margin-bottom:4px}
.stat-label{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:rgba(255,255,255,0.3)}
.stat-available .stat-num{color:#34d399}
.stat-rate_limited .stat-num{color:#fbbf24}
.stat-unavailable .stat-num{color:#f87171}
.stat-total .stat-num{color:#60a5fa}
.table-wrap{overflow-x:auto}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:12px 14px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:rgba(255,255,255,0.3);border-bottom:1px solid rgba(255,255,255,0.06)}
td{padding:12px 14px;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.03);vertical-align:middle}
tr{transition:background 0.15s}
tr:hover{background:rgba(255,255,255,0.02)}
.key-text{font-family:'SF Mono',monospace;font-size:12px;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:rgba(255,255,255,0.7)}
.badge{display:inline-block;padding:3px 10px;border-radius:8px;font-size:11px;font-weight:600;letter-spacing:0.5px}
.badge-available{background:rgba(52,211,153,0.12);border:1px solid rgba(52,211,153,0.2);color:#6ee7b7}
.badge-rate_limited{background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.2);color:#fcd34d}
.badge-unavailable{background:rgba(248,113,113,0.12);border:1px solid rgba(248,113,113,0.2);color:#fca5a5}
.badge-in_use{background:rgba(96,165,250,0.12);border:1px solid rgba(96,165,250,0.2);color:#93c5fd}
.region-tag{font-size:12px;font-weight:600}
.cell-url{font-size:11px;font-family:'SF Mono',monospace;color:rgba(255,255,255,0.35);max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.cell-time{font-size:11px;color:rgba(255,255,255,0.3)}
.btn-sm{padding:4px 10px;font-size:11px;border-radius:6px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);color:rgba(255,255,255,0.5);cursor:pointer;transition:all 0.15s;margin:2px}
.btn-sm:hover{background:rgba(255,255,255,0.1);color:#fff}
.btn-danger{background:rgba(248,113,113,0.12);border-color:rgba(248,113,113,0.2);color:#fca5a5}
.btn-danger:hover{background:rgba(248,113,113,0.3);color:#fff}
.toast{position:fixed;bottom:30px;right:30px;background:rgba(52,211,153,0.15);backdrop-filter:blur(20px);border:1px solid rgba(52,211,153,0.3);color:#6ee7b7;padding:12px 24px;border-radius:12px;font-size:13px;font-weight:500;display:none;z-index:999}
.toast.show{display:block;animation:slideUp 0.3s}
@keyframes slideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
.empty{text-align:center;padding:40px;color:rgba(255,255,255,0.15);font-size:14px}
.url-input-row{display:flex;gap:10px;margin-top:14px}
.url-input-row input:first-child{flex:1}
.url-input-row input:nth-child(2){width:120px}
</style>
</head>
<body>
<div class="container">
<h1>API KEY 管理器</h1>

<div class="glass">
<h2>接口端点</h2>
<div class="url-grid" id="urlList"></div>
<div class="url-input-row">
<input type="text" id="newUrl" placeholder="输入新的 Base URL，如 https://xxx.com/v1">
<input type="text" id="newRegion" placeholder="区域名（可选）">
<button class="btn btn-primary" onclick="addUrl()">添加</button>
</div>
</div>

<div class="glass">
<h2>粘贴验证</h2>
<textarea id="pasteArea" placeholder="粘贴杂乱文本... 支持 tp-xxx、sk-xxx、Base64编码、中文干扰字符"></textarea>
<div class="btn-row">
<button class="btn btn-primary" onclick="pasteValidate()">提取并验证</button>
<button class="btn btn-ghost" onclick="document.getElementById('pasteArea').value=''">清空</button>
</div>
</div>

<div class="glass">
<h2>测试控制</h2>
<div class="control-row">
<div class="toggle-wrap">
<label class="toggle">
<input type="checkbox" id="autoToggle" onchange="toggleAuto()" checked>
<span class="track"></span>
</label>
<span class="toggle-label">自动重测所有Key（2-5分钟随机）</span>
</div>
<button class="btn btn-warning" onclick="retestAll()">立即重测全部</button>
<button class="btn btn-ghost" onclick="refreshList()">刷新列表</button>
</div>
</div>

<div class="glass">
<h2>统计</h2>
<div class="stats-grid" id="stats"></div>
</div>

<div class="glass">
<h2>Key 列表</h2>
<div class="table-wrap">
<table>
<thead>
<tr><th>#</th><th>Key</th><th>区域</th><th>状态</th><th>延迟</th><th>URL</th><th>加入时间</th><th>入库时长</th><th>操作</th></tr>
</thead>
<tbody id="keyTable">
<tr><td colspan="7" class="empty">暂无数据</td></tr>
</tbody>
</table>
</div>
</div>

<div class="glass">
<h2>导出</h2>
<div class="btn-row">
<button class="btn btn-success" onclick="exportAll()">复制全部可用 Key+URL</button>
<button class="btn btn-ghost" onclick="exportJson()">复制 JSON</button>
<button class="btn btn-warning" onclick="clearUnavailable()">清除不可用Key</button>
<button class="btn btn-warning" onclick="clearAll()" style="margin-left:auto">清空所有Key</button>
</div>
</div>

</div>
<div class="toast" id="toast"></div>
<script>""" + JS_CODE + """</script>
</body>
</html>"""


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/urls', methods=['POST'])
def api_urls():
    return jsonify({"urls": [{"region": r, "url": u} for r, u in validator.urls.items()]})

@app.route('/api/paste', methods=['POST'])
def api_paste():
    text = request.json.get('text', '')
    keys, urls = validator.clean_text(text)
    results = [validator.validate(key) for key in keys]
    return jsonify({"count": len(results), "results": [r.__dict__ for r in results]})

@app.route('/api/list', methods=['POST'])
def api_list():
    return jsonify({"keys": [v.__dict__ for v in validator.keys.values()]})

@app.route('/api/retest', methods=['POST'])
def api_retest():
    key = request.json.get('key')
    validator.retest(key) if key else validator.retest()
    return jsonify({"ok": True})

@app.route('/api/auto', methods=['POST'])
def api_auto():
    on = request.json.get('on', False)
    interval = request.json.get('interval', 60)
    if on:
        validator.auto_retest(interval)
    else:
        validator.stop_auto_retest()
    return jsonify({"ok": True, "on": on})

@app.route('/api/add_url', methods=['POST'])
def api_add_url():
    url = request.json.get('url', '').strip()
    region = request.json.get('region', '').strip()
    if url and region:
        validator.urls[region] = url
    return jsonify({"ok": True})

@app.route('/api/del_url', methods=['POST'])
def api_del_url():
    region = request.json.get('region', '').strip()
    if region in validator.urls:
        del validator.urls[region]
    return jsonify({"ok": True})

@app.route('/api/delete_key', methods=['POST'])
def api_delete_key():
    key = request.json.get('key', '').strip()
    ok = validator.delete_key(key)
    return jsonify({"ok": ok})

@app.route('/api/clear_all', methods=['POST'])
def api_clear_all():
    count = validator.clear_all()
    return jsonify({"ok": True, "count": count})

@app.route('/api/clear_unavailable', methods=['POST'])
def api_clear_unavailable():
    count = validator.clear_unavailable()
    return jsonify({"ok": True, "count": count})


def open_browser():
    webbrowser.open('http://localhost:8899')

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("  API Key 管理器")
    print("  http://localhost:8899")
    print("=" * 50 + "\n")
    threading.Timer(1.5, open_browser).start()
    app.run(host='127.0.0.1', port=8899, debug=False)
