# GitHub 저장소 생성 및 첫 커밋/푸시 완벽 가이드

## 📚 목차
1. [GitHub 계정 및 저장소 생성](#1-github-계정-및-저장소-생성)
2. [Git 설치 및 초기 설정](#2-git-설치-및-초기-설정)
3. [SSH 키 설정 (권장)](#3-ssh-키-설정-권장)
4. [Personal Access Token 설정 (대안)](#4-personal-access-token-설정-대안)
5. [첫 커밋과 푸시](#5-첫-커밋과-푸시)
6. [Git 초보자 필수 지식](#6-git-초보자-필수-지식)
7. [자주 발생하는 문제와 해결법](#7-자주-발생하는-문제와-해결법)

---

## 1. GitHub 계정 및 저장소 생성

### 1.1 GitHub 계정 생성
1. [GitHub.com](https://github.com) 접속
2. "Sign up" 클릭
3. 이메일, 패스워드, 사용자명 입력
4. 이메일 인증 완료

### 1.2 새 저장소(Repository) 생성
1. GitHub 로그인 후 우측 상단 "+" 버튼 클릭
2. "New repository" 선택
3. 저장소 설정:
   ```
   Repository name: itlog-device-manager
   Description: Industrial IoT sensor monitoring platform
   Public/Private: 선택 (Private 권장)
   Initialize with README: 체크 해제 (로컬에서 생성할 예정)
   .gitignore: None
   License: 필요시 선택
   ```
4. "Create repository" 클릭

## 2. Git 설치 및 초기 설정

### 2.1 Git 설치
- **Windows**: [Git for Windows](https://git-scm.com/download/windows) 다운로드 및 설치
- **Mac**: Terminal에서 `brew install git` 실행
- **Linux**: `sudo apt-get install git` (Ubuntu/Debian)

### 2.2 Git 전역 설정
터미널/명령 프롬프트에서 실행:
```bash
# 사용자 이름 설정 (GitHub 사용자명과 동일하게)
git config --global user.name "Your Name"

# 이메일 설정 (GitHub 계정 이메일과 동일하게)
git config --global user.email "your.email@example.com"

# 설정 확인
git config --list
```

## 3. SSH 키 설정 (권장)

### 3.1 SSH 키 생성
```bash
# SSH 키 생성 (이메일을 본인 것으로 변경)
ssh-keygen -t ed25519 -C "your.email@example.com"

# 엔터 3번 입력 (기본 위치 사용, 패스프레이즈 생략 가능)
```

### 3.2 SSH 키 GitHub에 등록
1. 공개 키 확인:
   ```bash
   # Windows
   type %USERPROFILE%\.ssh\id_ed25519.pub

   # Mac/Linux
   cat ~/.ssh/id_ed25519.pub
   ```

2. 출력된 전체 내용 복사 (ssh-ed25519로 시작)

3. GitHub 설정:
   - GitHub.com 로그인
   - 우측 상단 프로필 → Settings
   - 좌측 메뉴 → SSH and GPG keys
   - "New SSH key" 클릭
   - Title: "My Computer" (원하는 이름)
   - Key: 복사한 공개 키 붙여넣기
   - "Add SSH key" 클릭

### 3.3 SSH 연결 테스트
```bash
ssh -T git@github.com
# "Hi username! You've successfully authenticated..." 메시지 확인
```

## 4. Personal Access Token 설정 (대안)

SSH 대신 HTTPS를 사용하려면:

### 4.1 Token 생성
1. GitHub.com → Settings → Developer settings
2. Personal access tokens → Tokens (classic)
3. "Generate new token" → Generate new token (classic)
4. Note: "device-manager-access"
5. Expiration: 90 days (또는 원하는 기간)
6. Scopes: repo 체크 (전체)
7. "Generate token" 클릭
8. **토큰 복사 및 안전한 곳에 저장** (다시 볼 수 없음!)

### 4.2 Token 사용
HTTPS clone 시 패스워드 대신 토큰 입력:
```bash
# 클론 예시
git clone https://github.com/username/repository.git
Username: your-github-username
Password: your-personal-access-token
```

## 5. 첫 커밋과 푸시

### 5.1 로컬 저장소 초기화
```bash
# 프로젝트 디렉토리로 이동
cd d:\Project\TSWS\Source\device_manager

# Git 저장소 초기화
git init

# 기본 브랜치명을 main으로 설정
git branch -M main
```

### 5.2 원격 저장소 연결
```bash
# SSH 방식 (권장)
git remote add origin git@github.com:your-username/itlog-device-manager.git

# 또는 HTTPS 방식
git remote add origin https://github.com/your-username/itlog-device-manager.git

# 연결 확인
git remote -v
```

### 5.3 .gitignore 파일 생성
```bash
# .gitignore 파일 생성 및 편집
echo "# Python" > .gitignore
echo "__pycache__/" >> .gitignore
echo "*.py[cod]" >> .gitignore
echo "*$py.class" >> .gitignore
echo "venv_webapp/" >> .gitignore
echo "*.db" >> .gitignore
echo ".env" >> .gitignore
echo "release/" >> .gitignore
echo "build/" >> .gitignore
echo "dist/" >> .gitignore
echo "*.spec" >> .gitignore
```

### 5.4 첫 커밋 생성
```bash
# 모든 파일을 스테이징 영역에 추가
git add .

# 상태 확인
git status

# 첫 커밋 생성
git commit -m "Initial commit: ITLog Device Manager project setup"
```

### 5.5 GitHub에 푸시
```bash
# 원격 저장소에 푸시
git push -u origin main

# 이후부터는 간단히 push 가능
git push
```

## 6. Git 초보자 필수 지식

### 6.1 기본 명령어
```bash
# 상태 확인
git status

# 변경사항 확인
git diff

# 파일 추가
git add filename.txt        # 특정 파일
git add .                   # 모든 파일
git add *.py               # 특정 패턴

# 커밋
git commit -m "메시지"      # 간단한 커밋
git commit -am "메시지"     # add + commit (수정된 파일만)

# 히스토리 확인
git log                    # 전체 로그
git log --oneline         # 한 줄로 보기
git log --graph           # 그래프로 보기

# 원격 저장소 작업
git pull                  # 가져오기 + 병합
git push                  # 업로드
git fetch                 # 가져오기만
```

### 6.2 브랜치 작업
```bash
# 브랜치 목록
git branch

# 새 브랜치 생성 및 이동
git checkout -b feature/new-feature

# 브랜치 이동
git checkout main

# 브랜치 병합 (main에 feature 병합)
git checkout main
git merge feature/new-feature

# 브랜치 삭제
git branch -d feature/new-feature
```

### 6.3 작업 되돌리기
```bash
# 스테이징 취소
git reset HEAD filename.txt

# 마지막 커밋 수정
git commit --amend -m "새 메시지"

# 변경사항 되돌리기
git checkout -- filename.txt

# 커밋 되돌리기 (기록 유지)
git revert HEAD
```

## 7. 자주 발생하는 문제와 해결법

### 문제 1: Permission denied (publickey)
**원인**: SSH 키가 제대로 설정되지 않음
**해결**:
```bash
# SSH 에이전트 시작
eval "$(ssh-agent -s)"

# SSH 키 추가
ssh-add ~/.ssh/id_ed25519

# 다시 테스트
ssh -T git@github.com
```

### 문제 2: rejected - non-fast-forward
**원인**: 원격 저장소에 로컬에 없는 커밋이 있음
**해결**:
```bash
# 원격 변경사항 가져오기
git pull --rebase origin main

# 충돌 해결 후
git push
```

### 문제 3: 충돌(Conflict) 발생
**원인**: 같은 파일의 같은 부분을 여러 사람이 수정
**해결**:
```bash
# 1. pull 시도
git pull

# 2. 충돌 파일 확인
git status

# 3. 파일 열어서 수동 수정
# <<<<<<< HEAD
# 내 변경사항
# =======
# 다른 사람 변경사항
# >>>>>>> branch-name

# 4. 수정 후 커밋
git add .
git commit -m "Resolve merge conflict"
git push
```

### 문제 4: 큰 파일 푸시 실패
**원인**: GitHub는 100MB 이상 파일 제한
**해결**:
```bash
# Git LFS 설치
git lfs track "*.db"
git lfs track "*.exe"
git add .gitattributes
git commit -m "Add Git LFS tracking"
```

### 문제 5: 실수로 민감한 정보 커밋
**원인**: .env, 패스워드 등을 실수로 커밋
**해결**:
```bash
# 파일 히스토리에서 완전 제거
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all

# 강제 푸시 (위험!)
git push origin --force --all
```

## 💡 추가 팁

### 커밋 메시지 작성 규칙
```
feat: 새로운 기능 추가
fix: 버그 수정
docs: 문서 수정
style: 코드 포맷팅, 세미콜론 누락 등
refactor: 코드 리팩토링
test: 테스트 코드
chore: 빌드 업무, 패키지 매니저 수정 등
```

### 유용한 Git 별칭 설정
```bash
git config --global alias.st status
git config --global alias.co checkout
git config --global alias.br branch
git config --global alias.cm commit
git config --global alias.lg "log --oneline --graph --all"
```

### GUI 도구 추천
- **GitHub Desktop**: 초보자 친화적
- **SourceTree**: 무료, 기능 풍부
- **GitKraken**: 시각적으로 우수
- **VSCode Git Extension**: 에디터 내장

## 📞 도움 받기
- [Git 공식 문서](https://git-scm.com/doc)
- [GitHub Guides](https://guides.github.com/)
- [Pro Git Book (한국어)](https://git-scm.com/book/ko/v2)

---

이제 Git과 GitHub를 사용할 준비가 완료되었습니다! 🚀