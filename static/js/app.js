// 全局变量
let socket;
let botRunning = false;
let runningTime = 0;
let runningTimeInterval;
let refreshInterval;
let currentEquityRange = '7d'; // 默认7天

// 初始化
document.addEventListener('DOMContentLoaded', function() {
    initializeSocket();
    initializeEventListeners();
    loadInitialData();
    startAutoRefresh();
    initializeMobileFeatures();
    startTradingLogRefresh(); // 启动交易日志刷新
    startCountdownTimer(); // 启动倒计时
    initializeEquityRangeSelector(); // 初始化资金曲线时间范围选择器
});

// 初始化移动端功能
function initializeMobileFeatures() {
    // 添加触摸反馈
    addTouchFeedback();
    
    // 优化滚动体验
    optimizeScrolling();
    
    // 添加移动端手势支持
    addGestureSupport();
    
    // 优化键盘输入
    optimizeKeyboardInput();
    
    // 添加离线检测
    addOfflineDetection();
}

// 添加触摸反馈
function addTouchFeedback() {
    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(button => {
        button.addEventListener('touchstart', function() {
            this.style.transform = 'scale(0.95)';
            this.style.transition = 'transform 0.1s ease';
        });
        
        button.addEventListener('touchend', function() {
            this.style.transform = 'scale(1)';
        });
        
        button.addEventListener('touchcancel', function() {
            this.style.transform = 'scale(1)';
        });
    });
}

// 优化滚动体验
function optimizeScrolling() {
    // 平滑滚动
    document.documentElement.style.scrollBehavior = 'smooth';
    
    // 防止过度滚动
    document.body.style.overscrollBehavior = 'contain';
    
    // 优化日志滚动
    const logContainer = document.getElementById('logContent');
    if (logContainer) {
        logContainer.style.scrollBehavior = 'smooth';
    }
}

// 添加手势支持
function addGestureSupport() {
    let startY = 0;
    let startX = 0;
    
    document.addEventListener('touchstart', function(e) {
        startY = e.touches[0].clientY;
        startX = e.touches[0].clientX;
    });
    
    document.addEventListener('touchmove', function(e) {
        const currentY = e.touches[0].clientY;
        const currentX = e.touches[0].clientX;
        const diffY = startY - currentY;
        const diffX = startX - currentX;
        
        // 检测下拉刷新手势
        if (diffY < -100 && Math.abs(diffX) < 50) {
            refreshData();
            // 下拉刷新触发，不显示在日志中
        }
    });
}

// 优化键盘输入
function optimizeKeyboardInput() {
    const inputs = document.querySelectorAll('input[type="number"], input[type="text"]');
    inputs.forEach(input => {
        // 移动端数字键盘
        if (input.type === 'number') {
            input.setAttribute('inputmode', 'decimal');
        }
        
        // 防止缩放
        input.addEventListener('focus', function() {
            if (window.innerWidth < 768) {
                setTimeout(() => {
                    this.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }, 300);
            }
        });
    });
}

// 添加离线检测
function addOfflineDetection() {
    window.addEventListener('online', function() {
        // 重新连接WebSocket
        if (socket && !socket.connected) {
            socket.connect();
        }
    });
    
    window.addEventListener('offline', function() {
        // 网络已断开
    });
}

// 初始化WebSocket连接
function initializeSocket() {
    socket = io();
    
    socket.on('connect', function() {
        // WebSocket连接成功
    });
    
    socket.on('disconnect', function() {
        // WebSocket断开
    });
    
    socket.on('update_data', function(data) {
        updateTradingData(data);
    });
}

// 初始化事件监听器
function initializeEventListeners() {
    // 控制按钮
    document.getElementById('toggleBot').addEventListener('click', toggleBot);
    document.getElementById('restartBot').addEventListener('click', restartBot);
    document.getElementById('refreshNow').addEventListener('click', refreshData);
    
    // 测试模式切换（自动保存）
    document.getElementById('testMode').addEventListener('change', saveTestMode);
    
    // 自动刷新设置
    document.getElementById('autoRefresh').addEventListener('change', toggleAutoRefresh);
    document.getElementById('refreshInterval').addEventListener('change', updateRefreshInterval);
}

// 加载初始数据
async function loadInitialData() {
    try {
        // 添加欢迎日志
        addLogEntry('🎯 交易机器人管理系统已就绪', 'INFO', 'fas fa-robot');
        
        const response = await fetch('/api/status');
        const data = await response.json();
        
        updateStatus(data);
        
        // 确保配置正确加载并显示
        if (data.config) {
            updateConfigDisplay(data.config);
        }
        
        // 加载机器人状态
        await updateBotRunningStatus();
    } catch (error) {
        console.error('加载数据失败:', error);
        addLogEntry('❌ 加载初始数据失败', 'ERROR', 'fas fa-exclamation-triangle');
    }
}

// 切换机器人状态（启动/停止）
async function toggleBot() {
    const btn = document.getElementById('toggleBot');
    const isRunning = btn.classList.contains('btn-danger');
    
    // 禁用按钮防止重复点击
    btn.disabled = true;
    
    try {
        if (isRunning) {
            // 当前是运行状态，执行停止
            const confirmed = confirm('⚠️ 确定要停止交易机器人吗？\n\n停止后机器人将不再执行交易。');
            if (!confirmed) {
                btn.disabled = false;
                return;
            }
            
            // 添加操作日志
            addLogEntry('🛑 正在停止交易机器人...', 'WARNING', 'fas fa-stop-circle');
            
            const response = await fetch('/api/stop_bot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                addLogEntry('✅ 交易机器人已停止', 'SUCCESS', 'fas fa-check-circle');
                alert('✅ ' + data.message);
                await updateBotRunningStatus();
            } else {
                addLogEntry('❌ 停止机器人失败: ' + data.message, 'ERROR', 'fas fa-exclamation-circle');
                alert('❌ 停止失败: ' + data.message);
            }
        } else {
            // 当前是停止状态，执行启动
            addLogEntry('🚀 正在启动交易机器人...', 'INFO', 'fas fa-rocket');
            
            const response = await fetch('/api/start_bot', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                addLogEntry('✅ 交易机器人已启动', 'SUCCESS', 'fas fa-check-circle');
                alert('✅ ' + data.message);
                await updateBotRunningStatus();
            } else {
                addLogEntry('❌ 启动机器人失败: ' + data.message, 'ERROR', 'fas fa-exclamation-circle');
                alert('❌ 启动失败: ' + data.message);
            }
        }
    } catch (error) {
        console.error('操作机器人失败:', error);
        addLogEntry('❌ 操作失败: ' + error.message, 'ERROR', 'fas fa-times-circle');
        alert('❌ 操作失败，请查看控制台');
    } finally {
        btn.disabled = false;
    }
}

// 重启机器人
async function restartBot() {
    const confirmed = confirm(
        '🔄 确定要重启交易机器人吗？\n\n' +
        '重启后：\n' +
        '• 新的配置将立即生效\n' +
        '• 机器人将重新开始执行\n' +
        '• 不会影响现有持仓\n\n' +
        '是否继续？'
    );
    
    if (!confirmed) {
        return;
    }
    
    const btn = document.getElementById('restartBot');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 重启中...';
    
    // 添加操作日志
    addLogEntry('🔄 正在重启交易机器人...', 'WARNING', 'fas fa-sync-alt');
    
    try {
        const response = await fetch('/api/restart_bot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            addLogEntry('✅ 交易机器人重启成功，新配置已生效', 'SUCCESS', 'fas fa-check-circle');
            alert('✅ ' + data.message);
            // 等待2秒后更新状态
            setTimeout(async () => {
                await updateBotRunningStatus();
            }, 2000);
        } else {
            addLogEntry('❌ 重启机器人失败: ' + data.message, 'ERROR', 'fas fa-exclamation-circle');
            alert('❌ 重启失败: ' + data.message);
        }
    } catch (error) {
        console.error('重启机器人失败:', error);
        addLogEntry('❌ 重启失败: ' + error.message, 'ERROR', 'fas fa-times-circle');
        alert('❌ 重启失败，请查看控制台');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-sync-alt"></i> 重启机器人';
    }
}

// 更新机器人运行状态
async function updateBotRunningStatus() {
    try {
        const response = await fetch('/api/bot_status');
        const data = await response.json();
        
        if (data.success) {
            updateBotStatusUI(data.running, data.status, data.uptime_ms || 0);
        }
    } catch (error) {
        console.error('获取机器人状态失败:', error);
    }
}

// 刷新数据
async function refreshData() {
    try {
        const response = await fetch('/api/refresh_data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        updateTradingData(data);
        // 不再添加Web应用自己的日志，因为现在显示交易机器人的真实日志
    } catch (error) {
        console.error('刷新数据失败:', error);
    }
}

// 保存测试模式（自动保存）
async function saveTestMode() {
    const testMode = document.getElementById('testMode').checked;
    
    // 如果关闭测试模式，需要二次确认
    if (!testMode) {
        const confirmed = confirm(
            '⚠️ 警告：关闭测试模式\n\n' +
            '关闭测试模式后，交易机器人将进行真实交易！\n\n' +
            '• 会使用真实资金下单\n' +
            '• 可能产生盈利或亏损\n' +
            '• 请确保账户有足够余额\n\n' +
            '确定要关闭测试模式吗？'
        );
        
        if (!confirmed) {
            document.getElementById('testMode').checked = true;
            updateTestModeLabel(true);
            return;
        }
    }
    
    // 从API获取当前配置，只更新test_mode
    try {
        const statusResponse = await fetch('/api/status');
        const statusData = await statusResponse.json();
    
    const config = {
            ...(statusData.config || {}),
        test_mode: testMode
    };
    
    // 添加操作日志
    const modeText = testMode ? '测试模式' : '真实交易模式';
        addLogEntry(`💾 正在保存配置 (${modeText})...`, 'INFO', 'fas fa-save');
    
        const response = await fetch('/api/update_config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            updateTestModeLabel(testMode);
            addLogEntry(`✅ 配置已保存 (${modeText})`, 'SUCCESS', 'fas fa-check-circle');
        } else {
            // 如果保存失败，恢复开关状态
            document.getElementById('testMode').checked = !testMode;
            updateTestModeLabel(!testMode);
            addLogEntry('❌ 保存配置失败: ' + data.message, 'ERROR', 'fas fa-exclamation-circle');
            alert('❌ 保存失败: ' + data.message);
        }
    } catch (error) {
        console.error('保存配置失败:', error);
        // 如果保存失败，恢复开关状态
        document.getElementById('testMode').checked = !testMode;
        updateTestModeLabel(!testMode);
        addLogEntry('❌ 保存配置失败: ' + error.message, 'ERROR', 'fas fa-times-circle');
        alert('❌ 保存配置失败，请查看控制台');
    }
}

// 更新测试模式标签
function updateTestModeLabel(testMode) {
    const label = document.getElementById('testModeLabel');
    if (label) {
        if (testMode) {
            label.textContent = '✅ 开启';
            label.style.color = '#28a745';
            label.className = 'status-text enabled';
        } else {
            label.textContent = '🔴 关闭';
            label.style.color = '#dc3545';
            label.className = 'status-text disabled';
        }
    }
}

// 切换自动刷新
function toggleAutoRefresh() {
    const autoRefresh = document.getElementById('autoRefresh').checked;
    if (autoRefresh) {
        startAutoRefresh();
    } else {
        stopAutoRefresh();
    }
}

// 更新刷新间隔
function updateRefreshInterval() {
    const interval = parseInt(document.getElementById('refreshInterval').value);
    if (document.getElementById('autoRefresh').checked) {
        stopAutoRefresh();
        startAutoRefresh(interval);
    }
}

// 开始自动刷新
function startAutoRefresh(interval = 2) {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    
    refreshInterval = setInterval(() => {
        if (document.getElementById('autoRefresh').checked) {
            refreshData();
            // 同时更新机器人状态（包括运行时长）
            updateBotRunningStatus();
        }
    }, interval * 1000);
}

// 停止自动刷新
function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// 开始运行计时器（使用PM2提供的启动时间）
function startRunningTimer(uptimeMs) {
    if (uptimeMs > 0) {
        // 根据PM2提供的uptime计算启动时间
        botStartTime = Date.now() - uptimeMs;
    } else {
        botStartTime = Date.now();
    }
    
    updateRunningTime();  // 立即更新一次
    
    if (runningTimeInterval) {
        clearInterval(runningTimeInterval);
    }
    
    // 每秒更新一次
    runningTimeInterval = setInterval(() => {
        updateRunningTime();
    }, 1000);
}

// 停止运行计时器
function stopRunningTimer() {
    if (runningTimeInterval) {
        clearInterval(runningTimeInterval);
        runningTimeInterval = null;
    }
    botStartTime = null;
    document.getElementById('runningTime').textContent = '0分钟';
}

// 更新运行时间显示
function updateRunningTime() {
    if (!botStartTime) {
        document.getElementById('runningTime').textContent = '0分钟';
        return;
    }
    
    const elapsedMs = Date.now() - botStartTime;
    const elapsedSeconds = Math.floor(elapsedMs / 1000);
    const hours = Math.floor(elapsedSeconds / 3600);
    const minutes = Math.floor((elapsedSeconds % 3600) / 60);
    const seconds = elapsedSeconds % 60;
    
    let timeString = '';
    if (hours > 0) {
        timeString = `${hours}小时${minutes}分钟`;
    } else if (minutes > 0) {
        timeString = `${minutes}分钟${seconds}秒`;
    } else {
        timeString = `${seconds}秒`;
    }
    
    document.getElementById('runningTime').textContent = timeString;
}

// 更新机器人状态UI
function updateBotStatusUI(isRunning, status, uptimeMs) {
    const toggleBtn = document.getElementById('toggleBot');
    const toggleText = document.getElementById('toggleBotText');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('botStatusText');
    
    if (isRunning) {
        // 运行中状态
        toggleBtn.classList.remove('btn-success');
        toggleBtn.classList.add('btn-danger');
        toggleBtn.innerHTML = '<i class="fas fa-stop"></i> <span id="toggleBotText">停止机器人</span>';
        
        statusDot.style.color = '#28a745';
        statusDot.classList.add('pulse');
        statusText.textContent = '运行中';
        statusText.style.color = '#28a745';
        
        // 只要机器人在运行，就更新运行时长
        // 使用PM2提供的uptime计算实际启动时间
        if (uptimeMs && uptimeMs > 0) {
            botStartTime = Date.now() - uptimeMs;
        } else if (!botStartTime) {
            // 如果没有uptime信息，但机器人在运行，使用当前时间
            botStartTime = Date.now();
        }
        
        // 确保计时器在运行
        if (!runningTimeInterval) {
            runningTimeInterval = setInterval(() => {
                updateRunningTime();
            }, 1000);
        }
        
        // 立即更新一次显示
        updateRunningTime();
    } else {
        // 停止状态
        toggleBtn.classList.remove('btn-danger');
        toggleBtn.classList.add('btn-success');
        toggleBtn.innerHTML = '<i class="fas fa-play"></i> <span id="toggleBotText">启动机器人</span>';
        
        statusDot.style.color = '#dc3545';
        statusDot.classList.remove('pulse');
        statusText.textContent = status === 'not_found' ? '未启动' : '已停止';
        statusText.style.color = '#dc3545';
        
        // 停止运行时长计时器
        stopRunningTimer();
    }
}

// 更新状态数据
function updateStatus(data) {
    // 机器人状态现在通过 PM2 API 单独获取
    
    // 更新价格
    if (data.price) {
        document.getElementById('btcPrice').textContent = `$${data.price.toLocaleString()}`;
    }
    
    // 更新信号
    if (data.signal) {
        updateSignal(data.signal, data.confidence);
    }
    
    // 更新持仓信息
    if (data.position) {
        updatePositionDetails(data.position);
    } else {
        clearPositionDetails();
    }
    
    // 强制更新配置（即使config为空也使用默认值）
    updateConfigDisplay(data.config);
}

// 更新交易数据
function updateTradingData(data) {
    // 更新价格
    if (data.price) {
        document.getElementById('btcPrice').textContent = `$${data.price.toLocaleString()}`;
    }
    
    // 更新信号
    if (data.signal) {
        updateSignal(data.signal, data.confidence);
    }
    
    // 更新持仓
    if (data.position) {
        updatePositionDetails(data.position);
    }
    
    // 不再显示数据更新时间戳在日志中
}

// 更新信号显示
function updateSignal(signal, confidence) {
    const signalElement = document.getElementById('latestSignal');
    let signalText = '';
    let signalClass = '';
    
    switch (signal) {
        case 'BUY':
            signalText = 'BUY 买入';
            signalClass = 'buy';
            break;
        case 'SELL':
            signalText = 'SELL 卖出';
            signalClass = 'sell';
            break;
        case 'HOLD':
            signalText = 'HOLD 观望';
            signalClass = 'hold';
            break;
        default:
            signalText = 'HOLD 观望';
            signalClass = 'hold';
    }
    
    signalElement.textContent = signalText;
    signalElement.className = `value signal ${signalClass}`;
    
    // 更新信心程度显示
    if (confidence) {
        const confidenceElement = document.getElementById('confidenceLevel');
        if (confidenceElement) {
            const confidenceUpper = (confidence || 'MEDIUM').toUpperCase();
            let confidenceText = '';
            let confidenceClass = '';
            
            switch (confidenceUpper) {
                case 'HIGH':
                    confidenceText = 'HIGH 高';
                    confidenceClass = 'confidence-high';
                    break;
                case 'MEDIUM':
                    confidenceText = 'MEDIUM 中';
                    confidenceClass = 'confidence-medium';
                    break;
                case 'LOW':
                    confidenceText = 'LOW 低';
                    confidenceClass = 'confidence-low';
                    break;
                default:
                    confidenceText = 'MEDIUM 中';
                    confidenceClass = 'confidence-medium';
                    break;
            }
            
            confidenceElement.textContent = confidenceText;
            confidenceElement.className = `value confidence ${confidenceClass}`;
        }
    } else {
        const confidenceElement = document.getElementById('confidenceLevel');
        if (confidenceElement) {
            confidenceElement.textContent = '--';
            confidenceElement.className = 'value confidence';
        }
    }
    
    // 不再显示信号在日志中，因为现在显示交易机器人的真实日志
}

// 更新持仓详情
function updatePositionDetails(position) {
    // 检查是否有持仓
    if (!position.side) {
        clearPositionDetails();
        // 但仍然显示账户余额
        if (position.total_balance !== undefined) {
            document.getElementById('accountBalance').textContent = `$${position.total_balance.toFixed(2)}`;
            document.getElementById('availableBalance').textContent = `$${position.free_balance.toFixed(2)}`;
        }
        return;
    }
    
    // 根据持仓方向设置显示文本
    let direction, directionText;
    if (position.side === 'long') {
        direction = '多单';
        directionText = '多单 (做多)';
    } else if (position.side === 'short') {
        direction = '空单';
        directionText = '空单 (做空)';
    } else {
        direction = '无持仓';
        directionText = '无持仓';
    }
    
    const directionClass = position.side === 'long' ? 'long' : 'short';
    
    document.getElementById('positionDirection').textContent = directionText;
    document.getElementById('directionDot').className = `direction-dot ${directionClass}`;
    document.getElementById('positionSize').textContent = `${position.size} 张`;
    document.getElementById('btcQuantity').textContent = `${(position.size * 0.01).toFixed(4)} BTC`;
    
    // 当前价格（使用标记价格）
    const currentPrice = position.mark_price || position.entry_price;
    document.getElementById('currentPrice').textContent = `$${currentPrice.toFixed(2)}`;
    
    // 持仓价值
    document.getElementById('positionValue').textContent = `$${(position.size * currentPrice * 0.01).toFixed(2)}`;
    document.getElementById('entryPrice').textContent = `$${position.entry_price.toFixed(2)}`;
    
    // 杠杆
    const leverage = position.leverage || 10;
    document.getElementById('leverage').textContent = `${leverage}x`;
    
    // 保证金信息
    document.getElementById('initialMargin').textContent = `$${(position.initial_margin || 0).toFixed(2)}`;
    
    // 维持保证金率 - 直接使用OKX返回的数据（已经是百分比数值）
    const maintMarginRate = position.maint_margin_ratio || 0;
    const maintMarginElement = document.getElementById('maintMargin');
    
    // 清除之前的样式
    maintMarginElement.className = 'value';
    
    // 根据保证金率设置颜色和图标
    let statusIcon = '';
    let statusClass = '';
    
    if (maintMarginRate < 300) {
        // 危险区域：<300% 即将强平
        statusClass = 'margin-ratio-danger';
        statusIcon = '<i class="fas fa-exclamation-triangle margin-icon"></i>';
    } else if (maintMarginRate < 1000) {
        // 警告区域：300%-1000% 需要注意
        statusClass = 'margin-ratio-warning';
        statusIcon = '<i class="fas fa-exclamation-circle margin-icon"></i>';
    } else {
        // 安全区域：>1000% 正常
        statusClass = 'margin-ratio-safe';
        statusIcon = '<i class="fas fa-check-circle margin-icon"></i>';
    }
    
    maintMarginElement.className = `value ${statusClass}`;
    maintMarginElement.innerHTML = `${statusIcon}${maintMarginRate.toFixed(2)}%`;
    
    // 强平价格
    const liqPrice = position.liquidation_price || 0;
    document.getElementById('liquidationPrice').textContent = `$${liqPrice.toFixed(2)}`;
    
    // 盈亏 - 根据正负值设置颜色
    const unrealizedPnlEl = document.getElementById('unrealizedPnl');
    const unrealizedPnl = position.unrealized_pnl || 0;
    unrealizedPnlEl.textContent = `${unrealizedPnl >= 0 ? '+' : ''}$${unrealizedPnl.toFixed(2)}`;
    // 设置颜色类：正值为绿色，负值为红色
    unrealizedPnlEl.className = `value pnl ${unrealizedPnl >= 0 ? 'positive' : 'negative'}`;
    
    // 计算盈亏比例 - 根据正负值设置颜色
    const pnlRatio = position.initial_margin > 0 
        ? (unrealizedPnl / position.initial_margin) * 100 
        : 0;
    const pnlRatioEl = document.getElementById('pnlRatio');
    pnlRatioEl.textContent = `${pnlRatio >= 0 ? '+' : ''}${pnlRatio.toFixed(2)}%`;
    // 设置颜色类：正值为绿色，负值为红色
    pnlRatioEl.className = `value pnl ${pnlRatio >= 0 ? 'positive' : 'negative'}`;
    
    // 账户余额
    document.getElementById('accountBalance').textContent = `$${(position.total_balance || 0).toFixed(2)}`;
    document.getElementById('availableBalance').textContent = `$${(position.free_balance || 0).toFixed(2)}`;
    
}

// 清空持仓详情
function clearPositionDetails() {
    document.getElementById('positionDirection').textContent = '无持仓';
    document.getElementById('directionDot').className = 'direction-dot';
    document.getElementById('positionSize').textContent = '0.00 张';
    document.getElementById('btcQuantity').textContent = '0.0000 BTC';
    document.getElementById('currentPrice').textContent = '$0.00';
    document.getElementById('positionValue').textContent = '$0.00';
    document.getElementById('entryPrice').textContent = '$0.00';
    document.getElementById('leverage').textContent = '10x';
    document.getElementById('initialMargin').textContent = '$0.00';
    const maintMarginElement = document.getElementById('maintMargin');
    maintMarginElement.className = 'value';
    maintMarginElement.innerHTML = '0.00%';
    document.getElementById('liquidationPrice').textContent = '$0.00';
    // 清空时重置为默认样式
    const unrealizedPnlEl = document.getElementById('unrealizedPnl');
    unrealizedPnlEl.textContent = '+$0.00';
    unrealizedPnlEl.className = 'value pnl';
    
    const pnlRatioEl = document.getElementById('pnlRatio');
    pnlRatioEl.textContent = '+0.00%';
    pnlRatioEl.className = 'value pnl';
    document.getElementById('accountBalance').textContent = '$0.00';
    document.getElementById('availableBalance').textContent = '$0.00';
}

// 更新配置显示（只更新测试模式）
function updateConfigDisplay(config) {
    // 确保配置对象存在
    if (!config) {
        config = {
            test_mode: true
        };
    }
    
    // 更新测试模式开关
    const testMode = config.test_mode !== undefined ? config.test_mode : true;
    const checkbox = document.getElementById('testMode');
    
    // 确保复选框状态正确设置
    checkbox.checked = testMode === true || testMode === 'true';
    
    // 更新标签显示
    updateTestModeLabel(testMode);
}

// 添加日志条目（在顶部显示，与交易日志一致）
function addLogEntry(message, level = 'INFO', icon = 'fas fa-info-circle') {
    const logContent = document.getElementById('logContent');
    const timestamp = new Date().toLocaleTimeString('zh-CN', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit' 
    });
    
    const logEntry = document.createElement('div');
    logEntry.className = 'log-entry';
    
    // 根据日志级别设置图标和样式
    let iconHtml = '';
    if (level === 'INFO') {
        iconHtml = `<i class="${icon}" style="color: #17a2b8;"></i>`;
    } else if (level === 'SUCCESS') {
        iconHtml = `<i class="${icon}" style="color: #28a745;"></i>`;
    } else if (level === 'WARNING') {
        iconHtml = `<i class="${icon}" style="color: #ffc107;"></i>`;
    } else if (level === 'ERROR') {
        iconHtml = `<i class="${icon}" style="color: #dc3545;"></i>`;
    }
    
    logEntry.innerHTML = `
        <span class="timestamp">[${timestamp}]</span>
        ${iconHtml}
        <span>${message}</span>
    `;
    
    // 在顶部插入（与交易日志显示逻辑一致）
    logContent.insertBefore(logEntry, logContent.firstChild);
    
    // 保持日志条数在合理范围内
    const entries = logContent.querySelectorAll('.log-entry');
    if (entries.length > 100) {
        entries[entries.length - 1].remove();
    }
    
    // 保持在顶部（最新日志可见）
    logContent.scrollTop = 0;
}

// 交易日志刷新
let tradingLogInterval;
let lastLogCount = 0;

// 启动交易日志刷新
// 倒计时定时器
let countdownInterval;

// 启动倒计时（北京时间00, 15, 30, 45分钟）
function startCountdownTimer() {
    updateCountdown();
    // 每秒更新一次倒计时
    countdownInterval = setInterval(updateCountdown, 1000);
}

// 更新倒计时显示
function updateCountdown() {
    const countdownText = document.getElementById('countdownText');
    if (!countdownText) return;
    
    try {
        // 获取北京时间（UTC+8）
        const now = new Date();
        // 获取UTC时间戳并转换为北京时间
        const utcTime = now.getTime() + (now.getTimezoneOffset() * 60 * 1000);
        const beijingTime = new Date(utcTime + (8 * 60 * 60 * 1000));
        
        const hours = beijingTime.getHours();
        const minutes = beijingTime.getMinutes();
        const seconds = beijingTime.getSeconds();
        
        // 计算下一个目标时间（每5分钟：00, 05, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55）
        const targetMinutes = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55];
        let nextTarget = null;
        let nextHour = hours;
        
        // 查找下一个目标分钟
        for (let i = 0; i < targetMinutes.length; i++) {
            if (targetMinutes[i] > minutes) {
                nextTarget = targetMinutes[i];
                break;
            }
        }
        
        // 如果当前分钟已经过了55，下一个目标是下一小时的00
        if (nextTarget === null) {
            nextTarget = 0;
            nextHour = (hours + 1) % 24;
        }
        
        // 计算剩余时间（秒）
        const currentTotalSeconds = hours * 3600 + minutes * 60 + seconds;
        const targetTotalSeconds = nextHour * 3600 + nextTarget * 60;
        
        let remainingSeconds = targetTotalSeconds - currentTotalSeconds;
        
        // 如果已经过了目标时间（跨天情况），加24小时
        if (remainingSeconds <= 0) {
            remainingSeconds += 24 * 3600;
        }
        
        // 转换为分:秒格式
        const mins = Math.floor(remainingSeconds / 60);
        const secs = remainingSeconds % 60;
        
        // 显示倒计时和目标时间
        const targetHourStr = nextHour.toString().padStart(2, '0');
        const targetMinStr = nextTarget.toString().padStart(2, '0');
        countdownText.textContent = `距离 ${targetHourStr}:${targetMinStr} 还有 ${mins}:${secs.toString().padStart(2, '0')}`;
        
        // 如果剩余时间少于1分钟，使用红色高亮
        if (remainingSeconds < 60) {
            countdownText.style.color = '#ff6b6b';
            countdownText.style.fontWeight = 'bold';
        } else {
            countdownText.style.color = '#666';
            countdownText.style.fontWeight = 'normal';
        }
    } catch (error) {
        console.error('倒计时计算错误:', error);
        countdownText.textContent = '计算中...';
    }
}

function startTradingLogRefresh() {
    // 立即加载一次
    loadTradingLogs();
    
    // 每2秒刷新一次交易日志
    tradingLogInterval = setInterval(() => {
        loadTradingLogs();
    }, 2000);
}

// 加载交易日志
async function loadTradingLogs() {
    try {
        const response = await fetch('/api/trading_logs');
        const data = await response.json();
        
        if (data.success && data.logs) {
            updateTradingLogs(data.logs);
        }
    } catch (error) {
        console.error('加载交易日志失败:', error);
    }
}

// ==================== 新增：信号准确率和资金曲线功能 ====================

// Chart.js 图表实例
let equityChart = null;
// ECharts 图表实例
let signalChart = null;

// 加载信号准确率统计
async function loadSignalAccuracy() {
    try {
        const response = await fetch('/api/signal_accuracy');
        const data = await response.json();
        
        if (data.success) {
            // 更新统计数字（只显示实盘数据）
            document.getElementById('totalTrades').textContent = data.total_trades || 0;
            document.getElementById('winningTrades').textContent = data.winning_trades || 0;
            document.getElementById('losingTrades').textContent = data.losing_trades || 0;
            document.getElementById('accuracyRate').textContent = (data.accuracy_rate || 0) + '%';
            
            // 更新信号分布图表（使用 ECharts，参考 alpha 项目）
            const signalChartDom = document.getElementById('signalChart');
            if (signalChartDom) {
                // 如果图表实例不存在，创建它
                if (!signalChart) {
                    signalChart = echarts.init(signalChartDom);
                }
                
                const signalOption = {
                    tooltip: { 
                        trigger: 'item',
                        formatter: '{b}: {c} ({d}%)'
                    },
                    legend: { 
                        show: false 
                    },
                    series: [
                        {
                            name: '信号分布',
                            type: 'pie',
                            radius: ['45%', '70%'],
                            itemStyle: { 
                                borderRadius: 5, 
                                borderColor: '#fff', 
                                borderWidth: 2 
                            },
                            label: { 
                                color: '#333',
                                fontSize: 12
                            },
                            data: [
                                { 
                                    value: data.signal_distribution.BUY || 0, 
                                    name: 'BUY',
                                    itemStyle: { color: '#51cf66' }
                                },
                                { 
                                    value: data.signal_distribution.SELL || 0, 
                                    name: 'SELL',
                                    itemStyle: { color: '#ff6b6b' }
                                },
                                { 
                                    value: data.signal_distribution.HOLD || 0, 
                                    name: 'HOLD',
                                    itemStyle: { color: '#ffa500' }
                                }
                            ]
                        }
                    ]
                };
                
                signalChart.setOption(signalOption, true);
            }
        }
    } catch (error) {
        console.error('加载信号准确率失败:', error);
    }
}

// 初始化资金曲线时间范围选择器
function initializeEquityRangeSelector() {
    const selector = document.getElementById('equityRangeSelector');
    if (!selector) return;
    
    selector.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-range]');
        if (!btn) return;
        
        currentEquityRange = btn.getAttribute('data-range');
        
        // 更新按钮状态
        selector.querySelectorAll('[data-range]').forEach(b => {
            b.classList.remove('active');
            b.style.background = '#f0f0f0';
        });
        btn.classList.add('active');
        btn.style.background = '#667eea';
        btn.style.color = '#fff';
        
        // 重新加载资金曲线
        loadEquityCurve();
    });
    
    // 设置默认选中状态
    const defaultBtn = selector.querySelector(`[data-range="${currentEquityRange}"]`);
    if (defaultBtn) {
        defaultBtn.style.background = '#667eea';
        defaultBtn.style.color = '#fff';
    }
}

// 加载资金曲线（优先使用新的overview接口，回退到旧的equity_curve接口）
async function loadEquityCurve() {
    try {
        // 优先尝试使用新的 /api/overview 接口（基于SQLite数据库）
        let response = await fetch(`/api/overview?range=${currentEquityRange}`);
        let data = await response.json();
        
        if (data.error) {
            // 如果新接口失败，回退到旧的接口
            console.warn('使用新接口失败，回退到旧接口:', data.error);
            response = await fetch('/api/equity_curve');
            data = await response.json();
            
            if (data.success) {
                // 使用旧接口的数据格式
                updateEquityStatsOld(data.stats);
                drawEquityChartOld(data.data);
            }
            return;
        }
        
        // 使用新接口的数据格式（多模型支持）
        if (data.aggregate && data.aggregate_series) {
            updateEquityStatsNew(data);
            drawEquityChartNew(data);
        } else if (data.series && Object.keys(data.series).length > 0) {
            // 有模型数据，使用第一个模型的数据
            const firstModelKey = Object.keys(data.series)[0];
            const modelData = data.series[firstModelKey];
            updateEquityStatsFromModel(modelData, data.models[firstModelKey]);
            drawEquityChartFromSeries(modelData);
        }
    } catch (error) {
        console.error('加载资金曲线失败:', error);
        // 回退到旧接口
    try {
        const response = await fetch('/api/equity_curve');
        const data = await response.json();
        if (data.success) {
                updateEquityStatsOld(data.stats);
                drawEquityChartOld(data.data);
            }
        } catch (fallbackError) {
            console.error('回退接口也失败:', fallbackError);
        }
    }
}

// 更新统计信息（新接口格式）
function updateEquityStatsNew(data) {
    const aggregate = data.aggregate || {};
    const totalEquity = aggregate.total_equity || 0;
    
    // 计算初始资金（从第一个数据点获取）
    let initialBalance = totalEquity;
    let maxBalance = totalEquity;
    let minBalance = totalEquity;
    
    if (data.aggregate_series && data.aggregate_series.length > 0) {
        const firstPoint = data.aggregate_series[0];
        const values = Object.values(firstPoint).filter(v => typeof v === 'number' && v > 0);
        if (values.length > 0) {
            initialBalance = values.reduce((a, b) => a + b, 0);
        }
        
        // 计算最大最小值
        data.aggregate_series.forEach(point => {
            const pointTotal = Object.values(point).filter(v => typeof v === 'number').reduce((a, b) => a + b, 0);
            if (pointTotal > maxBalance) maxBalance = pointTotal;
            if (pointTotal < minBalance) minBalance = pointTotal;
        });
    }
    
    const currentBalance = totalEquity;
    const totalReturn = ((currentBalance - initialBalance) / initialBalance * 100) || 0;
    
    // 计算最大回撤
    let maxDrawdown = 0;
    let peak = initialBalance;
    if (data.aggregate_series) {
        data.aggregate_series.forEach(point => {
            const pointTotal = Object.values(point).filter(v => typeof v === 'number').reduce((a, b) => a + b, 0);
            if (pointTotal > peak) peak = pointTotal;
            const drawdown = ((pointTotal - peak) / peak * 100) || 0;
            if (drawdown < maxDrawdown) maxDrawdown = drawdown;
        });
    }
    
    updateEquityStatsDisplay(initialBalance, currentBalance, totalReturn, maxDrawdown);
}

// 从单个模型数据更新统计
function updateEquityStatsFromModel(modelData, modelSummary) {
    if (!modelData || modelData.length === 0) return;
    
    const initialBalance = modelData[0].total_equity || 0;
    const latest = modelData[modelData.length - 1];
    const currentBalance = latest.total_equity || 0;
    const totalReturn = ((currentBalance - initialBalance) / initialBalance * 100) || 0;
    
    // 计算最大回撤
    let maxDrawdown = 0;
    let peak = initialBalance;
    modelData.forEach(point => {
        const equity = point.total_equity || 0;
        if (equity > peak) peak = equity;
        const drawdown = ((equity - peak) / peak * 100) || 0;
        if (drawdown < maxDrawdown) maxDrawdown = drawdown;
    });
    
    updateEquityStatsDisplay(initialBalance, currentBalance, totalReturn, maxDrawdown);
}

// 更新统计信息（旧接口格式）
function updateEquityStatsOld(stats) {
    updateEquityStatsDisplay(
        stats.initial_balance || 0,
        stats.current_balance || 0,
        stats.total_return || 0,
        stats.max_drawdown || 0
    );
}

// 统一更新统计信息显示
function updateEquityStatsDisplay(initial, current, returnPct, drawdown) {
    document.getElementById('initialBalance').textContent = '$' + initial.toFixed(2);
    document.getElementById('currentBalance').textContent = '$' + current.toFixed(2);
    
            const totalReturnEl = document.getElementById('totalReturn');
    totalReturnEl.textContent = (returnPct >= 0 ? '+' : '') + returnPct.toFixed(2) + '%';
    totalReturnEl.style.color = returnPct >= 0 ? '#51cf66' : '#ff6b6b';
            
            const maxDrawdownEl = document.getElementById('maxDrawdown');
    maxDrawdownEl.textContent = drawdown.toFixed(2) + '%';
    maxDrawdownEl.style.color = drawdown < -10 ? '#ff6b6b' : '#ffa500';
}

// 绘制图表（新接口格式 - 多模型）
function drawEquityChartNew(data) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    
    if (equityChart) {
        equityChart.destroy();
    }
    
    // 准备多模型数据
    const datasets = [];
    const colors = ['#667eea', '#f093fb', '#4facfe', '#43e97b', '#fa709a'];
    let colorIndex = 0;
    
    // 如果有aggregate_series，绘制总金额曲线
    if (data.aggregate_series && data.aggregate_series.length > 0) {
        const labels = data.aggregate_series.map(item => {
            const date = new Date(item.timestamp);
            return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        });
        
        const totalBalances = data.aggregate_series.map(item => {
            return Object.values(item).filter(v => typeof v === 'number').reduce((a, b) => a + b, 0);
        });
        
        datasets.push({
            label: '总权益',
            data: totalBalances,
            borderColor: colors[0],
            backgroundColor: 'rgba(102, 126, 234, 0.1)',
            borderWidth: 2,
            fill: true,
            tension: 0.4
        });
        
        equityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: datasets
            },
            options: getChartOptions()
        });
    }
}

// 从单个模型系列绘制图表
function drawEquityChartFromSeries(seriesData) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    
    if (equityChart) {
        equityChart.destroy();
    }
    
    const labels = seriesData.map(item => {
        const date = new Date(item.timestamp);
        return date.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    });
    
    const balances = seriesData.map(item => item.total_equity || 0);
    
    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '账户余额',
                data: balances,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 2,
                pointHoverRadius: 4
            }]
        },
        options: getChartOptions()
    });
}

// 绘制图表（旧接口格式）
function drawEquityChartOld(equityData) {
    const ctx = document.getElementById('equityChart').getContext('2d');
    
    if (equityChart) {
        equityChart.destroy();
    }
    
    const labels = equityData.map(item => {
        const date = new Date(item.timestamp);
        return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
    });
    
    const balances = equityData.map(item => item.balance);
    
    equityChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '账户余额',
                data: balances,
                borderColor: '#667eea',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 5
            }]
        },
        options: getChartOptions()
    });
}

// 统一的图表配置
function getChartOptions() {
    return {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#333',
                    font: { size: 12 }
                    }
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: '#fff',
                    bodyColor: '#fff',
                    borderColor: '#667eea',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                        return context.dataset.label + ': $' + context.parsed.y.toFixed(2);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        color: '#666',
                        callback: function(value) {
                            return '$' + value.toFixed(0);
                        }
                    },
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    }
                },
                x: {
                    ticks: {
                        color: '#666',
                        maxRotation: 45,
                        minRotation: 45,
                    font: { size: 10 }
                    },
                    grid: {
                        display: false
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
    };
}

// 保留旧的函数名作为别名（向后兼容）
function drawEquityChart(equityData) {
    drawEquityChartOld(equityData);
}

// 加载AI决策历史
async function loadAIDecisions() {
    const container = document.getElementById('aiDecisionList');
    if (!container) {
        console.error('AI决策容器不存在');
        return;
    }
    
    try {
        // 不传递 symbol 参数，获取所有交易对的合并数据
        const response = await fetch('/api/ai_decisions');
        
        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
        }
        
        const decisions = await response.json();
        
        console.log('AI决策数据:', decisions);
        console.log('AI决策数据类型:', typeof decisions);
        console.log('AI决策数据长度:', Array.isArray(decisions) ? decisions.length : '不是数组');
        
        // 检查返回的数据格式
        if (!Array.isArray(decisions)) {
            console.error('AI决策数据格式错误，期望数组，实际:', typeof decisions, decisions);
            // 如果容器已有内容，保留它；否则显示空状态
            if (!container.innerHTML || container.innerHTML.includes('加载失败')) {
                container.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">暂无AI决策记录</div>';
            }
            return;
        }

        if (decisions.length === 0) {
            console.warn('AI决策数据为空数组');
            container.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">暂无AI决策记录</div>';
            return;
        }
        
        console.log('准备显示', decisions.length, '条AI决策记录');
        console.log('第一条决策:', decisions[0]);

        // 数据已经是按时间倒序排列的（最新的在前），直接取前10条显示
        container.innerHTML = decisions.slice(0, 10).map((decision) => {
            const signal = (decision.signal || 'HOLD').toUpperCase();
            const confidence = (decision.confidence || 'MEDIUM').toUpperCase();
            const reason = decision.reason || '无理由说明';
            const price = (decision.price || 0).toFixed(2);
            const timestamp = decision.timestamp || '--';
            
            return `
                <div class="ai-decision-card">
                    <div class="decision-header">
                        <span class="decision-signal decision-signal-${signal.toLowerCase()}">${signal}</span>
                        <span class="decision-confidence decision-confidence-${confidence.toLowerCase()}">${confidence}</span>
                    </div>
                    <div class="decision-body">
                        <div class="decision-reason">${reason}</div>
                        <div class="decision-details">价格:$${price} 时间:${timestamp}</div>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('加载AI决策失败:', error);
        // 只有在容器为空或显示错误时才更新，避免覆盖已有数据
        const currentContent = container.innerHTML;
        if (!currentContent || currentContent.includes('加载失败') || currentContent.includes('加载中')) {
            container.innerHTML = '<div style="text-align: center; color: #ff6b6b; padding: 20px;">加载失败: ' + error.message + '</div>';
        } else {
            // 保留现有内容，只记录错误
            console.warn('AI决策加载失败，保留现有数据显示');
        }
    }
}

// 加载交易记录
async function loadTrades() {
    const container = document.getElementById('tradeHistory');
    if (!container) {
        console.error('交易记录容器不存在');
        return;
    }
    
    try {
        // 不传递 symbol 参数，获取所有交易对的合并数据
        const response = await fetch('/api/trades');
        
        if (!response.ok) {
            throw new Error(`HTTP错误: ${response.status} ${response.statusText}`);
        }
        
        const trades = await response.json();
        
        console.log('交易记录数据:', trades);
        
        // 检查返回的数据格式
        if (!Array.isArray(trades)) {
            console.error('交易记录数据格式错误，期望数组，实际:', typeof trades, trades);
            // 如果容器已有内容，保留它；否则显示空状态
            if (!container.innerHTML || container.innerHTML.includes('加载失败')) {
                container.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">暂无交易记录</div>';
            }
            return;
        }

        if (trades.length === 0) {
            container.innerHTML = '<div style="text-align: center; color: #999; padding: 20px;">暂无交易记录</div>';
            return;
        }

        // 数据已经是按时间倒序排列的（最新的在前），直接显示所有数据
        container.innerHTML = trades.map((trade) => {
            const sideColor = trade.side === 'long' || trade.side === 'buy' ? '#51cf66' : 
                            trade.side === 'short' || trade.side === 'sell' ? '#ff6b6b' : '#999';
            const pnlColor = trade.pnl > 0 ? '#51cf66' : trade.pnl < 0 ? '#ff6b6b' : '#999';
            const pnlDisplay = trade.pnl > 0 ? '+' : '';
            const pnlValue = (trade.pnl || 0).toFixed(2);
            const pnlRatioText = trade.pnlRatio !== undefined && trade.pnlRatio !== 0 
                ? ` (${(trade.pnlRatio * 100).toFixed(2)}%)` 
                : '';
            
            // 如果有开仓价和平仓价，显示更详细的信息
            const hasOpenClose = trade.openAvgPx !== undefined && trade.closeAvgPx !== undefined;
            const priceDisplay = hasOpenClose 
                ? `开: $${(trade.openAvgPx || 0).toFixed(2)} → 平: $${(trade.closeAvgPx || trade.price || 0).toFixed(2)}`
                : `$${(trade.price || 0).toFixed(2)}`;
            
            return `
                <div class="trade-item" style="padding: 12px; margin-bottom: 12px; border-left: 4px solid ${sideColor}; background: #f9f9f9; border-radius: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span style="padding: 4px 10px; background: ${sideColor}; color: white; border-radius: 4px; font-size: 12px; font-weight: bold;">${(trade.side || '--').toUpperCase()}</span>
                        <span style="font-weight: bold; color: ${pnlColor}; font-size: 16px; font-weight: 700;">
                            ${pnlDisplay}${pnlValue} USDT${pnlRatioText}
                        </span>
                    </div>
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-weight: 600; color: ${sideColor}; font-size: 13px;">${priceDisplay}</span>
                        <span style="font-size: 11px; color: #666;">${trade.timestamp || '--'}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; font-size: 11px; color: #666;">
                        <span>数量: ${(trade.amount || 0).toFixed(4)}</span>
                        <span>杠杆: ${trade.leverage || '--'}x</span>
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('加载交易记录失败:', error);
        // 只有在容器为空或显示错误时才更新，避免覆盖已有数据
        const currentContent = container.innerHTML;
        if (!currentContent || currentContent.includes('加载失败') || currentContent.includes('加载中')) {
            container.innerHTML = '<div style="text-align: center; color: #ff6b6b; padding: 20px;">加载失败: ' + error.message + '</div>';
        } else {
            // 保留现有内容，只记录错误
            console.warn('交易记录加载失败，保留现有数据显示');
        }
    }
}


// 更新新功能数据
// 防止并发请求的标志
let isLoadingAIDecisions = false;
let isLoadingTrades = false;

function updateNewFeatures() {
    // 使用 Promise.all 并行加载，但避免重复请求
    const promises = [];
    
    if (!isLoadingAIDecisions) {
        isLoadingAIDecisions = true;
        promises.push(
            loadAIDecisions().finally(() => {
                isLoadingAIDecisions = false;
            })
        );
    }
    
    if (!isLoadingTrades) {
        isLoadingTrades = true;
        promises.push(
            loadTrades().finally(() => {
                isLoadingTrades = false;
            })
        );
    }
    
    // 其他功能可以并行加载
    loadSignalAccuracy();
    loadEquityCurve();
    
    // 等待异步操作完成
    Promise.all(promises).catch(error => {
        console.error('更新新功能数据失败:', error);
    });
}

// 修改原有的loadInitialData函数，添加新功能加载
const originalLoadInitialData = loadInitialData;
loadInitialData = function() {
    originalLoadInitialData();
    updateNewFeatures();
};

// 修改原有的自动刷新，添加新功能
const originalStartAutoRefresh = startAutoRefresh;
startAutoRefresh = function() {
    originalStartAutoRefresh();
    
    // 每30秒刷新一次统计数据
    setInterval(() => {
        if (document.getElementById('autoRefresh').checked) {
            updateNewFeatures();
        }
    }, 30000);
};

// 更新交易日志显示（最新的在上方）
function updateTradingLogs(logs) {
    const logContent = document.getElementById('logContent');
    
    // 清空现有日志
    logContent.innerHTML = '';
    
    // 反转日志顺序，让最新的在上方
    const reversedLogs = logs.slice().reverse();
    
    // 添加新日志
    reversedLogs.forEach(log => {
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        
        // 尝试多种日志格式解析
        let timeOnly = '';
        let message = log;
        let level = 'INFO';
        
        // 格式1: "2025-10-28 19:14:07 - INFO - 消息内容"
        let logMatch = log.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - (.+)$/);
        
        // 格式2: "2025-11-05T17:42:02: 消息内容" (PM2格式)
        if (!logMatch) {
            logMatch = log.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}):\s*(.+)$/);
        if (logMatch) {
                const [, timestamp, msg] = logMatch;
                timeOnly = timestamp.split('T')[1].split(':').slice(0, 3).join(':');
                message = msg.trim();
            }
        }
        
        // 格式3: "2025-11-05 17:42:02,123 - INFO - 消息内容" (带毫秒)
        if (!logMatch) {
            logMatch = log.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ - (\w+) - (.+)$/);
        }
        
        // 格式4: "[2025-11-05 17:42:02] 消息内容"
        if (!logMatch) {
            logMatch = log.match(/^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]\s*(.+)$/);
            if (logMatch) {
                const [, timestamp, msg] = logMatch;
                timeOnly = timestamp.split(' ')[1];
                message = msg.trim();
            }
        }
        
        // 如果匹配到标准格式
        if (logMatch && !timeOnly) {
            const [, timestamp, lvl, msg] = logMatch;
            timeOnly = timestamp.split(' ')[1] || timestamp.split('T')[1]?.split(':').slice(0, 3).join(':') || '';
            level = lvl || 'INFO';
            message = msg || message;
        }
        
        // 如果还是没有时间，尝试从日志中提取任意时间格式
        if (!timeOnly) {
            const timeMatch = log.match(/(\d{2}:\d{2}:\d{2})/);
            timeOnly = timeMatch ? timeMatch[1] : '';
        }
        
        // 如果还是没有时间，尝试从当前时间生成（作为最后手段）
        if (!timeOnly) {
            const now = new Date();
            timeOnly = now.toTimeString().split(' ')[0];
        }
        
        // 从消息内容中移除时间戳（避免重复显示）
        // 移除类似 "2025-11-05T17:55:06:" 或 "2025-11-05 17:55:06" 的格式
        message = message.replace(/^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[:,]?\s*/g, '');
        message = message.replace(/^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}[,\s]*-?\s*/g, '');
        message = message.trim();
        
        // 过滤空日志条目：如果消息为空或只包含空白字符，跳过不显示
        if (!message || message.length === 0) {
            return;
        }
        
        // 处理分割线：如果消息是多个等号或减号，缩短为固定长度
        if (/^[=\-]{10,}$/.test(message)) {
            message = '════════════════════════════════';
        }
            
            // 根据日志级别选择图标
            let iconClass = 'fas fa-info-circle';
        if (level === 'ERROR' || message.includes('错误') || message.includes('失败') || message.includes('❌')) {
                iconClass = 'fas fa-exclamation-triangle';
                logEntry.style.color = '#ff6b6b';
        } else if (level === 'WARNING' || message.includes('警告') || message.includes('⚠️')) {
                iconClass = 'fas fa-exclamation-circle';
                logEntry.style.color = '#ffa500';
            } else if (message.includes('BUY') || message.includes('买入') || message.includes('多仓')) {
                iconClass = 'fas fa-arrow-up';
                logEntry.style.color = '#51cf66';
            } else if (message.includes('SELL') || message.includes('卖出') || message.includes('空仓')) {
                iconClass = 'fas fa-arrow-down';
                logEntry.style.color = '#ff6b6b';
            } else if (message.includes('价格') || message.includes('BTC')) {
                iconClass = 'fas fa-chart-line';
            } else if (message.includes('持仓') || message.includes('仓位')) {
                iconClass = 'fas fa-wallet';
        } else if (message.includes('成功') || message.includes('完成') || message.includes('✅')) {
                iconClass = 'fas fa-check-circle';
                logEntry.style.color = '#51cf66';
            }
            
            logEntry.innerHTML = `
            <span class="log-time">${timeOnly}</span>
                <i class="${iconClass}"></i>
            <span class="log-message">${message}</span>
        `;
        
        logContent.appendChild(logEntry);
    });
    
    // 保持在顶部（最新日志可见）
    const logContainer = document.querySelector('.log-container');
    if (logContainer) {
        logContainer.scrollTop = 0;
    }
    lastLogCount = logs.length;
}

// 页面卸载时清理
window.addEventListener('beforeunload', function() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }
    if (runningTimeInterval) {
        clearInterval(runningTimeInterval);
    }
    if (tradingLogInterval) {
        clearInterval(tradingLogInterval);
    }
    if (socket) {
        socket.disconnect();
    }
});
