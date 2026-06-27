#!/usr/bin/env python3
"""API Key Validator - Mac Web App (Glassmorphism UI)"""

from flask import Flask, render_template_string, request, jsonify
from api_validator import ApiKeyValidator, ApiKeyInfo
from dataclasses import asdict
from datetime import datetime
import threading
import os
import requests

app = Flask(__name__)
validator = ApiKeyValidator()

JS_CODE = r"""
// Loading状态管理
function showLoading(msg) {
    var overlay = document.getElementById('loadingOverlay');
    var text = document.getElementById('loadingText');
    text.textContent = msg || '处理中...';
    overlay.style.display = 'flex';
    // 点击遮罩可关闭
    overlay.onclick = function() {
        overlay.style.display = 'none';
    };
}

function hideLoading() {
    document.getElementById('loadingOverlay').style.display = 'none';
}

function showToast(msg, type) {
    var t = document.getElementById('toast');
    t.textContent = msg;
    t.className = 'toast show';
    if (type === 'error') t.style.borderColor = 'rgba(248,113,113,0.5)';
    else if (type === 'success') t.style.borderColor = 'rgba(52,211,153,0.5)';
    else t.style.borderColor = 'rgba(96,165,250,0.5)';
    setTimeout(function(){ t.classList.remove('show'); }, 3000);
}

function copyText(text) {
    navigator.clipboard.writeText(text);
    showToast('已复制: ' + text.substring(0, 40) + '...', 'success');
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
    if (!text) { showToast('请粘贴内容', 'error'); return; }
    
    // 显示提示
    showToast('正在提取并验证Key...', 'info');
    
    apiCall('paste', {text: text}).then(function(data) {
        // 在屏幕中间显示结果
        showResultModal(data);
        refreshList();
    }).catch(function() {
        showToast('验证失败', 'error');
    });
}

function showResultModal(data) {
    var modal = document.getElementById('resultModal');
    var content = document.getElementById('resultContent');
    
    // 统计各状态数量
    var stats = {available: 0, rate_limited: 0, unavailable: 0};
    if (data.results && data.results.length > 0) {
        data.results.forEach(function(r) {
            if (stats[r.status] !== undefined) stats[r.status]++;
        });
    }
    
    var html = '<div class="result-header">提取完成</div>';
    html += '<div class="result-count">共提取 ' + data.count + ' 个Key</div>';
    html += '<div class="result-stats">';
    html += '<span class="stat-success">可用: ' + stats.available + '</span>';
    html += '<span class="stat-warning">限流: ' + stats.rate_limited + '</span>';
    html += '<span class="stat-error">不可用: ' + stats.unavailable + '</span>';
    html += '</div>';
    
    if (data.results && data.results.length > 0) {
        html += '<div class="result-list">';
        data.results.forEach(function(r, i) {
            var statusClass = r.status === 'available' ? 'success' : (r.status === 'rate_limited' ? 'warning' : 'error');
            var statusText = r.status === 'available' ? '可用' : (r.status === 'rate_limited' ? '限流' : '不可用');
            html += '<div class="result-item ' + statusClass + '">';
            html += '<span class="result-key">' + r.key.substring(0, 20) + '...</span>';
            html += '<span class="result-status">' + statusText + '</span>';
            html += '</div>';
        });
        html += '</div>';
    }
    
    html += '<button class="btn btn-primary" onclick="closeResultModal()" style="margin-top:15px;width:100%">确定</button>';
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

function closeResultModal() {
    document.getElementById('resultModal').style.display = 'none';
}

function showKeyDetail(key) {
    apiCall('list').then(function(data) {
        var keys = data.keys;
        var keyInfo = null;
        keys.forEach(function(k) {
            if (k.key === key) keyInfo = k;
        });
        if (!keyInfo) return;
        
        var modal = document.getElementById('resultModal');
        var content = document.getElementById('resultContent');
        
        var statusLabel = {available: '可用', rate_limited: '限流中', unavailable: '不可用', in_use: '使用中'};
        var regionLabel = {sgp: '新加坡', cn: '国内', 'sgp-anthropic': '新加坡A', 'cn-anthropic': '国内A', unknown: '-'};
        
        // 评分颜色（无上限，按等级划分）
        var scoreColor = '#f87171';
        if (keyInfo.score >= 100) scoreColor = '#34d399';
        else if (keyInfo.score >= 80) scoreColor = '#6ee7b7';
        else if (keyInfo.score >= 60) scoreColor = '#fbbf24';
        else if (keyInfo.score >= 40) scoreColor = '#fb923c';
        
        var html = '<div class="result-header">Key 详情</div>';
        html += '<div class="detail-row"><span class="detail-label">完整Key:</span></div>';
        html += '<div class="detail-key">' + keyInfo.key + '</div>';
        html += '<div class="detail-row"><span class="detail-label">区域:</span> <span class="region-tag region-' + keyInfo.region + '">' + (regionLabel[keyInfo.region] || keyInfo.region) + '</span></div>';
        html += '<div class="detail-row"><span class="detail-label">状态:</span> <span class="badge badge-' + keyInfo.status + '">' + (statusLabel[keyInfo.status] || keyInfo.status) + '</span></div>';
        html += '<div class="detail-row"><span class="detail-label">评分:</span> <span style="color:' + scoreColor + ';font-weight:700;font-size:18px">' + keyInfo.score + '分</span></div>';
        html += '<div class="detail-row"><span class="detail-label">延迟:</span> ' + (keyInfo.latency > 0 ? keyInfo.latency + 'ms' : '-') + '</div>';
        html += '<div class="detail-row"><span class="detail-label">URL:</span> <span class="cell-url">' + (keyInfo.url || '-') + '</span></div>';
        html += '<div class="detail-row"><span class="detail-label">测试次数:</span> ' + keyInfo.test_count + '</div>';
        html += '<div class="detail-row"><span class="detail-label">限速次数:</span> ' + keyInfo.rate_limit_count + '</div>';
        html += '<div class="detail-row"><span class="detail-label">加入时间:</span> ' + (keyInfo.added_at ? new Date(keyInfo.added_at).toLocaleString() : '-') + '</div>';
        html += '<div class="detail-row"><span class="detail-label">最后测试:</span> ' + (keyInfo.tested_at ? new Date(keyInfo.tested_at).toLocaleString() : '-') + '</div>';
        
        html += '<div style="display:flex;gap:10px;margin-top:15px">';
        html += '<button class="btn btn-primary" onclick="copyText(\'' + keyInfo.key + '\')" style="flex:1">复制Key</button>';
        if (keyInfo.url) {
            html += '<button class="btn btn-ghost" onclick="copyText(\'' + keyInfo.key + '\\n' + keyInfo.url + '\')" style="flex:1">复制Key+URL</button>';
        }
        html += '</div>';
        html += '<button class="btn btn-ghost" onclick="closeResultModal()" style="width:100%;margin-top:10px">关闭</button>';
        
        content.innerHTML = html;
        modal.style.display = 'flex';
    });
}

function refreshList() {
    showLoading('正在刷新列表...');
    apiCall('list').then(function(data) {
        hideLoading();
        var keys = data.keys;
        var stats = {available: 0, rate_limited: 0, unavailable: 0, in_use: 0};
        keys.forEach(function(k){ stats[k.status] = (stats[k.status] || 0) + 1; });

        document.getElementById('stats').innerHTML =
            '<div class="stat-card stat-total"><div class="stat-num">' + keys.length + '</div><div class="stat-label">总计</div></div>' +
            '<div class="stat-card stat-available"><div class="stat-num">' + stats.available + '</div><div class="stat-label">可用</div></div>' +
            '<div class="stat-card stat-rate_limited"><div class="stat-num">' + stats.rate_limited + '</div><div class="stat-label">限流中</div></div>' +
            '<div class="stat-card stat-unavailable"><div class="stat-num">' + stats.unavailable + '</div><div class="stat-label">不可用</div></div>';

        if (!keys.length) {
            document.getElementById('keyTable').innerHTML = '<tr><td colspan="9" class="empty">暂无数据</td></tr>';
            return;
        }

        var statusLabel = {available: '可用', rate_limited: '限流中', unavailable: '不可用', in_use: '使用中'};
        var regionLabel = {sgp: '新加坡', cn: '国内', 'sgp-anthropic': '新加坡A', 'cn-anthropic': '国内A', unknown: '-'};
        var html = '';
        keys.forEach(function(k, i) {
            // 评分颜色（无上限，按等级划分）
            var scoreColor = '#f87171'; // 红色
            if (k.score >= 100) scoreColor = '#34d399'; // 绿色（优质）
            else if (k.score >= 80) scoreColor = '#6ee7b7'; // 浅绿色（良好）
            else if (k.score >= 60) scoreColor = '#fbbf24'; // 黄色（一般）
            else if (k.score >= 40) scoreColor = '#fb923c'; // 橙色（较差）
            
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
            
            // 操作按钮
            var urlBtn = k.url ? '<button class="btn-sm" onclick="copyText(\'' + k.key + '\\n' + k.url + '\')">URL</button>' : '';
            
            html += '<tr>';
            html += '<td style="color:rgba(255,255,255,0.25)">' + (i + 1) + '</td>';
            html += '<td><span class="key-text" title="点击查看详情" onclick="showKeyDetail(\'' + k.key + '\')" style="cursor:pointer">' + k.key + '</span></td>';
            html += '<td><span class="region-tag region-' + k.region + '">' + (regionLabel[k.region] || k.region) + '</span></td>';
            html += '<td><span class="badge badge-' + k.status + '">' + (statusLabel[k.status] || k.status) + '</span></td>';
            html += '<td><span style="color:' + scoreColor + ';font-weight:700">' + k.score + '</span></td>';
            html += '<td><span class="cell-time">' + latencyStr + '</span></td>';
            html += '<td><span class="cell-time">' + (k.added_at ? new Date(k.added_at).toLocaleString() : '-') + '</span></td>';
            html += '<td><span class="cell-time">' + duration + '</span></td>';
            html += '<td><button class="btn-sm" onclick="copyText(\'' + k.key + '\')">复制</button>' + urlBtn;
            html += '<button class="btn-sm" onclick="retestOne(\'' + k.key + '\')">重测</button>';
            html += '<button class="btn-sm btn-danger" onclick="deleteKey(\'' + k.key + '\')">删除</button></td>';
            html += '</tr>';
        });
        document.getElementById('keyTable').innerHTML = html;
    }).catch(function() {
        hideLoading();
        showToast('刷新失败', 'error');
    });
}

function retestOne(key) {
    showToast('正在重测Key...', 'info');
    apiCall('retest', {key: key}).then(function() {
        showToast('重测完成', 'success');
        refreshList();
    }).catch(function() {
        showToast('重测失败', 'error');
    });
}

function retestAll() {
    showToast('正在测试所有Key，请不要做其他动作...', 'info');
    apiCall('retest', {test_all: true}).then(function() {
        showToast('重测完成', 'success');
        refreshList();
    }).catch(function() {
        showToast('重测失败', 'error');
    });
}

function toggleAuto() {
    var on = document.getElementById('autoToggle').checked;
    apiCall('auto', {on: on, interval: 180}).then(function() {
        showToast(on ? '自动重测已开启（2-5分钟随机）' : '自动重测已关闭', 'success');
    });
}

function initApp() {
    loadUrls();
    refreshList();
    document.getElementById('autoToggle').checked = true;
    apiCall('auto', {on: true, interval: 180});
    
    // 自动检查更新（每天一次）
    checkUpdateOnLoad();
}

function checkUpdateOnLoad() {
    apiCall('check_update', {}).then(function(data) {
        if (data.ok) {
            // 更新版本号显示
            var versionEl = document.getElementById('versionTag');
            if (versionEl) {
                versionEl.textContent = 'v' + data.local;
                if (data.has_update) {
                    versionEl.innerHTML = 'v' + data.local + ' <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#fbbf24" stroke-width="3"><path d="M12 19V5M5 12l7-7 7 7"/></svg>';
                    versionEl.onclick = function() {
                        if (confirm('发现新版本 ' + data.remote + '，当前版本 ' + data.local + '，是否升级？')) {
                            doUpdate();
                        }
                    };
                }
            }
        }
    });
}

initApp();

function exportAll() {
    apiCall('list').then(function(data) {
        var usable = data.keys.filter(function(k){ return k.status === 'available'; });
        if (!usable.length) { showToast('没有可用的Key（不含限流）', 'error'); return; }
        var lines = usable.map(function(k){ return k.key + (k.url ? '\n' + k.url : ''); });
        copyText(lines.join('\n\n'));
        showToast('已复制 ' + usable.length + ' 个可用Key', 'success');
    });
}

function exportKeysOnly() {
    apiCall('list').then(function(data) {
        var usable = data.keys.filter(function(k){ return k.status === 'available'; });
        if (!usable.length) { showToast('没有可用的Key（不含限流）', 'error'); return; }
        var lines = usable.map(function(k){ return k.key; });
        copyText(lines.join('\n'));
        showToast('已复制 ' + usable.length + ' 个可用Key', 'success');
    });
}

function exportJson() {
    apiCall('list').then(function(data) {
        copyText(JSON.stringify(data.keys, null, 2));
        showToast('JSON已复制', 'success');
    });
}

function exportData() {
    showLoading('正在导出数据...');
    apiCall('export_data', {}).then(function(data) {
        hideLoading();
        if (data.ok) {
            // 创建下载文件
            var blob = new Blob([JSON.stringify(data.data, null, 2)], {type: 'application/json'});
            var url = URL.createObjectURL(blob);
            var a = document.createElement('a');
            a.href = url;
            a.download = 'api-keys-backup-' + new Date().toISOString().slice(0,10) + '.json';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
            showToast('数据导出成功', 'success');
        } else {
            showToast('导出失败: ' + data.error, 'error');
        }
    }).catch(function() {
        hideLoading();
        showToast('导出失败', 'error');
    });
}

function importData() {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = function(e) {
        var file = e.target.files[0];
        if (!file) return;
        
        var reader = new FileReader();
        reader.onload = function(event) {
            try {
                var data = JSON.parse(event.target.result);
                showLoading('正在导入数据...');
                apiCall('import_data', {data: data}).then(function(result) {
                    hideLoading();
                    if (result.ok) {
                        showToast('导入成功！新增 ' + result.imported + ' 个Key，共 ' + result.total + ' 个', 'success');
                        refreshList();
                    } else {
                        showToast('导入失败: ' + result.error, 'error');
                    }
                }).catch(function() {
                    hideLoading();
                    showToast('导入失败', 'error');
                });
            } catch(err) {
                showToast('文件格式错误', 'error');
            }
        };
        reader.readAsText(file);
    };
    input.click();
}

function addUrl() {
    var url = document.getElementById('newUrl').value.trim();
    var region = document.getElementById('newRegion').value.trim();
    if (!url) { showToast('请输入URL', 'error'); return; }
    if (!region) region = 'custom_' + Date.now();
    apiCall('add_url', {url: url, region: region}).then(function() {
        document.getElementById('newUrl').value = '';
        document.getElementById('newRegion').value = '';
        loadUrls();
        showToast('已添加: ' + region, 'success');
    });
}

function removeUrl(region) {
    apiCall('del_url', {region: region}).then(function() {
        loadUrls();
        showToast('已删除', 'success');
    });
}

function deleteKey(key) {
    if (!confirm('确定删除这个Key？')) return;
    showLoading('正在删除...');
    apiCall('delete_key', {key: key}).then(function() {
        hideLoading();
        showToast('已删除', 'success');
        refreshList();
    });
}

function clearAll() {
    if (!confirm('确定清空所有Key？此操作不可恢复。')) return;
    showLoading('正在清空...');
    apiCall('clear_all', {}).then(function(data) {
        hideLoading();
        showToast('已清空 ' + data.count + ' 个Key', 'success');
        refreshList();
    });
}

function checkUpdate() {
    showLoading('正在检查更新...');
    apiCall('check_update', {}).then(function(data) {
        hideLoading();
        if (!data.ok) {
            showToast('检查失败: ' + data.error, 'error');
            return;
        }
        if (data.has_update) {
            if (confirm('发现新版本 ' + data.remote + '，当前版本 ' + data.local + '，是否升级？')) {
                doUpdate();
            }
        } else {
            showToast('已是最新版本 ' + data.local, 'success');
        }
    }).catch(function() {
        hideLoading();
        showToast('检查更新失败', 'error');
    });
}

function doUpdate() {
    showLoading('正在升级...');
    apiCall('do_update', {}).then(function(data) {
        hideLoading();
        if (data.ok) {
            if (data.install_type === 'docker') {
                showToast('Docker容器已重建，版本: ' + data.old_version + ' → ' + data.version, 'success');
            } else {
                showToast('升级成功！版本: ' + data.old_version + ' → ' + data.version + '，正在重启...', 'success');
                // 等待重启后刷新页面
                setTimeout(function() {
                    window.location.reload();
                }, 3000);
            }
        } else {
            showToast('升级失败: ' + data.error, 'error');
        }
    }).catch(function() {
        hideLoading();
        showToast('升级失败', 'error');
    });
}

function clearUnavailable() {
    if (!confirm('确定清除所有不可用的Key？')) return;
    showLoading('正在清除...');
    apiCall('clear_unavailable', {}).then(function(data) {
        hideLoading();
        showToast('已清除 ' + data.count + ' 个不可用Key', 'success');
        refreshList();
    });
}

function exportToOmniRoute() {
    // 先加载配置
    apiCall('get_config', {}).then(function(configData) {
        var config = configData.config || {};
        var url = prompt('OmniRoute地址:', config.omniroute_url || 'http://192.168.2.35:20128');
        if (!url) return;
        var apiKey = prompt('OmniRoute Access Token:', config.omniroute_api_key || '');
        
        showLoading('正在导出到OmniRoute...');
        apiCall('export_omniroute', {
            omniroute_url: url,
            omniroute_api_key: apiKey || ''
        }).then(function(data) {
            hideLoading();
            if (data.ok) {
                var msg = '导出完成！新增 ' + data.success + ' 个';
                if (data.skipped > 0) msg += '，跳过 ' + data.skipped + ' 个重复';
                if (data.errors && data.errors.length > 0) msg += '，失败 ' + data.errors.length + ' 个';
                showToast(msg, data.errors.length > 0 ? 'error' : 'success');
            } else {
                showToast('导出失败', 'error');
            }
            refreshList();
        }).catch(function() {
            hideLoading();
            showToast('导出失败，无法连接OmniRoute', 'error');
        });
    });
}

function syncOmniRoute() {
    if (!confirm('同步会删除OmniRoute中所有无效Key对应的配置，确定？')) return;
    showLoading('正在同步OmniRoute...');
    apiCall('sync_omniroute', {}).then(function(data) {
        hideLoading();
        if (data.ok) {
            showToast('同步完成，删除了 ' + data.deleted + ' 个无效配置', 'success');
        } else {
            showToast('同步失败: ' + data.error, 'error');
        }
    }).catch(function() {
        hideLoading();
        showToast('同步失败', 'error');
    });
}

function configOmniRoute() {
    apiCall('get_config', {}).then(function(data) {
        var config = data.config || {};
        var url = prompt('OmniRoute地址:', config.omniroute_url || 'http://192.168.2.35:20128');
        if (url === null) return;  // 用户取消
        var apiKey = prompt('OmniRoute Access Token:', config.omniroute_api_key || '');
        if (apiKey === null) return;  // 用户取消
        
        apiCall('save_config', {
            config: {
                omniroute_url: url,
                omniroute_api_key: apiKey
            }
        }).then(function() {
            showToast('OmniRoute配置已保存', 'success');
        });
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
.table-wrap{overflow-x:auto;max-width:100%}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:12px 14px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:1px;color:rgba(255,255,255,0.3);border-bottom:1px solid rgba(255,255,255,0.06);white-space:nowrap}
td{padding:12px 14px;font-size:13px;border-bottom:1px solid rgba(255,255,255,0.03);vertical-align:middle;white-space:nowrap}
tr{transition:background 0.15s}
tr:hover{background:rgba(255,255,255,0.02)}
.key-text{font-family:'SF Mono',monospace;font-size:12px;color:rgba(255,255,255,0.7)}
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
.loading-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);backdrop-filter:blur(10px);display:none;justify-content:center;align-items:center;z-index:9999;flex-direction:column}
.loading-spinner{width:50px;height:50px;border:3px solid rgba(255,255,255,0.1);border-top-color:#a78bfa;border-radius:50%;animation:spin 1s linear infinite}
.loading-text{color:#e0e0e0;margin-top:20px;font-size:14px}
@keyframes spin{to{transform:rotate(360deg)}}
.result-modal{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);backdrop-filter:blur(10px);display:none;justify-content:center;align-items:center;z-index:9998}
.result-box{background:rgba(30,30,50,0.95);border:1px solid rgba(255,255,255,0.1);border-radius:16px;padding:24px;max-width:400px;width:90%;max-height:80vh;overflow-y:auto}
.result-header{font-size:18px;font-weight:700;text-align:center;margin-bottom:15px;color:#fff}
.result-count{text-align:center;font-size:16px;margin-bottom:15px;color:rgba(255,255,255,0.8)}
.result-stats{display:flex;justify-content:center;gap:15px;margin-bottom:15px}
.stat-success{color:#34d399;font-weight:600}
.stat-warning{color:#fbbf24;font-weight:600}
.stat-error{color:#f87171;font-weight:600}
.result-list{max-height:200px;overflow-y:auto;margin-bottom:10px}
.result-item{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-radius:8px;margin-bottom:5px}
.result-item.success{background:rgba(52,211,153,0.1);border:1px solid rgba(52,211,153,0.2)}
.result-item.warning{background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.2)}
.result-item.error{background:rgba(248,113,113,0.1);border:1px solid rgba(248,113,113,0.2)}
.result-key{font-family:'SF Mono',monospace;font-size:12px;color:rgba(255,255,255,0.7)}
.result-status{font-size:11px;font-weight:600}
.detail-row{margin:8px 0;font-size:13px}
.detail-label{color:rgba(255,255,255,0.5);margin-right:8px}
.detail-key{font-family:'SF Mono',monospace;font-size:12px;background:rgba(0,0,0,0.3);padding:10px;border-radius:8px;margin:10px 0;word-break:break-all}
.header-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:30px}
.header-row h1{margin-bottom:0}
.version-tag{font-size:12px;color:rgba(255,255,255,0.3);cursor:pointer}
.version-tag:hover{color:rgba(255,255,255,0.6)}
</style>
</head>
<body>
<div class="loading-overlay" id="loadingOverlay">
<div class="loading-spinner"></div>
<div class="loading-text" id="loadingText">处理中...</div>
</div>
<div class="result-modal" id="resultModal">
<div class="result-box" id="resultContent"></div>
</div>
<div class="container">
<div class="header-row">
<h1>API KEY 管理器</h1>
<span class="version-tag" id="versionTag" onclick="checkUpdate()">v1.0.0</span>
</div>

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
<tr><th>#</th><th>Key</th><th>区域</th><th>状态</th><th>评分</th><th>延迟</th><th>加入时间</th><th>入库时长</th><th>操作</th></tr>
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
<button class="btn btn-ghost" onclick="exportKeysOnly()">复制全部可用 Key</button>
<button class="btn btn-ghost" onclick="exportJson()">复制 JSON</button>
<button class="btn btn-primary" onclick="exportData()">导出数据</button>
<button class="btn btn-ghost" onclick="importData()">导入数据</button>
<button class="btn btn-primary" onclick="exportToOmniRoute()">导出到 OmniRoute</button>
<button class="btn btn-ghost" onclick="configOmniRoute()">配置OmniRoute</button>
<button class="btn btn-ghost" onclick="syncOmniRoute()">同步OmniRoute</button>
<button class="btn btn-warning" onclick="clearUnavailable()">清除不可用Key</button>
<button class="btn btn-warning" onclick="clearAll()">清空所有Key</button>
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
    test_all = request.json.get('test_all', False)
    validator.retest(key, test_all=test_all)
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

@app.route('/api/check_update', methods=['POST'])
def api_check_update():
    """检查是否有新版本"""
    import json as json_mod
    try:
        # 读取本地版本
        with open('version.json', 'r') as f:
            local_version = json_mod.load(f).get('version', '0.0.0')
        
        # 从GitHub获取远程版本
        resp = requests.get(
            'https://raw.githubusercontent.com/shaoxianbilly/mimo/main/version.json',
            timeout=10
        )
        if resp.status_code == 200:
            remote_version = resp.json().get('version', '0.0.0')
            has_update = remote_version > local_version
            return jsonify({
                "ok": True,
                "local": local_version,
                "remote": remote_version,
                "has_update": has_update
            })
        else:
            return jsonify({"ok": False, "error": "无法获取远程版本"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route('/api/do_update', methods=['POST'])
def api_do_update():
    """执行升级（根据安装方式）"""
    import subprocess
    import json as json_mod
    try:
        # 检测安装方式
        is_docker = os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == 'true'
        
        # 备份当前版本
        try:
            with open('version.json', 'r') as f:
                old_version = json_mod.load(f).get('version', '0.0.0')
        except:
            old_version = '0.0.0'
        
        # 拉取最新代码
        result = subprocess.run(
            ['git', 'pull', 'origin', 'main'],
            capture_output=True, text=True, timeout=30,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        if result.returncode == 0:
            # 读取新版本号
            with open('version.json', 'r') as f:
                new_version = json_mod.load(f).get('version', 'unknown')
            
            if is_docker:
                # Docker方式：重建容器
                subprocess.run(['docker-compose', 'down'], capture_output=True)
                subprocess.run(['docker-compose', 'up', '-d', '--build'], capture_output=True)
                return jsonify({
                    "ok": True,
                    "version": new_version,
                    "old_version": old_version,
                    "message": "Docker容器已重建",
                    "install_type": "docker"
                })
            else:
                # 本地方式：自动重启
                def restart_delayed():
                    import time
                    time.sleep(2)
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                
                threading.Thread(target=restart_delayed, daemon=True).start()
                return jsonify({
                    "ok": True,
                    "version": new_version,
                    "old_version": old_version,
                    "message": "代码已更新，正在重启...",
                    "install_type": "local"
                })
        else:
            return jsonify({
                "ok": False,
                "error": result.stderr or "git pull失败"
            })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route('/api/restart', methods=['POST'])
def api_restart():
    """重启应用"""
    import os
    import sys
    import subprocess
    
    # 延迟1秒后重启
    def restart_delayed():
        import time
        time.sleep(1)
        os.execv(sys.executable, [sys.executable] + sys.argv)
    
    threading.Thread(target=restart_delayed, daemon=True).start()
    return jsonify({"ok": True, "message": "正在重启..."})

@app.route('/api/export_omniroute', methods=['POST'])
def api_export_omniroute():
    omniroute_url = request.json.get('omniroute_url', '')
    omniroute_api_key = request.json.get('omniroute_api_key', '')
    
    # 保存配置
    validator.config['omniroute_url'] = omniroute_url
    validator.config['omniroute_api_key'] = omniroute_api_key
    validator._save_config()
    
    success_count, errors, skip_count = validator.export_to_omniroute(omniroute_url, omniroute_api_key)
    return jsonify({
        "ok": True,
        "success": success_count,
        "skipped": skip_count,
        "errors": errors,
        "total": success_count + len(errors) + skip_count
    })

@app.route('/api/sync_omniroute', methods=['POST'])
def api_sync_omniroute():
    """同步：删除OmniRoute中无效的Key"""
    omniroute_url = validator.config.get('omniroute_url', '')
    omniroute_api_key = validator.config.get('omniroute_api_key', '')
    
    if not omniroute_url:
        return jsonify({"ok": False, "error": "未配置OmniRoute地址"})
    
    try:
        headers = {"Content-Type": "application/json"}
        if omniroute_api_key:
            headers["Authorization"] = f"Bearer {omniroute_api_key}"
        
        # 获取OmniRoute中的连接
        resp = requests.get(f"{omniroute_url}/api/providers", headers=headers, timeout=10)
        if resp.status_code != 200:
            return jsonify({"ok": False, "error": "无法连接OmniRoute"})
        
        connections = resp.json().get('connections', [])
        
        # 找出无效的Key对应的连接ID
        invalid_ids = []
        for conn in connections:
            api_key = conn.get('apiKey', '')
            # 检查本地是否有这个Key且状态为unavailable
            for key, info in validator.keys.items():
                if key[:20] == api_key[:20] and info.status == 'unavailable':
                    invalid_ids.append(conn['id'])
                    break
        
        # 删除无效连接
        deleted = 0
        if invalid_ids:
            del_resp = requests.delete(
                f"{omniroute_url}/api/providers",
                headers=headers,
                json={"ids": invalid_ids},
                timeout=10
            )
            if del_resp.status_code == 200:
                deleted = del_resp.json().get('deleted', 0)
        
        return jsonify({
            "ok": True,
            "deleted": deleted,
            "total": len(connections)
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route('/api/get_config', methods=['POST'])
def api_get_config():
    """获取配置"""
    return jsonify({
        "ok": True,
        "config": validator.config
    })

@app.route('/api/save_config', methods=['POST'])
def api_save_config():
    """保存配置"""
    config = request.json.get('config', {})
    validator.config.update(config)
    validator._save_config()
    return jsonify({"ok": True})

@app.route('/api/export_data', methods=['POST'])
def api_export_data():
    """导出所有数据（keys + config）"""
    import json as json_mod
    try:
        data = {
            "version": "1.0.0",
            "exported_at": datetime.now().isoformat(),
            "config": validator.config,
            "keys": {k: asdict(v) for k, v in validator.keys.items()}
        }
        return jsonify({"ok": True, "data": data})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route('/api/import_data', methods=['POST'])
def api_import_data():
    """导入数据（keys + config）"""
    import json as json_mod
    try:
        data = request.json.get('data', {})
        
        # 导入配置
        if 'config' in data:
            validator.config.update(data['config'])
            validator._save_config()
        
        # 导入keys
        imported_count = 0
        if 'keys' in data:
            for key, key_data in data['keys'].items():
                if key not in validator.keys:
                    validator.keys[key] = ApiKeyInfo(
                        key=key_data.get('key', key),
                        region=key_data.get('region', 'unknown'),
                        status=key_data.get('status', 'unavailable'),
                        url=key_data.get('url', ''),
                        tested_at=key_data.get('tested_at', ''),
                        added_at=key_data.get('added_at', ''),
                        latency=key_data.get('latency', 0),
                        error=key_data.get('error'),
                        omniroute_id=key_data.get('omniroute_id', ''),
                        score=key_data.get('score', 0),
                        test_count=key_data.get('test_count', 0),
                        rate_limit_count=key_data.get('rate_limit_count', 0)
                    )
                    imported_count += 1
            validator._save_keys()
        
        return jsonify({
            "ok": True,
            "imported": imported_count,
            "total": len(validator.keys)
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


def open_browser():
    import webbrowser
    webbrowser.open('http://localhost:8899')

if __name__ == '__main__':
    import sys
    
    # 启动Flask
    print("\n" + "=" * 50)
    print("  API Key 管理器")
    print("  http://localhost:8899")
    print("=" * 50 + "\n")
    
    # 自动打开浏览器
    import threading
    threading.Timer(1.5, open_browser).start()
    
    app.run(host='127.0.0.1', port=8899, debug=False)

# Vercel handler
handler = app
