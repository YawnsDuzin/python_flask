 Windows 설치 방법

  1. 공식 사이트에서 다운로드

  https://www.python.org/downloads/
  - "Download Python 3.10.x" 클릭
  - Windows installer (64-bit) 다운로드

  2. 설치 과정

  1. 설치 파일 실행
  2. ✅ "Add Python to PATH" 체크 (중요!)
  3. "Install Now" 클릭
  4. 설치 완료 후 "Disable path length limit" 클릭 (권장)

  3. 설치 확인

  python --version
  pip --version

  4. 프로젝트 의존성 설치

  cd C:\_dzP\Project\_Etc\통합센서 웹앱 개발\Source\device_manager\device_manager
  pip install -r requirements.txt

  5. 애플리케이션 실행

  python app.py

  브라우저에서 http://localhost:5000 접속하면 됩니다.



  추가 권장사항
  - 가상환경 사용 (선택사항):
  python -m venv venv_webapp
  venv_webapp\Scripts\activate
  pip install -r requirements.txt
