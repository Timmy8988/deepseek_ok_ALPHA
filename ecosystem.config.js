module.exports = {
  apps: [
    {
      name: 'dsok-web',
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
      error_file: '/dsok/logs/pm2-web-error.log',
      out_file: '/dsok/logs/pm2-web-out.log',
      log_file: '/dsok/logs/pm2-web-combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      kill_timeout: 5000,
      wait_ready: false,
      listen_timeout: 10000
    },
    {
      name: 'dsok-bot',
      script: 'deepseek_ok_3.0.py',
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
      error_file: '/dsok/logs/pm2-bot-error.log',
      out_file: '/dsok/logs/pm2-bot-out.log',
      log_file: '/dsok/logs/pm2-bot-combined.log',
      time: true,
      merge_logs: true,
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z',
      kill_timeout: 5000,
      wait_ready: false,
      listen_timeout: 10000
    }
  ]
};


