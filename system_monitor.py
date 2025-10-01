#!/usr/bin/env python3
"""
시스템 모니터링 모듈
라즈베리파이의 SystemMonitorThread와 동일한 기능을 제공합니다.
"""

import psutil
import subprocess
import time
import socket
from datetime import datetime


class SystemMonitor:
    """시스템 상태 모니터링 클래스"""
    
    def __init__(self):
        self.last_disk_io = None
        self.last_net_io = None
        self.last_time = None
        # 캐싱을 위한 변수들
        self.cached_info = None
        self.cache_time = None
        self.cache_duration = 3  # 3초 캐시
    
    def get_cpu_temperature(self):
        """CPU 온도 가져오기 (최적화된 버전)
        
        Returns:
            float: 섭씨 온도
        """
        # 1차: 파일 직접 읽기 (가장 효율적)
        try:
            # Linux 시스템의 일반적인 온도 센서 경로들
            temp_paths = [
                '/sys/class/thermal/thermal_zone0/temp',
                '/sys/class/thermal/thermal_zone1/temp',
                '/sys/class/hwmon/hwmon0/temp1_input',
                '/sys/class/hwmon/hwmon1/temp1_input'
            ]
            
            for path in temp_paths:
                try:
                    with open(path, 'r') as f:
                        temp = int(f.read().strip()) / 1000.0
                        if 0 < temp < 150:  # 합리적인 온도 범위
                            return temp
                except:
                    continue
        except:
            pass
        
        # 2차: 라즈베리파이 전용 명령 (subprocess 사용)
        try:
            result = subprocess.run(
                ['vcgencmd', 'measure_temp'],
                capture_output=True,
                text=True,
                timeout=2  # 타임아웃 단축
            )
            
            # 출력 형식: "temp=42.8'C"
            if result.returncode == 0:
                temp_str = result.stdout.strip()
                temp = float(temp_str.split('=')[1].split("'")[0])
                if 0 < temp < 150:
                    return temp
        except Exception:
            pass
            
        return 0.0
    
    def get_disk_usage(self, path='/'):
        """디스크 사용량 정보
        
        Args:
            path (str): 확인할 경로 (기본: 루트)
            
        Returns:
            dict: 디스크 사용량 정보
        """
        try:
            usage = psutil.disk_usage(path)
            return {
                'total': usage.total,
                'used': usage.used,
                'free': usage.free,
                'percent': (usage.used / usage.total) * 100
            }
        except:
            return {'total': 0, 'used': 0, 'free': 0, 'percent': 0}
    
    def get_network_speed(self):
        """네트워크 속도 계산 (bps)
        
        Returns:
            dict: 업로드/다운로드 속도
        """
        try:
            current_net = psutil.net_io_counters()
            current_time = time.time()
            
            if self.last_net_io is None or self.last_time is None:
                self.last_net_io = current_net
                self.last_time = current_time
                return {'upload_speed': 0, 'download_speed': 0}
            
            time_delta = current_time - self.last_time
            if time_delta <= 0:
                return {'upload_speed': 0, 'download_speed': 0}
            
            upload_speed = (current_net.bytes_sent - self.last_net_io.bytes_sent) / time_delta
            download_speed = (current_net.bytes_recv - self.last_net_io.bytes_recv) / time_delta
            
            self.last_net_io = current_net
            self.last_time = current_time
            
            return {
                'upload_speed': max(0, upload_speed),
                'download_speed': max(0, download_speed)
            }
        except:
            return {'upload_speed': 0, 'download_speed': 0}
    
    def get_network_interfaces(self):
        """네트워크 인터페이스 정보 수집
        
        Returns:
            dict: 호스트명과 IP 주소 정보
        """
        try:
            # 호스트명 가져오기
            hostname = socket.gethostname()
            
            # IP 주소 정보 수집
            interfaces = []
            
            # 활성화된 네트워크 인터페이스 가져오기
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            for interface_name, addresses in net_if_addrs.items():
                # 인터페이스 상태 확인 (활성화된 것만)
                if interface_name in net_if_stats and net_if_stats[interface_name].isup:
                    for address in addresses:
                        # IPv4 주소만 추가
                        if address.family == socket.AF_INET:
                            # 로컬호스트 주소 제외
                            if address.address != '127.0.0.1':
                                interfaces.append({
                                    'name': interface_name,
                                    'ip': address.address,
                                    'netmask': address.netmask
                                })
            
            # Primary IP 주소 찾기 (외부 연결 가능한 주소)
            primary_ip = None
            try:
                # 외부 서버에 연결하여 로컬 IP 확인
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    primary_ip = s.getsockname()[0]
            except:
                # 실패시 첫 번째 non-loopback 주소 사용
                if interfaces:
                    primary_ip = interfaces[0]['ip']
            
            return {
                'hostname': hostname,
                'primary_ip': primary_ip or 'Unknown',
                'interfaces': interfaces
            }
        except Exception as e:
            return {
                'hostname': 'Unknown',
                'primary_ip': 'Unknown',
                'interfaces': [],
                'error': str(e)
            }
    
    def get_system_info(self, use_cache=True):
        """전체 시스템 정보 수집 (캐싱 지원)
        
        Args:
            use_cache (bool): 캐시 사용 여부
            
        Returns:
            dict: 시스템 상태 정보
        """
        # 캐시 확인
        if use_cache and self.cached_info and self.cache_time:
            if time.time() - self.cache_time < self.cache_duration:
                return self.cached_info
        
        try:
            # CPU 사용률 (블로킹 시간 단축)
            cpu_percent = psutil.cpu_percent(interval=None)  # 즉시 반환 (이전 값 기반)
            
            # 메모리 정보
            memory = psutil.virtual_memory()
            
            # CPU 온도
            cpu_temp = self.get_cpu_temperature()
            
            # 디스크 I/O
            disk_io = psutil.disk_io_counters()
            
            # 네트워크 I/O
            net_io = psutil.net_io_counters()
            
            # 디스크 사용량
            disk_usage = self.get_disk_usage()
            
            # 네트워크 속도
            net_speed = self.get_network_speed()
            
            # 네트워크 인터페이스 정보
            network_interfaces = self.get_network_interfaces()
            
            # 시스템 정보
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            # 결과 생성
            result = {
                'timestamp': datetime.now().isoformat(),
                'cpu': {
                    'usage_percent': round(cpu_percent, 1),
                    'temperature': round(cpu_temp, 1),
                    'count': psutil.cpu_count()
                },
                'memory': {
                    'total': memory.total,
                    'used': memory.used,
                    'free': memory.free,
                    'percent': round(memory.percent, 1),
                    'available': memory.available
                },
                'disk': {
                    'usage': disk_usage,
                    'io': {
                        'read_bytes': disk_io.read_bytes if disk_io else 0,
                        'write_bytes': disk_io.write_bytes if disk_io else 0,
                        'read_count': disk_io.read_count if disk_io else 0,
                        'write_count': disk_io.write_count if disk_io else 0
                    }
                },
                'network': {
                    'io': {
                        'bytes_sent': net_io.bytes_sent if net_io else 0,
                        'bytes_recv': net_io.bytes_recv if net_io else 0,
                        'packets_sent': net_io.packets_sent if net_io else 0,
                        'packets_recv': net_io.packets_recv if net_io else 0
                    },
                    'speed': net_speed,
                    'interfaces': network_interfaces
                },
                'system': {
                    'boot_time': boot_time.isoformat(),
                    'uptime_seconds': int(uptime.total_seconds()),
                    'uptime_string': str(uptime).split('.')[0]  # 소수점 제거
                }
            }
            
            # 캐시 업데이트
            if use_cache:
                self.cached_info = result
                self.cache_time = time.time()
            
            return result
        except Exception as e:
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e),
                'cpu': {'usage_percent': 0, 'temperature': 0, 'count': 0},
                'memory': {'total': 0, 'used': 0, 'free': 0, 'percent': 0, 'available': 0},
                'disk': {'usage': {'total': 0, 'used': 0, 'free': 0, 'percent': 0}, 'io': {}},
                'network': {'io': {}, 'speed': {'upload_speed': 0, 'download_speed': 0}},
                'system': {'boot_time': '', 'uptime_seconds': 0, 'uptime_string': ''}
            }

    def format_bytes(self, bytes_value):
        """바이트를 읽기 쉬운 형태로 변환
        
        Args:
            bytes_value (int): 바이트 값
            
        Returns:
            str: 변환된 문자열 (예: "1.2 GB")
        """
        if bytes_value == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        i = 0
        while bytes_value >= 1024 and i < len(units) - 1:
            bytes_value /= 1024
            i += 1
        
        return f"{bytes_value:.1f} {units[i]}"


# 전역 시스템 모니터 인스턴스
system_monitor = SystemMonitor()


def get_system_status():
    """시스템 상태 정보 반환 (Flask 앱에서 사용)
    
    Returns:
        dict: 시스템 상태 정보
    """
    return system_monitor.get_system_info()


if __name__ == "__main__":
    # 테스트용 코드
    import json
    
    monitor = SystemMonitor()
    info = monitor.get_system_info()
    
    print("시스템 정보:")
    print(json.dumps(info, indent=2, ensure_ascii=False))