# K-Shorts — 한국 예능 자동 숏폼 편집기

YouTube 예능 영상을 입력하면 AI가 재미있는 구간을 자동으로 잘라 1080×1920 Shorts 영상으로 출력합니다.

---

## 아키텍처

```
YouTube URL
    │
    ▼
[1. Download]  yt-dlp → 1080p mp4 + audio.wav
    │
    ▼
[2. ASR]       faster-whisper large-v3 (GPU)
               → 단어별 타임스탬프 / 30초 청크 서브프로세스 / asr_cache.json
    │
    ▼
[3. Signals]   오디오 신호 5종 병렬 분석
               retention · volume · tempo · laughter · emotion
    │
    ▼
[4. Scoring]   Ollama LLM (qwen3:8b)
               피크 인근 자막 샘플링 → 재미 구간 3개 선택
    │
    ▼
[5. Render]    ffmpeg — 레이아웃 + ASS 자막 합성
               → rendered_{template}.mp4
```

---

## 파이프라인 단계별 상세

### 1. Download (`app/pipeline/stages/download.py`)
- yt-dlp로 `bestvideo[ext=mp4]+bestaudio[ext=m4a]` 포맷 다운로드 (ffmpeg merge)
- 1920×1080 원본 화질 유지
- YouTube 조회수 heatmap 추출 (retention 신호로 활용)

### 2. ASR (`app/pipeline/stages/asr.py`)
- faster-whisper large-v3, `int8_float16` 양자화, CUDA
- ctranslate2 native crash 방지: **30초 청크 × 서브프로세스 격리**
  - 크래시 발생 청크는 건너뛰고 계속 진행
- 결과를 `asr_cache.json`에 저장 → 재실행 시 즉시 로드

### 3. Signals (`app/pipeline/signals/`)
| 신호 | 기본 가중치 | 설명 |
|------|------------|------|
| retention | 0.35 | YouTube 시청 유지율 heatmap |
| laughter | 0.25 | PANNs 웃음 감지 |
| volume | 0.15 | RMS 볼륨 피크 |
| emotion | 0.15 | 감정(기쁨·놀람) 강도 |
| tempo | 0.10 | 발화 속도 변화 |

가중치는 사용자 피드백(👍/👎) 기반으로 자동 조정됨

### 4. Scoring (`app/pipeline/stages/score.py`)
- 신호 피크 인근 ±90초 자막 우선 샘플링 → LLM 컨텍스트 제한 내 전체 영상 커버
- Ollama LLM이 재미 점수(1~10)와 제목 생성
- Few-shot: 과거 피드백 기반 예시 자동 삽입

### 5. Render (`app/pipeline/render/engine.py`)
- ffmpeg 기반, 1080×1920 출력
- ASS 자막 burn-in (libass)
- 얼굴 추적 사용 시 선형 보간으로 부드러운 크롭 이동

---

## 템플릿

| ID | 배경 | 자막 | 특징 |
|----|------|------|------|
| `clean` | 검은 여백 | Malgun Gothic | 기본 |
| `soft` | 블러 배경 (σ=25) | Batang 명조 | 감성 |
| `bold` | 블러 배경 (σ=30) | Malgun Gothic Bold | 시선 강조 |
| `split` | 거울 반전 블러 | Malgun Gothic | 예능 감성 |

모든 템플릿: **원본 16:9 영상 중앙 배치 + 상하 배경 변경** (비율 변경 없음)

---

## 실행 방법

### 환경 요구사항
- Python 3.11+
- CUDA GPU (RTX 3070 기준 개발)
- Ollama 실행 중 (`qwen3:8b` 모델)
- ffmpeg (imageio-ffmpeg 내장)

### 설치
```bash
pip install -e ".[dev]"
pip install torch --index-url https://download.pytorch.org/whl/cu121
```

### 서버 실행
```bash
uvicorn app.main:app --host 127.0.0.1 --port 8020 --reload
```

### ASR 캐시 사전 생성 (선택)
```bash
python run_asr.py
```

### API 사용
```bash
# 편집 요청
curl -X POST http://localhost:8020/edit \
  -H "Content-Type: application/json" \
  -d '{"url": "https://youtu.be/...", "template_id": "soft"}'

# 진행 상황 조회
curl http://localhost:8020/jobs/{job_id}

# 결과물 위치
data/clips/{job_id}_{index}/rendered_{template}.mp4
```

---

## 프로젝트 구조

```
backend/
├── app/
│   ├── api/              # FastAPI 라우터
│   ├── db/               # SQLite (클립 기록, 신호 통계, 가중치)
│   ├── models/           # Pydantic 모델
│   ├── pipeline/
│   │   ├── render/
│   │   │   ├── engine.py      # ffmpeg 렌더링 + 레이아웃 필터
│   │   │   ├── subtitles.py   # ASS 자막 생성
│   │   │   └── facetrack.py   # 얼굴 추적 (OpenCV Haar cascade)
│   │   ├── signals/           # 오디오 신호 분석 모듈
│   │   ├── stages/
│   │   │   ├── asr.py         # Whisper 음성 인식
│   │   │   ├── download.py    # yt-dlp 다운로드
│   │   │   ├── render.py      # 렌더 스테이지
│   │   │   └── score.py       # LLM 재미 구간 분석
│   │   └── orchestrator.py    # 파이프라인 실행 관리
│   ├── services/
│   └── templates/        # 템플릿 JSON (clean/soft/bold/split)
├── data/
│   ├── videos/           # 다운로드된 원본 영상 + ASR 캐시
│   └── clips/            # 렌더링 결과물
├── tests/
└── run_asr.py            # 독립 실행형 ASR 캐시 생성 스크립트
```

---

## 완료된 기능

- [x] YouTube 영상 다운로드 (1080p)
- [x] Whisper 음성 인식 + 단어별 타임스탬프
- [x] ASR 캐시 (재실행 시 즉시 로드)
- [x] 오디오 신호 5종 분석 (retention / laughter / volume / emotion / tempo)
- [x] 신호 가중치 자동 진화 (사용자 피드백 기반)
- [x] LLM 재미 구간 선택 (피크 기반 자막 샘플링으로 전체 영상 커버)
- [x] 4종 배경 레이아웃 (black_bars / blur_bg / mirror_bg / blur_top)
- [x] ASS 자막 burn-in
- [x] Few-shot 학습 (과거 👍/👎 피드백 LLM 예시 삽입)
- [x] 침묵 구간 기반 경계 스냅
- [x] 얼굴 추적 선형 보간 (부드러운 크롭 이동)

## 미완성 / 예정

- [ ] **배경 스타일 추가** — 색상 그라디언트, 파티클 등 추가 배경 옵션
- [ ] **자막 개선** — 단어별 하이라이팅, 이모지 자동 삽입, 단어별 팝업 애니메이션
- [ ] **YouTube 자동 업로드** — OAuth2 인증 후 Shorts 자동 업로드 + 제목/설명 자동 생성

---

## 기술 스택

| 영역 | 사용 기술 |
|------|----------|
| 백엔드 | FastAPI + Uvicorn |
| AI / ASR | faster-whisper (large-v3), CUDA |
| LLM | Ollama (qwen3:8b, 로컬) |
| 오디오 분석 | librosa, PANNs, scipy |
| 영상 처리 | ffmpeg, OpenCV, yt-dlp |
| DB | SQLite (SQLAlchemy) |
| 얼굴 감지 | OpenCV Haar cascade |
