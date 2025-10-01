#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import socket
import threading
import time
import os
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                            QWidget, QLabel, QLineEdit, QPushButton, QComboBox, 
                            QTextEdit, QSpinBox, QCheckBox, QTabWidget, QFormLayout,
                            QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView,
                            QMessageBox, QSplitter, QFrame)
from PyQt5.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt5.QtGui import QFont, QTextCursor, QColor

class SocketServerThread(QThread):
    """소켓 서버 스레드"""
    client_connected = pyqtSignal(str, int)
    client_disconnected = pyqtSignal(str, int)
    data_received = pyqtSignal(str, str, str)  # client_addr, data, timestamp
    log_message = pyqtSignal(str)
    
    def __init__(self, host, port, parent=None):
        super().__init__(parent)
        self.host = host
        self.port = port
        self.server_socket = None
        self.running = False
        self.clients = {}  # {socket: (addr, port)}
        self.client_threads = []
        
    def run(self):
        """서버 실행"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)
            self.server_socket.settimeout(1.0)
            
            self.running = True
            self.log_message.emit(f"서버 시작: {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, client_addr = self.server_socket.accept()
                    client_socket.settimeout(30.0)
                    
                    self.clients[client_socket] = client_addr
                    self.client_connected.emit(client_addr[0], client_addr[1])
                    
                    # 클라이언트 핸들러 스레드 시작
                    client_thread = ClientHandlerThread(client_socket, client_addr, self)
                    client_thread.data_received.connect(self.data_received.emit)
                    client_thread.client_disconnected.connect(self.on_client_disconnect)
                    client_thread.log_message.connect(self.log_message.emit)
                    client_thread.start()
                    self.client_threads.append(client_thread)
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        self.log_message.emit(f"클라이언트 접속 오류: {e}")
                        
        except Exception as e:
            self.log_message.emit(f"서버 시작 실패: {e}")
            
    def on_client_disconnect(self, client_socket, addr, port):
        """클라이언트 연결 해제 처리"""
        if client_socket in self.clients:
            del self.clients[client_socket]
        self.client_disconnected.emit(addr, port)
        
    def send_to_client(self, client_socket, data):
        """특정 클라이언트에 데이터 전송"""
        try:
            if client_socket in self.clients:
                client_socket.send(data.encode('utf-8'))
                return True
        except Exception as e:
            self.log_message.emit(f"클라이언트 전송 오류: {e}")
        return False
        
    def broadcast_to_all(self, data):
        """모든 클라이언트에 브로드캐스트"""
        # 연결된 클라이언트가 없으면 브로드캐스트하지 않음
        if len(self.clients) == 0:
            return False
            
        disconnected_clients = []
        for client_socket in list(self.clients.keys()):
            try:
                client_socket.send(data.encode('utf-8'))
            except:
                disconnected_clients.append(client_socket)
                
        for client_socket in disconnected_clients:
            if client_socket in self.clients:
                addr = self.clients[client_socket]
                del self.clients[client_socket]
                self.client_disconnected.emit(addr[0], addr[1])
        
        return True
                
    def stop_server(self):
        """서버 중지"""
        self.running = False
        
        # 모든 클라이언트 스레드 종료
        for thread in self.client_threads:
            thread.stop()
            thread.wait(1000)
            
        # 모든 클라이언트 소켓 닫기
        for client_socket in list(self.clients.keys()):
            try:
                client_socket.close()
            except:
                pass
                
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        self.log_message.emit("서버 중지됨")

class ClientHandlerThread(QThread):
    """클라이언트 핸들러 스레드"""
    data_received = pyqtSignal(str, str, str)
    client_disconnected = pyqtSignal(object, str, int)
    log_message = pyqtSignal(str)
    
    def __init__(self, client_socket, client_addr, parent=None):
        super().__init__(parent)
        self.client_socket = client_socket
        self.client_addr = client_addr
        self.running = False
        
    def run(self):
        """클라이언트 데이터 수신 처리"""
        self.running = True
        client_info = f"{self.client_addr[0]}:{self.client_addr[1]}"
        
        try:
            while self.running:
                try:
                    data = self.client_socket.recv(1024)
                    if not data:
                        break
                        
                    received_data = data.decode('utf-8').strip()
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    self.data_received.emit(client_info, received_data, timestamp)
                    self.log_message.emit(f"[{client_info}] 수신: {received_data}")
                    
                except socket.timeout:
                    continue
                except Exception as e:
                    self.log_message.emit(f"[{client_info}] 수신 오류: {e}")
                    break
                    
        except Exception as e:
            self.log_message.emit(f"[{client_info}] 클라이언트 처리 오류: {e}")
            
        finally:
            try:
                self.client_socket.close()
            except:
                pass
            self.client_disconnected.emit(self.client_socket, self.client_addr[0], self.client_addr[1])
            
    def stop(self):
        """클라이언트 핸들러 중지"""
        self.running = False

class SensorDataSimulator(QThread):
    """센서 데이터 시뮬레이터"""
    send_data = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.running = False
        self.interval = 1.0
        self.sensor_type = "PM"
        self.device_id = "1"
        self.sensor_templates = {}
        self.load_sensor_templates()
        
    def load_sensor_templates(self):
        """센서 템플릿 로드 - 실제 센서 데이터 포맷 사용"""
        self.sensor_templates = {
            "PM": {
                "format": "{device_id}|PM||{pm25},{pm25_max},{pm25_avg},{pm25_month},{pm25_status},{pm25_forecast},{pm10},{pm10_max},{pm10_avg},{pm10_month},{pm10_status},{pm10_forecast},,,^192.168.0.27",
                "values": {
                    "pm25": lambda: f"{__import__('random').randint(10, 80)}",
                    "pm25_max": lambda: f"{__import__('random').randint(20, 100)}",
                    "pm25_avg": lambda: f"{__import__('random').randint(15, 60)}",
                    "pm25_month": lambda: f"{__import__('random').randint(18, 50)}",
                    "pm25_status": lambda: __import__('random').choice(["N", "G", "W", "D"]),
                    "pm25_forecast": lambda: f"{__import__('random').randint(0, 10)}",
                    "pm10": lambda: f"{__import__('random').randint(30, 150)}",
                    "pm10_max": lambda: f"{__import__('random').randint(50, 200)}",
                    "pm10_avg": lambda: f"{__import__('random').randint(35, 120)}",
                    "pm10_month": lambda: f"{__import__('random').randint(40, 100)}",
                    "pm10_status": lambda: __import__('random').choice(["N", "G", "W", "D"]),
                    "pm10_forecast": lambda: f"{__import__('random').randint(0, 10)}"
                }
            },
            "SOUND": {
                "format": "{device_id}|SOUND||{current},{max},{avg},{month},{status}^192.168.0.27",
                "values": {
                    "current": lambda: f"{__import__('random').uniform(40, 80):.1f}",
                    "max": lambda: f"{__import__('random').uniform(70, 95):.1f}",
                    "avg": lambda: f"{__import__('random').uniform(45, 75):.1f}",
                    "month": lambda: f"{__import__('random').uniform(50, 70):.1f}",
                    "status": lambda: __import__('random').choice(["N", "G", "W", "D"])
                }
            },
            "VIBRO": {
                "format": "{device_id}|VIBRO||{current},{max},{avg},{month},{status}^192.168.0.27",
                "values": {
                    "current": lambda: f"{__import__('random').uniform(0, 50):.1f}",
                    "max": lambda: f"{__import__('random').uniform(0, 10):.1f}",
                    "avg": lambda: f"{__import__('random').uniform(0, 5):.1f}",
                    "month": lambda: f"{__import__('random').uniform(10, 40):.1f}",
                    "status": lambda: __import__('random').choice(["N", "G", "W", "D"])
                }
            },
            "TILT": {
                "format": "{device_id}|TILT||{current},{max},{avg},{month},{status}^192.168.0.27",
                "values": {
                    "current": lambda: f"{__import__('random').uniform(0, 5):.1f}",
                    "max": lambda: f"{__import__('random').uniform(0, 2):.1f}",
                    "avg": lambda: f"{__import__('random').uniform(0, 1):.1f}",
                    "month": lambda: f"{__import__('random').uniform(0, 2):.1f}",
                    "status": lambda: __import__('random').choice(["N", "G", "W", "D"])
                }
            },
            "CRACK": {
                "format": "{device_id}|CRACK|MINUO|{current},{max},{avg},{month},{status}^192.168.0.27",
                "values": {
                    "current": lambda: f"{__import__('random').uniform(5, 15):.1f}",
                    "max": lambda: f"{__import__('random').uniform(20, 50):.1f}",
                    "avg": lambda: f"{__import__('random').uniform(25, 45):.1f}",
                    "month": lambda: f"{__import__('random').uniform(0, 2):.1f}",
                    "status": lambda: __import__('random').choice(["N", "G", "W", "D"])
                }
            },
            "WIND": {
                "format": "{device_id}|WIND|UltraSonic|{speed},{speed_max},{speed_avg},{speed_month},{status},{direction_angle},{direction}^192.168.0.27",
                "values": {
                    "speed": lambda: f"{__import__('random').uniform(0, 15):.1f}",
                    "speed_max": lambda: f"{__import__('random').uniform(5, 20):.1f}",
                    "speed_avg": lambda: f"{__import__('random').uniform(2, 10):.1f}",
                    "speed_month": lambda: f"{__import__('random').uniform(3, 8):.1f}",
                    "status": lambda: __import__('random').choice(["N", "G", "W", "D"]),
                    "direction_angle": lambda: f"{__import__('random').randint(0, 359)}",
                    "direction": lambda: __import__('random').choice(["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
                }
            },
            "O2": {
                "format": "{device_id}|O2|PER|{per1}_{ppm1}_{temp1}_{at1},{per_max},{per_avg},{per_month},{status}|{per2}_{ppm2}_{temp2}_{at2}^192.168.0.27",
                "values": {
                    "per1": lambda: f"{__import__('random').uniform(18, 22):.2f}",
                    "ppm1": lambda: f"{__import__('random').randint(200, 300)}",
                    "temp1": lambda: f"{__import__('random').randint(20, 40)}",
                    "at1": lambda: f"{__import__('random').randint(1000, 1500)}",
                    "per_max": lambda: f"{__import__('random').uniform(20, 24):.2f}",
                    "per_avg": lambda: f"{__import__('random').uniform(19, 21):.2f}",
                    "per_month": lambda: f"{__import__('random').uniform(19.5, 20.5):.2f}",
                    "status": lambda: __import__('random').choice(["N", "G", "W", "D"]),
                    "per2": lambda: f"{__import__('random').uniform(18, 22):.2f}",
                    "ppm2": lambda: f"{__import__('random').randint(200, 300)}",
                    "temp2": lambda: f"{__import__('random').randint(20, 40)}",
                    "at2": lambda: f"{__import__('random').randint(1000, 1500)}"
                }
            },
            "MQ": {
                "format": "{device_id}|MQ|LPG|{lpg1}_{co1}_{smoke1},{lpg_max},{lpg_avg},{lpg_month},{status1}_{status2}_{status3}|{lpg2}_{co2}_{smoke2}^192.168.0.27",
                "values": {
                    "lpg1": lambda: f"{__import__('random').randint(20, 80)}",
                    "co1": lambda: f"{__import__('random').randint(500, 800)}",
                    "smoke1": lambda: f"{__import__('random').randint(100, 300)}",
                    "lpg_max": lambda: f"{__import__('random').randint(0, 10)}",
                    "lpg_avg": lambda: f"{__import__('random').randint(0, 5)}",
                    "lpg_month": lambda: f"{__import__('random').randint(100, 300)}",
                    "status1": lambda: __import__('random').choice(["N", "G", "W", "D"]),
                    "status2": lambda: __import__('random').choice(["N", "G", "W", "D"]),
                    "status3": lambda: __import__('random').choice(["N", "G", "W", "D"]),
                    "lpg2": lambda: f"{__import__('random').randint(20, 80)}",
                    "co2": lambda: f"{__import__('random').randint(500, 800)}",
                    "smoke2": lambda: f"{__import__('random').randint(100, 300)}"
                }
            },
            "NOX": {
                "format": "{device_id}|NOX|NO2|{no2}_{co},{no2_max},{no2_avg},{no2_month},{status1}_{status2}^192.168.0.27",
                "values": {
                    "no2": lambda: f"{__import__('random').uniform(0, 0.1):.3f}",
                    "co": lambda: f"{__import__('random').randint(500, 800)}",
                    "no2_max": lambda: f"{__import__('random').uniform(0, 0.05):.3f}",
                    "no2_avg": lambda: f"{__import__('random').uniform(0, 0.02):.3f}",
                    "no2_month": lambda: f"{__import__('random').uniform(0.01, 0.08):.3f}",
                    "status1": lambda: __import__('random').choice(["N", "G", "W", "D"]),
                    "status2": lambda: __import__('random').choice(["N", "G", "W", "D"])
                }
            },
            "GASM": {
                "format": "{device_id}|GASM|WMKY2000|{gas1},{temp1},{hum1},{pres1},{status1}|{gas2},{temp2},{hum2},{pres2},{status2}|{gas3},{temp3},{hum3},{pres3},{status3}|{gas4},{temp4},{hum4},{pres4},{status4}|{gas5},{temp5},{hum5},{pres5},{status5}|{gas6},{temp6},{hum6},{pres6},{status6}|{gas7},{temp7},{hum7},{pres7},{status7}|{gas8},{temp8},{hum8},{pres8},{status8}^192.168.0.27",
                "values": {
                    **{f"gas{i}": (lambda i=i: lambda: f"{__import__('random').uniform(0, 50):.6f}")() for i in range(1, 9)},
                    **{f"temp{i}": (lambda i=i: lambda: f"{__import__('random').randint(20, 80)}")() for i in range(1, 9)},
                    **{f"hum{i}": (lambda i=i: lambda: f"{__import__('random').randint(15, 40)}")() for i in range(1, 9)},
                    **{f"pres{i}": (lambda i=i: lambda: f"{__import__('random').randint(15, 40)}")() for i in range(1, 9)},
                    **{f"status{i}": (lambda i=i: lambda: __import__('random').choice(["-1", "1"]))() for i in range(1, 9)}
                }
            }
        }
        
    def set_config(self, sensor_type, device_id, interval):
        """시뮬레이터 설정"""
        self.sensor_type = sensor_type
        self.device_id = device_id
        self.interval = interval
        
    def run(self):
        """시뮬레이터 실행"""
        self.running = True
        while self.running:
            if self.sensor_type in self.sensor_templates:
                template = self.sensor_templates[self.sensor_type]
                
                # 템플릿 값 생성
                values = {"device_id": self.device_id}
                for key, func in template["values"].items():
                    values[key] = func()
                
                # 데이터 포맷 생성
                data = template["format"].format(**values)
                self.send_data.emit(data)
                
            time.sleep(self.interval)
            
    def stop(self):
        """시뮬레이터 중지"""
        self.running = False

class SocketServerTestApp(QMainWindow):
    """소켓 서버 테스트 애플리케이션"""
    
    def __init__(self):
        super().__init__()
        # PyInstaller 빌드 시 실행 파일과 같은 디렉토리에서 config 파일 찾기
        if getattr(sys, 'frozen', False):
            # 빌드된 실행 파일인 경우
            application_path = os.path.dirname(sys.executable)
        else:
            # 개발 환경인 경우
            application_path = os.path.dirname(os.path.abspath(__file__))
        
        self.config_file = os.path.join(application_path, "config_socket.json")
        self.config = self.load_config()
        self.server_thread = None
        self.simulator_thread = None
        self.init_ui()
        self.load_settings()
        
    def load_config(self):
        """설정 파일 로드"""
        default_config = {
            "server": {
                "host": "127.0.0.1",
                "port": 3000,
                "max_connections": 10,
                "timeout": 30,
                "keepalive": True,
                "buffer_size": 1024
            },
            "simulator": {
                "enabled": True,
                "interval": 1.0,
                "sensor_type": "SOUND",
                "device_id": "1",
                "auto_start": False
            },
            "logging": {
                "enabled": True,
                "max_lines": 1000,
                "timestamp": True
            },
            "ui": {
                "font_size": 9,
                "auto_scroll": True,
                "show_connection_count": True
            }
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                    # 기본값과 병합
                    for section in default_config:
                        if section not in loaded_config:
                            loaded_config[section] = default_config[section]
                        else:
                            for key in default_config[section]:
                                if key not in loaded_config[section]:
                                    loaded_config[section][key] = default_config[section][key]
                    return loaded_config
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            
        return default_config
        
    def save_config(self):
        """설정 파일 저장"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            QMessageBox.warning(self, "설정 저장 실패", f"설정 저장 중 오류가 발생했습니다: {e}")
            
    def init_ui(self):
        """UI 초기화"""
        self.setWindowTitle("Socket Server Sensor Test - IT Log Device Manager")
        self.setGeometry(100, 100, 1200, 800)
        
        # 중앙 위젯 및 스플리터
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # 좌측 패널 (설정 및 제어)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        # 탭 위젯
        tab_widget = QTabWidget()
        left_layout.addWidget(tab_widget)
        
        # 서버 설정 탭
        server_tab = self.create_server_tab()
        tab_widget.addTab(server_tab, "서버 설정")
        
        # 센서 시뮬레이터 탭
        simulator_tab = self.create_simulator_tab()
        tab_widget.addTab(simulator_tab, "센서 시뮬레이터")
        
        # 클라이언트 관리 탭
        client_tab = self.create_client_tab()
        tab_widget.addTab(client_tab, "클라이언트 관리")
        
        # 우측 패널 (로그 및 데이터)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 상태 표시
        self.status_label = QLabel("서버 중지됨")
        self.status_label.setStyleSheet("QLabel { background-color: #ffcccc; padding: 5px; border: 1px solid #ccc; }")
        right_layout.addWidget(self.status_label)
        
        # 로그 영역
        log_group = QGroupBox("서버 로그")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setFont(QFont("Consolas", self.config["ui"]["font_size"]))
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        log_controls = QHBoxLayout()
        clear_log_btn = QPushButton("로그 지우기")
        clear_log_btn.clicked.connect(self.clear_log)
        save_log_btn = QPushButton("로그 저장")
        save_log_btn.clicked.connect(self.save_log)
        log_controls.addWidget(clear_log_btn)
        log_controls.addWidget(save_log_btn)
        log_controls.addStretch()
        log_layout.addLayout(log_controls)
        
        right_layout.addWidget(log_group)
        
        # 스플리터 설정
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 800])
        
        # 타이머 설정
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.update_connection_status)
        self.connection_timer.start(1000)
        
    def create_server_tab(self):
        """서버 설정 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 서버 기본 설정
        server_group = QGroupBox("서버 설정")
        server_layout = QFormLayout(server_group)
        
        self.host_edit = QLineEdit(self.config["server"]["host"])
        server_layout.addRow("Host:", self.host_edit)
        
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(self.config["server"]["port"])
        server_layout.addRow("Port:", self.port_spin)
        
        self.max_connections_spin = QSpinBox()
        self.max_connections_spin.setRange(1, 100)
        self.max_connections_spin.setValue(self.config["server"]["max_connections"])
        server_layout.addRow("최대 연결수:", self.max_connections_spin)
        
        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(5, 300)
        self.timeout_spin.setValue(self.config["server"]["timeout"])
        server_layout.addRow("타임아웃(초):", self.timeout_spin)
        
        self.keepalive_check = QCheckBox()
        self.keepalive_check.setChecked(self.config["server"]["keepalive"])
        server_layout.addRow("Keep-Alive:", self.keepalive_check)
        
        layout.addWidget(server_group)
        
        # 서버 제어
        control_group = QGroupBox("서버 제어")
        control_layout = QVBoxLayout(control_group)
        
        self.start_server_btn = QPushButton("서버 시작")
        self.start_server_btn.clicked.connect(self.start_server)
        self.stop_server_btn = QPushButton("서버 중지")
        self.stop_server_btn.clicked.connect(self.stop_server)
        self.stop_server_btn.setEnabled(False)
        
        control_layout.addWidget(self.start_server_btn)
        control_layout.addWidget(self.stop_server_btn)
        
        layout.addWidget(control_group)
        layout.addStretch()
        
        return tab
        
    def create_simulator_tab(self):
        """센서 시뮬레이터 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 시뮬레이터 설정
        sim_group = QGroupBox("시뮬레이터 설정")
        sim_layout = QFormLayout(sim_group)
        
        self.sensor_combo = QComboBox()
        sensor_types = ["PM", "SOUND", "VIBRO", "TILT", "CRACK", "WIND", "O2", "MQ", "NOX", "GASM"]
        self.sensor_combo.addItems(sensor_types)
        self.sensor_combo.setCurrentText(self.config["simulator"]["sensor_type"])
        sim_layout.addRow("센서 타입:", self.sensor_combo)
        
        self.device_id_edit = QLineEdit(self.config["simulator"]["device_id"])
        sim_layout.addRow("디바이스 ID:", self.device_id_edit)
        
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(1, 60)
        self.interval_spin.setValue(int(self.config["simulator"]["interval"]))
        sim_layout.addRow("전송 간격(초):", self.interval_spin)
        
        self.auto_start_check = QCheckBox()
        self.auto_start_check.setChecked(self.config["simulator"]["auto_start"])
        sim_layout.addRow("서버 시작시 자동 시작:", self.auto_start_check)
        
        layout.addWidget(sim_group)
        
        # 시뮬레이터 제어
        sim_control_group = QGroupBox("시뮬레이터 제어")
        sim_control_layout = QVBoxLayout(sim_control_group)
        
        self.start_sim_btn = QPushButton("시뮬레이터 시작")
        self.start_sim_btn.clicked.connect(self.start_simulator)
        self.stop_sim_btn = QPushButton("시뮬레이터 중지")
        self.stop_sim_btn.clicked.connect(self.stop_simulator)
        self.stop_sim_btn.setEnabled(False)
        
        sim_control_layout.addWidget(self.start_sim_btn)
        sim_control_layout.addWidget(self.stop_sim_btn)
        
        layout.addWidget(sim_control_group)
        
        # 수동 데이터 전송
        manual_group = QGroupBox("수동 데이터 전송")
        manual_layout = QVBoxLayout(manual_group)
        
        self.manual_data_edit = QTextEdit()
        self.manual_data_edit.setMaximumHeight(100)
        self.manual_data_edit.setPlaceholderText("전송할 데이터를 입력하세요...")
        manual_layout.addWidget(self.manual_data_edit)
        
        self.send_manual_btn = QPushButton("데이터 전송")
        self.send_manual_btn.clicked.connect(self.send_manual_data)
        manual_layout.addWidget(self.send_manual_btn)
        
        layout.addWidget(manual_group)
        layout.addStretch()
        
        return tab
        
    def create_client_tab(self):
        """클라이언트 관리 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # 연결된 클라이언트 목록
        client_group = QGroupBox("연결된 클라이언트")
        client_layout = QVBoxLayout(client_group)
        
        self.client_table = QTableWidget()
        self.client_table.setColumnCount(4)
        self.client_table.setHorizontalHeaderLabels(["IP 주소", "포트", "연결 시간", "상태"])
        self.client_table.horizontalHeader().setStretchLastSection(True)
        client_layout.addWidget(self.client_table)
        
        # 클라이언트 제어
        client_control = QHBoxLayout()
        self.disconnect_client_btn = QPushButton("선택된 클라이언트 연결 해제")
        self.disconnect_client_btn.clicked.connect(self.disconnect_selected_client)
        self.disconnect_all_btn = QPushButton("모든 클라이언트 연결 해제")
        self.disconnect_all_btn.clicked.connect(self.disconnect_all_clients)
        
        client_control.addWidget(self.disconnect_client_btn)
        client_control.addWidget(self.disconnect_all_btn)
        client_layout.addLayout(client_control)
        
        layout.addWidget(client_group)
        layout.addStretch()
        
        return tab
        
    def load_settings(self):
        """설정 로드 및 UI 반영"""
        pass
        
    def start_server(self):
        """서버 시작"""
        try:
            host = self.host_edit.text().strip()
            port = self.port_spin.value()
            
            if not host:
                QMessageBox.warning(self, "입력 오류", "Host를 입력해주세요.")
                return
                
            self.server_thread = SocketServerThread(host, port)
            self.server_thread.client_connected.connect(self.on_client_connected)
            self.server_thread.client_disconnected.connect(self.on_client_disconnected)
            self.server_thread.data_received.connect(self.on_data_received)
            self.server_thread.log_message.connect(self.log_message)
            self.server_thread.start()
            
            self.start_server_btn.setEnabled(False)
            self.stop_server_btn.setEnabled(True)
            self.update_status(f"서버 실행 중: {host}:{port}", "#ccffcc")
            
            # 설정 업데이트
            self.config["server"]["host"] = host
            self.config["server"]["port"] = port
            self.save_config()
            
            # 자동 시뮬레이터 시작
            if self.auto_start_check.isChecked():
                self.start_simulator()
                
        except Exception as e:
            QMessageBox.critical(self, "서버 시작 실패", f"서버 시작 중 오류가 발생했습니다: {e}")
            
    def stop_server(self):
        """서버 중지"""
        if self.server_thread:
            self.server_thread.stop_server()
            self.server_thread.wait()
            self.server_thread = None
            
        if self.simulator_thread:
            self.stop_simulator()
            
        self.start_server_btn.setEnabled(True)
        self.stop_server_btn.setEnabled(False)
        self.update_status("서버 중지됨", "#ffcccc")
        self.client_table.setRowCount(0)
        
    def start_simulator(self):
        """시뮬레이터 시작"""
        if not self.server_thread or not self.server_thread.running:
            QMessageBox.warning(self, "시뮬레이터 오류", "서버가 실행 중이어야 합니다.")
            return
            
        sensor_type = self.sensor_combo.currentText()
        device_id = self.device_id_edit.text().strip()
        interval = self.interval_spin.value()
        
        if not device_id:
            QMessageBox.warning(self, "입력 오류", "디바이스 ID를 입력해주세요.")
            return
            
        self.simulator_thread = SensorDataSimulator()
        self.simulator_thread.set_config(sensor_type, device_id, interval)
        self.simulator_thread.send_data.connect(self.broadcast_sensor_data)
        self.simulator_thread.start()
        
        self.start_sim_btn.setEnabled(False)
        self.stop_sim_btn.setEnabled(True)
        
        self.log_message(f"시뮬레이터 시작됨: {sensor_type}, ID={device_id}, 간격={interval}초")
        
    def stop_simulator(self):
        """시뮬레이터 중지"""
        if self.simulator_thread:
            self.simulator_thread.stop()
            self.simulator_thread.wait()
            self.simulator_thread = None
            
        self.start_sim_btn.setEnabled(True)
        self.stop_sim_btn.setEnabled(False)
        
        self.log_message("시뮬레이터 중지됨")
        
    def send_manual_data(self):
        """수동 데이터 전송"""
        if not self.server_thread or not self.server_thread.running:
            QMessageBox.warning(self, "전송 실패", "서버가 실행 중이어야 합니다.")
            return
            
        data = self.manual_data_edit.toPlainText().strip()
        if not data:
            QMessageBox.warning(self, "전송 실패", "전송할 데이터를 입력해주세요.")
            return
            
        self.broadcast_sensor_data(data)
        
    def broadcast_sensor_data(self, data):
        """센서 데이터 브로드캐스트"""
        if self.server_thread:
            # 클라이언트가 연결되어 있을 때만 브로드캐스트
            if self.server_thread.broadcast_to_all(data):
                self.log_message(f"브로드캐스트: {data}")
            else:
                self.log_message(f"브로드캐스트 건너뛰기: 연결된 클라이언트 없음")
            
    def on_client_connected(self, addr, port):
        """클라이언트 연결 처리"""
        row_count = self.client_table.rowCount()
        self.client_table.setRowCount(row_count + 1)
        
        self.client_table.setItem(row_count, 0, QTableWidgetItem(addr))
        self.client_table.setItem(row_count, 1, QTableWidgetItem(str(port)))
        self.client_table.setItem(row_count, 2, QTableWidgetItem(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.client_table.setItem(row_count, 3, QTableWidgetItem("연결됨"))
        
        self.log_message(f"클라이언트 연결됨: {addr}:{port}")
        
    def on_client_disconnected(self, addr, port):
        """클라이언트 연결 해제 처리"""
        for row in range(self.client_table.rowCount()):
            if (self.client_table.item(row, 0).text() == addr and 
                self.client_table.item(row, 1).text() == str(port)):
                self.client_table.removeRow(row)
                break
                
        self.log_message(f"클라이언트 연결 해제됨: {addr}:{port}")
        
    def on_data_received(self, client_addr, data, timestamp):
        """데이터 수신 처리"""
        self.log_message(f"[{client_addr}] {timestamp}: {data}")
        
    def disconnect_selected_client(self):
        """선택된 클라이언트 연결 해제"""
        current_row = self.client_table.currentRow()
        if current_row >= 0:
            addr = self.client_table.item(current_row, 0).text()
            port = int(self.client_table.item(current_row, 1).text())
            # 클라이언트 연결 해제 로직 구현
            self.log_message(f"클라이언트 {addr}:{port} 연결 해제 요청")
            
    def disconnect_all_clients(self):
        """모든 클라이언트 연결 해제"""
        if self.server_thread:
            # 모든 클라이언트 연결 해제 로직 구현
            self.log_message("모든 클라이언트 연결 해제 요청")
            
    def update_connection_status(self):
        """연결 상태 업데이트"""
        if self.server_thread and self.server_thread.running:
            client_count = len(self.server_thread.clients)
            self.update_status(f"서버 실행 중 - 클라이언트: {client_count}개", "#ccffcc")
            
    def update_status(self, message, color):
        """상태 업데이트"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet(f"QLabel {{ background-color: {color}; padding: 5px; border: 1px solid #ccc; }}")
        
    def log_message(self, message):
        """로그 메시지 추가"""
        if self.config["logging"]["timestamp"]:
            timestamp = datetime.now().strftime("%H:%M:%S")
            formatted_message = f"[{timestamp}] {message}"
        else:
            formatted_message = message
            
        self.log_text.append(formatted_message)
        
        # 최대 줄수 제한
        if self.config["logging"]["max_lines"] > 0:
            lines = self.log_text.toPlainText().split('\n')
            if len(lines) > self.config["logging"]["max_lines"]:
                self.log_text.setPlainText('\n'.join(lines[-self.config["logging"]["max_lines"]:]))
                
        # 자동 스크롤
        if self.config["ui"]["auto_scroll"]:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_text.setTextCursor(cursor)
            
    def clear_log(self):
        """로그 지우기"""
        self.log_text.clear()
        
    def save_log(self):
        """로그 저장"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"server_log_{timestamp}.txt"
            
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(self.log_text.toPlainText())
                
            QMessageBox.information(self, "로그 저장", f"로그가 '{filename}'에 저장되었습니다.")
        except Exception as e:
            QMessageBox.warning(self, "로그 저장 실패", f"로그 저장 중 오류가 발생했습니다: {e}")
            
    def closeEvent(self, event):
        """애플리케이션 종료 처리"""
        if self.server_thread:
            self.stop_server()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # 깔끔한 UI 스타일
    
    # 한글 폰트 설정
    font = QFont("맑은 고딕", 9)
    app.setFont(font)
    
    window = SocketServerTestApp()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()