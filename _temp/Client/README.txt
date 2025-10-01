ITLOG Device Manager - Deployment Guide
=====================================

How to run:
  ITLOG_Device_Manager.exe

Required files:
  - ITLOG_Device_Manager.exe  (executable file)
  - templates/                (HTML template folder)
  - static/                   (CSS, JS, image folder)
  - config_sensor.json        (sensor config file)
  - .env                      (environment config file)
  - sensor.db                 (database file, optional)

Configuration check:
  1. Check DATABASE_PATH=./ in .env file
  2. Set EXE_MODE=SERVER or CLIENT in .env file
  3. Allow port 5000 in firewall

Access URL:
  http://localhost:5000
  or
  http://<server-IP>:5000

Troubleshooting:
  - sensor.db file will be created automatically if not exists
  - Change port in config_sensor.json if port conflict occurs
  - Check logs in console window
