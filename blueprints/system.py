"""
시스템 관리 블루프린트
라즈베리파이 시스템 설정, 네트워크 설정, 재부팅 기능을 담당합니다.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from user_manager import login_required, operator_required
import subprocess
import re
import sys
import os

# 상위 디렉토리의 모듈을 import하기 위한 경로 설정
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

system_bp = Blueprint('system', __name__)

def read_network_config():
    """현재 네트워크 설정 읽기"""
    try:
        # dhcpcd.conf 파일 읽기
        with open('/etc/dhcpcd.conf', 'r') as f:
            content = f.read()
        
        config = {}
        
        # 현재 IP 주소 정보 가져오기
        try:
            result = subprocess.run(['hostname', '-I'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                current_ips = result.stdout.strip().split()
                if current_ips:
                    config['current_ip'] = current_ips[0]
        except:
            config['current_ip'] = 'Unknown'
        
        # dhcpcd.conf에서 고정 IP 설정 찾기
        # 라인별로 파싱하는 더 안정적인 방식 사용
        lines = content.split('\n')
        in_eth0_section = False
        
        for line in lines:
            line_stripped = line.strip()
            
            # eth0 섹션 시작
            if line_stripped.startswith('interface eth0'):
                in_eth0_section = True
                continue
                
            # 다른 인터페이스 섹션이 시작되면 eth0 섹션 종료
            if in_eth0_section and line_stripped.startswith('interface ') and 'eth0' not in line_stripped:
                in_eth0_section = False
                break
                
            # eth0 섹션 내에서 설정 찾기
            if in_eth0_section:
                if line_stripped.startswith('static ip_address'):
                    # '=' 기준으로 분리하고 /24 같은 서브넷 마스크 제거
                    try:
                        ip_value = line_stripped.split('=', 1)[1].strip()
                        config['static_ip'] = ip_value.split('/')[0]
                    except IndexError:
                        pass
                        
                elif line_stripped.startswith('static routers'):
                    try:
                        config['gateway'] = line_stripped.split('=', 1)[1].strip()
                    except IndexError:
                        pass
                        
                elif line_stripped.startswith('static domain_name_servers'):
                    try:
                        dns_servers = line_stripped.split('=', 1)[1].strip().split()
                        config['dns1'] = dns_servers[0] if dns_servers else ''
                        config['dns2'] = dns_servers[1] if len(dns_servers) > 1 else ''
                    except IndexError:
                        pass
        
        # hostname 가져오기
        try:
            with open('/etc/hostname', 'r') as f:
                config['hostname'] = f.read().strip()
        except:
            config['hostname'] = 'Unknown'
        
        return config
        
    except Exception as e:
        print(f"Network config read error: {e}")
        return {}


@system_bp.route('/raspi/settings')
@login_required  # 조회는 모든 사용자 가능
def raspi_settings():
    """라즈베리파이 설정 페이지"""
    try:
        network_config = read_network_config()
        return render_template('raspi_settings.html', config=network_config)
    except Exception as e:
        flash(f'설정 정보를 불러오는 중 오류가 발생했습니다: {e}', 'error')
        return render_template('raspi_settings.html', config=None)


@system_bp.route('/raspi/set-static-ip', methods=['POST'])
@operator_required  # 네트워크 설정은 operator 이상
def set_static_ip():
    """고정 IP 설정"""
    try:
        ip_address = request.form.get('ip_address', '').strip()
        gateway = request.form.get('gateway', '').strip()
        dns_server1 = request.form.get('dns_server1', '168.126.63.1').strip()
        dns_server2 = request.form.get('dns_server2', '168.126.63.2').strip()
        
        # 입력값 검증
        if not ip_address or not gateway:
            flash('IP 주소와 게이트웨이는 필수 입력 항목입니다.', 'error')
            return redirect(url_for('system.raspi_settings'))
        
        # IP 주소 형식 검증 (간단한 검증)
        ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}(/\d{1,2})?$'
        if not re.match(ip_pattern, ip_address):
            flash('올바른 IP 주소 형식이 아닙니다. (예: 192.168.1.100/24)', 'error')
            return redirect(url_for('system.raspi_settings'))
        
        # DNS 서버 설정 구성
        dns_servers = dns_server1
        if dns_server2:
            dns_servers += f' {dns_server2}'
        
        # dhcpcd.conf 백업 및 수정
        try:
            # 기존 파일 백업
            subprocess.run(['sudo', 'cp', '/etc/dhcpcd.conf', '/etc/dhcpcd.conf.backup'], 
                         check=True, timeout=10)
            
            # 기존 설정 파일 읽기
            with open('/etc/dhcpcd.conf', 'r') as f:
                existing_content = f.read()
            
            # 기존 고정 IP 설정이 있는지 확인하고 제거
            # interface eth0 블록 찾기 및 제거
            pattern = r'# 고정 IP 설정.*?(?=\n(?:[a-zA-Z#]|\Z))'
            cleaned_content = re.sub(pattern, '', existing_content, flags=re.DOTALL)
            
            # interface eth0/wlan0로 시작하는 기존 static 설정 블록들도 제거
            eth_pattern = r'interface eth0\s*\nstatic.*?(?=\n(?:interface|\n[a-zA-Z#]|\Z))'
            wlan_pattern = r'interface wlan0\s*\nstatic.*?(?=\n(?:interface|\n[a-zA-Z#]|\Z))'
            
            cleaned_content = re.sub(eth_pattern, '', cleaned_content, flags=re.DOTALL)
            cleaned_content = re.sub(wlan_pattern, '', cleaned_content, flags=re.DOTALL)
            
            # 새로운 설정 작성
            config_content = f"""
# 고정 IP 설정 (IT Log Device Manager에서 설정됨)
interface eth0
static ip_address={ip_address}
static routers={gateway}
static domain_name_servers={dns_servers}
"""
            
            # 최종 설정 파일 내용 구성
            final_content = cleaned_content.rstrip() + '\n' + config_content
            
            # 임시 파일에 저장 후 sudo로 복사
            temp_file = '/tmp/dhcpcd.conf.tmp'
            with open(temp_file, 'w') as f:
                f.write(final_content)
            
            subprocess.run(['sudo', 'cp', temp_file, '/etc/dhcpcd.conf'], 
                         check=True, timeout=10)
            subprocess.run(['rm', temp_file], timeout=5)
            
            flash('고정 IP 설정이 완료되었습니다. 재부팅 후 적용됩니다.', 'success')
            
        except subprocess.CalledProcessError as e:
            flash(f'네트워크 설정 중 오류가 발생했습니다: {e}', 'error')
        except Exception as e:
            flash(f'설정 파일 작성 중 오류가 발생했습니다: {e}', 'error')
            
    except Exception as e:
        flash(f'고정 IP 설정 중 오류가 발생했습니다: {e}', 'error')
    
    return redirect(url_for('system.raspi_settings'))


@system_bp.route('/raspi/set-hostname', methods=['POST'])
@operator_required  # 호스트명 변경은 operator 이상
def set_hostname():
    """hostname 설정"""
    try:
        new_hostname = request.form.get('hostname', '').strip()
        
        # 입력값 검증
        if not new_hostname:
            flash('호스트명을 입력해주세요.', 'error')
            return redirect(url_for('system.raspi_settings'))
        
        # 호스트명 형식 검증 (영문자, 숫자, 하이픈만 허용)
        if not re.match(r'^[a-zA-Z0-9-]+$', new_hostname):
            flash('호스트명은 영문자, 숫자, 하이픈만 사용할 수 있습니다.', 'error')
            return redirect(url_for('system.raspi_settings'))
        
        if len(new_hostname) > 63:
            flash('호스트명은 63자를 초과할 수 없습니다.', 'error')
            return redirect(url_for('system.raspi_settings'))
        
        try:
            # /etc/hostname 수정
            temp_file = '/tmp/hostname.tmp'
            with open(temp_file, 'w') as f:
                f.write(new_hostname + '\n')
            
            subprocess.run(['sudo', 'cp', temp_file, '/etc/hostname'], 
                         check=True, timeout=10)
            subprocess.run(['rm', temp_file], timeout=5)
            
            # /etc/hosts 수정
            try:
                with open('/etc/hosts', 'r') as f:
                    hosts_content = f.read()
                
                # 기존 127.0.1.1 라인 수정
                hosts_lines = hosts_content.split('\n')
                updated_lines = []
                found_local = False
                
                for line in hosts_lines:
                    if line.startswith('127.0.1.1'):
                        updated_lines.append(f'127.0.1.1\t{new_hostname}')
                        found_local = True
                    else:
                        updated_lines.append(line)
                
                # 127.0.1.1 라인이 없으면 추가
                if not found_local:
                    # 127.0.0.1 다음에 추가
                    for i, line in enumerate(updated_lines):
                        if line.startswith('127.0.0.1'):
                            updated_lines.insert(i + 1, f'127.0.1.1\t{new_hostname}')
                            break
                
                # 임시 파일로 저장 후 복사
                temp_hosts = '/tmp/hosts.tmp'
                with open(temp_hosts, 'w') as f:
                    f.write('\n'.join(updated_lines))
                
                subprocess.run(['sudo', 'cp', temp_hosts, '/etc/hosts'], 
                             check=True, timeout=10)
                subprocess.run(['rm', temp_hosts], timeout=5)
                
            except Exception as hosts_error:
                print(f"hosts 파일 수정 중 오류: {hosts_error}")
                flash('호스트명 설정은 완료되었으나, hosts 파일 수정 중 문제가 발생했습니다.', 'warning')
            
            flash('호스트명이 성공적으로 변경되었습니다. 재부팅 후 적용됩니다.', 'success')
            
        except subprocess.CalledProcessError as e:
            flash(f'호스트명 설정 중 오류가 발생했습니다: {e}', 'error')
        except Exception as e:
            flash(f'호스트명 파일 작성 중 오류가 발생했습니다: {e}', 'error')
            
    except Exception as e:
        flash(f'호스트명 변경 중 오류가 발생했습니다: {e}', 'error')
    
    return redirect(url_for('system.raspi_settings'))


@system_bp.route('/raspi/reboot', methods=['POST'])
@operator_required  # 재부팅은 operator 이상 권한 필요
def raspi_reboot():
    """라즈베리파이 재부팅"""
    from app import config_manager
    
    try:
        # 데이터베이스에서 프로세스 설정 읽기
        process_config = config_manager.get_config('process')
        
        if process_config:
            process_name = process_config.get('totalsensor_process', 'itlog-ss2')
            
            # 센서 프로그램 종료
            try:
                subprocess.run(['sudo', 'pkill', '-f', process_name], 
                             check=False, timeout=10)
                print(f"센서 프로세스 종료 시도: {process_name}")
            except Exception as e:
                print(f"센서 프로세스 종료 중 오류 (무시): {e}")
        
        # 10초 후 재부팅 명령 실행 (백그라운드에서)
        # 2025.09.24 duzin
        # subprocess.run(['sudo', 'shutdown', '-r', '+1'], 
        #               check=False, timeout=5)
        subprocess.Popen(['bash', '-c', 'sleep 10 && sudo reboot'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)

        return jsonify({
            'success': True,
            'message': '10초 후 재부팅됩니다. 센서 프로그램도 안전하게 종료되었습니다.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False, 
            'message': f'재부팅 명령 실행 중 오류가 발생했습니다: {e}'
        })