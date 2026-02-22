# 배포 가이드

24시간 PC에서 Docker로 실행하고, 외부에서 Cloudflare Tunnel을 통해 접속하는 방법.

---

## 사전 요구사항

- Docker Desktop (Windows) 또는 Docker Engine (Linux)
- Git

---

## 1. 설치

```bash
git clone <repo-url>
cd quantum-campaign-automation
cp .env.example .env
```

`.env` 파일을 열고 필요한 값을 설정:

```env
SECRET_KEY=your-random-secret-key-here
SUPERAP_ACCOUNTS='[{"user_id":"계정ID","password":"비밀번호","agency":"대행사명"}]'
```

---

## 2. 실행

```bash
# 빌드 + 백그라운드 실행
docker compose up -d --build

# 상태 확인
docker compose ps

# 로그 확인
docker compose logs -f
```

정상 실행 시:
- **대시보드**: http://localhost:3000
- **API 문서**: http://localhost:3000/api/docs
- **헬스체크**: http://localhost:3000/api/health

---

## 3. 외부 접속 (Cloudflare Tunnel)

### 방법 A: Quick Tunnel (간편, URL 변경됨)

계정 없이 바로 사용. 재시작 시 URL이 변경됨.

```bash
docker compose --profile tunnel-quick up cloudflared-quick
```

출력에서 `https://xxxx.trycloudflare.com` URL을 확인하여 접속.

### 방법 B: Named Tunnel (고정 URL)

Cloudflare 계정이 필요하지만 고정 도메인 사용 가능.

1. [Cloudflare Zero Trust 대시보드](https://one.dash.cloudflare.com/) 접속
2. Networks > Tunnels > Create a tunnel
3. Tunnel 생성 후 토큰 복사
4. `.env`에 토큰 설정:
   ```env
   CLOUDFLARE_TUNNEL_TOKEN=your-token-here
   ```
5. 실행:
   ```bash
   docker compose --profile tunnel up -d
   ```

---

## 4. 주요 명령어

```bash
# 전체 시작
docker compose up -d

# 전체 중지
docker compose down

# 재빌드 (코드 변경 시)
docker compose up -d --build

# 로그 확인 (실시간)
docker compose logs -f backend
docker compose logs -f frontend

# 개별 서비스 재시작
docker compose restart backend
```

---

## 5. 데이터 관리

### DB 위치
- 호스트: `./data/quantum.db`
- 컨테이너: `/app/data/quantum.db`

### 백업
```bash
# DB 백업
cp data/quantum.db data/quantum_backup_$(date +%Y%m%d).db
```

### 초기화
```bash
# DB 삭제 후 재시작하면 빈 DB로 시작
rm data/quantum.db
docker compose restart backend
```

---

## 6. 업데이트

```bash
git pull
docker compose up -d --build
```

DB 스키마 변경이 있어도 자동 마이그레이션(컬럼 추가)이 실행됨.

---

## 7. 자동 시작 설정

### Docker Desktop (Windows)
Settings > General > "Start Docker Desktop when you sign in" 체크.
`docker-compose.yml`의 `restart: always` 설정으로 Docker가 시작되면 컨테이너도 자동 시작.

### Linux (systemd)
```bash
sudo systemctl enable docker
```

---

## 8. 포트 변경

`.env`에서 포트 변경 가능:
```env
FRONTEND_PORT=8080
```

---

## 9. 트러블슈팅

### 컨테이너가 시작되지 않음
```bash
docker compose logs backend
docker compose logs frontend
```

### 포트 충돌
```bash
# 3000번 포트를 사용 중인 프로세스 확인 (Windows)
netstat -ano | findstr :3000
```
`.env`에서 `FRONTEND_PORT`를 다른 포트로 변경.

### DB 오류
```bash
# DB 파일 권한 확인
ls -la data/

# DB 삭제 후 재시작
rm data/quantum.db
docker compose restart backend
```

### 빌드 실패
```bash
# 캐시 없이 재빌드
docker compose build --no-cache
docker compose up -d
```

### Cloudflare Tunnel 연결 안 됨
```bash
# tunnel 로그 확인
docker compose --profile tunnel-quick logs cloudflared-quick
```

---

## 구성 요약

```
[외부 브라우저]
    │
    ▼
[Cloudflare Tunnel] ──── https://xxxx.trycloudflare.com
    │
    ▼
[nginx (frontend)]  ──── :3000
    │
    ├── /api/* ──▶ [uvicorn (backend)] :8000
    │                    │
    │                    ├── SQLite DB  (./data/)
    │                    ├── APScheduler (키워드 로테이션)
    │                    └── Playwright  (superap 자동화)
    │
    └── /* ──▶ React SPA (정적 파일)
```
