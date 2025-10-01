"""
블루프린트 모듈 초기화
각 기능별 블루프린트를 등록합니다.
"""

from flask import Flask

def register_blueprints(app: Flask):
    """모든 블루프린트를 Flask 앱에 등록"""
    
    # 인증 관련
    from .auth import auth_bp
    app.register_blueprint(auth_bp)
    
    # 디바이스 관리
    from .device import device_bp
    app.register_blueprint(device_bp)
    
    # CLIENT 관리
    from .client import client_bp
    app.register_blueprint(client_bp)
    
    # 센서 관련
    from .sensor import sensor_bp
    app.register_blueprint(sensor_bp)
    
    # 센서 대시보드 API
    from .sensor_dashboard import sensor_dashboard_bp
    app.register_blueprint(sensor_dashboard_bp)
    
    # 시스템 관리
    from .system import system_bp
    app.register_blueprint(system_bp)
    
    # 관리자 기능 - 분리된 블루프린트
    from .user_admin import user_admin_bp
    from .config_admin import config_admin_bp
    app.register_blueprint(user_admin_bp)
    app.register_blueprint(config_admin_bp)
    
    # 기존 admin 블루프린트 (호환성 유지를 위해 주석 처리)
    # from .admin import admin_bp
    # app.register_blueprint(admin_bp)
    
    # API 엔드포인트
    from .api import api_bp
    app.register_blueprint(api_bp)