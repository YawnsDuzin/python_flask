#!/usr/bin/env python3
"""
설치된 라이브러리 버전 확인 스크립트
"""

import pkg_resources
import sys

def check_package_versions():
    """설치된 패키지들의 버전을 확인합니다."""
    
    # requirements.txt에 명시된 주요 패키지들
    required_packages = [
        'flask',
        'python-dotenv',
        'psutil',
        'PyQt5',
        'pyinstaller', 
        'bcrypt'
    ]
    
    print("=== 설치된 라이브러리 버전 확인 ===\n")
    print(f"Python 버전: {sys.version}\n")
    
    for package in required_packages:
        try:
            version = pkg_resources.get_distribution(package).version
            print(f"✓ {package}: {version}")
        except pkg_resources.DistributionNotFound:
            print(f"✗ {package}: 설치되지 않음")
    
    print("\n=== 모든 설치된 패키지 ===")
    installed_packages = [d for d in pkg_resources.working_set]
    installed_packages.sort(key=lambda x: x.project_name.lower())
    
    for package in installed_packages:
        print(f"{package.project_name}: {package.version}")

if __name__ == "__main__":
    check_package_versions()