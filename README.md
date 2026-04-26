# K-Shorts — Korean Variety Shorts Auto-Editor

한국 예능 롱폼 영상을 입력하면 AI가 재미있는 구간을 찾아 9:16 숏츠로 자동 편집하고 YouTube에 업로드하는 로컬 웹 앱.

설계 문서: [docs/superpowers/specs/2026-04-21-korean-shorts-autoeditor-design.md](docs/superpowers/specs/2026-04-21-korean-shorts-autoeditor-design.md)

## 구성

- `backend/` — FastAPI + ML 파이프라인 (Python 3.11+)
- `frontend/` — Next.js 15 + Tailwind + shadcn/ui
- `data/` — 다운로드 원본·생성된 클립·SQLite DB (git-ignored)
- `docs/` — 설계 스펙

## 실행 전 수동 셋업 (M0)

1. **NVIDIA 드라이버 + CUDA 12.x** — RTX 3070 기준
2. **Ollama 설치** — https://ollama.com/download
   ```
   ollama list                    # 현재 pull 된 모델 확인
   ollama pull qwen3:8b           # 기본값. 더 큰/신형 태그는 ollama search 로 확인 후 .env에 지정
   # EXAONE 3.5 는 커뮤니티 변환 태그 확인 필요
   ```
3. **Python 3.11+**, **Node.js 20+**
4. **YouTube Data API OAuth** — Google Cloud Console에서 앱 등록 후 `client_secret.json` 을 `backend/` 에 저장

## 개발 실행

```bash
# Backend
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Docker Compose

```bash
docker compose up
```

세 서비스: `ollama` (11434), `api` (8000), `web` (3000).
GPU 패스스루는 Docker Desktop (Windows) 에서 WSL2 + NVIDIA Container Toolkit 필요.
