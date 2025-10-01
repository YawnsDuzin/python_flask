#!/usr/bin/env python
"""
dhcpcd.conf 파싱 테스트 스크립트
"""

import re

# 실제 dhcpcd.conf 내용 시뮬레이션
test_content = """
# 고정 IP 설정 (IT Log Device Manager에서 설정됨)
interface eth0
static ip_address=192.168.0.180
static routers=192.168.0.1
static domain_name_servers=168.126.63.1 168.126.63.2
"""

def parse_dhcpcd_original(content):
    """원래 방식"""
    config = {}
    
    # 원래 패턴
    eth_section = re.search(r'interface eth0.*?(?=\ninterface|\n[a-zA-Z#]|\Z)', content, re.DOTALL)
    if eth_section:
        section_text = eth_section.group(0)
        print("[원래 방식] Found section:")
        print(repr(section_text))
        print("-" * 50)
        
        ip_match = re.search(r'static ip_address=(.+)', section_text)
        if ip_match:
            config['static_ip'] = ip_match.group(1).strip()
            
        router_match = re.search(r'static routers=(.+)', section_text)
        if router_match:
            config['gateway'] = router_match.group(1).strip()
            
        dns_match = re.search(r'static domain_name_servers=(.+)', section_text)
        if dns_match:
            dns_servers = dns_match.group(1).strip().split()
            config['dns1'] = dns_servers[0] if dns_servers else ''
            config['dns2'] = dns_servers[1] if len(dns_servers) > 1 else ''
    else:
        print("[원래 방식] No eth0 section found")
        
    return config

def parse_dhcpcd_improved(content):
    """개선된 방식"""
    config = {}
    
    # 개선된 패턴
    eth_section = re.search(r'interface\s+eth0\b.*?(?=\ninterface\s+|\Z)', content, re.DOTALL | re.MULTILINE)
    if eth_section:
        section_text = eth_section.group(0)
        print("[개선된 방식] Found section:")
        print(repr(section_text))
        print("-" * 50)
        
        # '=' 주변 공백 허용
        ip_match = re.search(r'static\s+ip_address\s*=\s*(.+)', section_text)
        if ip_match:
            ip_addr = ip_match.group(1).strip().split('/')[0]
            config['static_ip'] = ip_addr
            
        router_match = re.search(r'static\s+routers\s*=\s*(.+)', section_text)
        if router_match:
            config['gateway'] = router_match.group(1).strip()
            
        dns_match = re.search(r'static\s+domain_name_servers\s*=\s*(.+)', section_text)
        if dns_match:
            dns_servers = dns_match.group(1).strip().split()
            config['dns1'] = dns_servers[0] if dns_servers else ''
            config['dns2'] = dns_servers[1] if len(dns_servers) > 1 else ''
    else:
        print("[개선된 방식] No eth0 section found")
        
    return config

def parse_dhcpcd_simple(content):
    """더 간단한 방식 - 전체 파일에서 직접 찾기"""
    config = {}
    
    # 전체 내용에서 직접 찾기
    lines = content.split('\n')
    in_eth0_section = False
    
    for line in lines:
        line = line.strip()
        
        # eth0 섹션 시작
        if line.startswith('interface eth0'):
            in_eth0_section = True
            print(f"[간단한 방식] Found interface eth0")
            continue
            
        # 다른 인터페이스 섹션 시작되면 eth0 섹션 종료
        if in_eth0_section and line.startswith('interface ') and 'eth0' not in line:
            in_eth0_section = False
            continue
            
        # eth0 섹션 내에서만 처리
        if in_eth0_section:
            if line.startswith('static ip_address'):
                ip_value = line.split('=', 1)[1].strip()
                config['static_ip'] = ip_value.split('/')[0]
                print(f"[간단한 방식] Found IP: {config['static_ip']}")
                
            elif line.startswith('static routers'):
                config['gateway'] = line.split('=', 1)[1].strip()
                print(f"[간단한 방식] Found gateway: {config['gateway']}")
                
            elif line.startswith('static domain_name_servers'):
                dns_servers = line.split('=', 1)[1].strip().split()
                config['dns1'] = dns_servers[0] if dns_servers else ''
                config['dns2'] = dns_servers[1] if len(dns_servers) > 1 else ''
                print(f"[간단한 방식] Found DNS: {config.get('dns1')}, {config.get('dns2')}")
    
    return config

if __name__ == "__main__":
    print("=" * 70)
    print("dhcpcd.conf 파싱 테스트")
    print("=" * 70)
    print("\n테스트 내용:")
    print(test_content)
    print("=" * 70)
    
    print("\n1. 원래 방식 테스트:")
    print("-" * 50)
    config1 = parse_dhcpcd_original(test_content)
    print(f"결과: {config1}")
    
    print("\n2. 개선된 방식 테스트:")
    print("-" * 50)
    config2 = parse_dhcpcd_improved(test_content)
    print(f"결과: {config2}")
    
    print("\n3. 간단한 방식 테스트:")
    print("-" * 50)
    config3 = parse_dhcpcd_simple(test_content)
    print(f"결과: {config3}")
    
    print("\n" + "=" * 70)
    print("결과 비교:")
    print(f"원래 방식:   {config1}")
    print(f"개선된 방식: {config2}")
    print(f"간단한 방식: {config3}")