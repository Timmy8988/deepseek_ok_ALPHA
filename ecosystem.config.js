// PM2 配置文件
// 项目部署路径：/dsok
// 同时启动Web服务器和交易机器人（合并为一个进程）

module.exports = {
  apps: [
    {
      name: 'dsok',
      script: 'app.py',
      interpreter: '/dsok/venv/bin/python3',
      cwd: '/dsok',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '1G',
      env: {
        NODE_ENV: 'production',
        PYTHONUNBUFFERED: '1'
      },
      error_file: '/dsok/logs/pm2-error.log',
      out_file: '/dsok/logs/pm2-out.log',
      log_file: '/dsok/logs/pm2-combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      kill_timeout: 5000,
      wait_ready: false,
      listen_timeout: 10000,
      exec_mode: 'fork'
    }
  ]
};


