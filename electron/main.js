const { app, BrowserWindow, Tray, Menu, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let tray;
let flaskProcess;
let isAlwaysOnTop = false;

function startFlask() {
    const pythonPath = path.join(__dirname, '..', '..', 'venv', 'bin', 'python3');
    const appPath = path.join(__dirname, '..', 'app.py');
    
    flaskProcess = spawn('python3', [appPath, '--no-window'], {
        cwd: path.join(__dirname, '..'),
        env: { ...process.env, FLASK_ENV: 'production' }
    });
    
    flaskProcess.stdout.on('data', (data) => {
        console.log(`Flask: ${data}`);
    });
    
    flaskProcess.stderr.on('data', (data) => {
        console.log(`Flask: ${data}`);
    });
}

function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 800,
        minHeight: 600,
        title: 'API Key 管理器',
        icon: path.join(__dirname, 'icon.png'),
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        },
        titleBarStyle: 'hiddenInset',
        backgroundColor: '#0c0c1d'
    });

    // 等待Flask启动后加载
    setTimeout(() => {
        mainWindow.loadURL('http://127.0.0.1:8899');
    }, 2000);

    // 创建菜单
    const menuTemplate = [
        {
            label: 'API Key 管理器',
            submenu: [
                { role: 'about' },
                { type: 'separator' },
                { role: 'quit' }
            ]
        },
        {
            label: '窗口',
            submenu: [
                { role: 'minimize' },
                { role: 'zoom' },
                { type: 'separator' },
                {
                    label: '窗口置顶',
                    type: 'checkbox',
                    checked: false,
                    click: (menuItem) => {
                        isAlwaysOnTop = menuItem.checked;
                        mainWindow.setAlwaysOnTop(isAlwaysOnTop);
                    }
                },
                { type: 'separator' },
                { role: 'togglefullscreen' }
            ]
        },
        {
            label: '编辑',
            submenu: [
                { role: 'undo' },
                { role: 'redo' },
                { type: 'separator' },
                { role: 'cut' },
                { role: 'copy' },
                { role: 'paste' },
                { role: 'selectAll' }
            ]
        },
        {
            label: '视图',
            submenu: [
                { role: 'reload' },
                { role: 'forceReload' },
                { role: 'toggleDevTools' },
                { type: 'separator' },
                { role: 'resetZoom' },
                { role: 'zoomIn' },
                { role: 'zoomOut' }
            ]
        }
    ];

    const menu = Menu.buildFromTemplate(menuTemplate);
    Menu.setApplicationMenu(menu);

    // 系统托盘
    const trayIcon = nativeImage.createFromPath(path.join(__dirname, 'icon.png'));
    tray = new Tray(trayIcon.resize({ width: 16, height: 16 }));
    
    const contextMenu = Menu.buildFromTemplate([
        {
            label: '显示窗口',
            click: () => {
                mainWindow.show();
                mainWindow.focus();
            }
        },
        {
            label: '窗口置顶',
            type: 'checkbox',
            checked: isAlwaysOnTop,
            click: (menuItem) => {
                isAlwaysOnTop = menuItem.checked;
                mainWindow.setAlwaysOnTop(isAlwaysOnTop);
            }
        },
        { type: 'separator' },
        {
            label: '退出',
            click: () => {
                app.isQuitting = true;
                app.quit();
            }
        }
    ]);
    
    tray.setToolTip('API Key 管理器');
    tray.setContextMenu(contextMenu);
    
    tray.on('click', () => {
        mainWindow.show();
        mainWindow.focus();
    });

    // 关闭时最小化到托盘
    mainWindow.on('close', (event) => {
        if (!app.isQuitting) {
            event.preventDefault();
            mainWindow.hide();
        }
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

app.on('ready', () => {
    startFlask();
    createWindow();
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('activate', () => {
    if (mainWindow === null) {
        createWindow();
    }
});

app.on('before-quit', () => {
    app.isQuitting = true;
    if (flaskProcess) {
        flaskProcess.kill();
    }
});
