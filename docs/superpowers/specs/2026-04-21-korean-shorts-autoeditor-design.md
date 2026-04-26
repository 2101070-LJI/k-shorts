# 한국 예능 숏츠 자동 편집기 — 설계 명세

- **작성일**: 2026-04-21
- **프로젝트 코드명**: K-Variety Shorts Auto-Editor (이하 "K-Shorts")
- **작업 경로**: `C:\Users\37\claude_workspace\capstone`
- **대상**: 캡스톤 디자인 프로젝트 (논문 작성 없음, 작동하는 툴 제작)

---

## 1. 개요

### 1.1 프로젝트 목표

한국 예능 롱폼(30분~1시간) 영상을 입력받아, **AI가 재미있는 구간을 자동으로 찾고 9:16 세로 숏츠로 편집**하는 로컬 웹 애플리케이션을 제작한다. 기성 도구(Opus Clip)가 커버하지 못하는 **한국어·한국 예능 맥락**에 특화하며, 사용자의 선호와 업로드된 숏츠의 YouTube 지표를 피드백으로 받아 **스스로 학습하는 자기진화형 편집기**로 설계한다.

### 1.2 타겟 사용자 / 사용 시나리오

- **사용자**: 단일 사용자 (프로젝트 제작자 본인)
- **사용 시나리오**: 본인이 선호하는 한국 예능(런닝맨·유퀴즈·무한도전·나영석 예능 등) 풀영상을 주 단위로 넣고, 자동 편집된 숏츠 3개를 YouTube 본인 채널에 업로드. 수 주간 누적된 데이터로 편집 품질이 자동 향상.

### 1.3 범위 (Scope)

**In Scope**
- 한국 예능 영상을 대상으로 한 숏츠 자동 편집
- 로컬 실행 (외부 LLM API 미사용)
- Whisper 기반 한국어 음성 인식
- 5개 신호 기반 Hybrid Scoring (retention·laughter·volume·emotion·tempo)
- 4개 비주얼 템플릿 (Clean/Soft/Bold/Split)
- YouTube Data API로 Shorts 업로드 자동화
- YouTube Analytics 기반 Phase 2 자기진화 (가중치 자동 조정)
- 사용자 👍/👎 기반 Phase 1 선호 학습
- Evolution 페이지 (학습 증거 시각화)

**Out of Scope**
- 예능 외 장르 (강의·브이로그·뉴스·게임 스트림 등) 최적화
- 다중 사용자 / 계정 분리
- 클라우드 배포
- 모바일 앱
- 다중 구간 컴필레이션 편집 (한 숏츠 안에 여러 구간 이어붙이기)
- 커스텀 템플릿 UI 생성기
- 효과음·BGM·이모지 오버레이 (원본 예능이 이미 편집된 완제품이므로 이중편집 방지)
- 키워드 컬러 강조·흔들림 등 자막 장식 (〃)
- LoRA 등 모델 파인튜닝 수준 학습 (데이터 양 제약)
- 논문 작성·학술적 평가 프로토콜(MOS·IRB 등)

### 1.4 차별 포인트 (vs Opus Clip·Vizard 등 기존 도구)

1. **한국어·한국 예능 특화** — Opus Clip이 한국어 맥락·유머 코드 해석에 약함. 한국어 어휘 비중 높은 LLM(Qwen3.5, EXAONE-3.5) 사용.
2. **완전 로컬 실행** — 외부 API 비용 0, 개인정보 유출 없음, quota 제한 없음.
3. **자기진화 피드백 루프** — 사용자의 명시적 선호(Phase 1) + YouTube 실제 성과(Phase 2) 로 가중치 자동 조정.
4. **템플릿 시스템** — 같은 구간을 여러 비주얼 스타일로 재렌더링 가능.

### 1.5 성공 기준

- **작동성**: 유튜브 URL 입력 → 5~10분 내 3개 숏츠 mp4 생성 성공률 ≥ 90%
- **품질 체감**: 생성된 숏츠가 발표장·지인·본인 기준 "재미있다" 판단 가능한 수준
- **자기진화 증거**: 캡스톤 기간 내 가중치 최소 2회 자동 업데이트, Evolution 차트로 시각화 가능
- **발표 데모**: 심사위원 앞에서 URL 붙여넣고 실제 편집·업로드까지 5분 내 시연 성공

---

## 2. 시스템 아키텍처

### 2.1 전체 구조

```
┌──────────────────────────────────────────────────────────┐
│  브라우저 (localhost:3000)  — Next.js 15 + Tailwind      │
│  페이지: Edit / History / Evolution / Settings            │
└─────────────┬────────────────────────────────────────────┘
              │ HTTP (REST) + WebSocket (진행률)
┌─────────────▼────────────────────────────────────────────┐
│  FastAPI 백엔드 (localhost:8000)                          │
│  ├─ 작업 오케스트레이션 (BackgroundTasks + APScheduler)     │
│  ├─ 파이프라인 스테이지 (다운로드·ASR·scoring·렌더)        │
│  ├─ DB 액세스 (SQLite)                                    │
│  ├─ YouTube Data/Analytics API 클라이언트                 │
│  └─ WebSocket 진행률 publisher                            │
└─────┬─────────────────────┬──────────────────┬───────────┘
      │                     │                  │
      ▼                     ▼                  ▼
┌───────────┐        ┌──────────────┐   ┌──────────────┐
│  Ollama   │        │  로컬 파일     │   │   SQLite      │
│  :11434   │        │  /data/       │   │   k-shorts.db │
│ Qwen3.5-9B│        │  ├─ videos/  │   │               │
│ EXAONE3.5 │        │  ├─ clips/   │   │  clips,       │
│           │        │  ├─ models/  │   │  preferences, │
└───────────┘        │  └─ fonts/   │   │  metrics,     │
                     └──────────────┘   │  weight_history│
                                         └──────────────┘
```

### 2.2 컴포넌트별 기술 선택

| 계층 | 선택 | 근거 |
|---|---|---|
| 프론트엔드 | Next.js 15 (App Router) + Tailwind + shadcn/ui | 빠른 UI 개발, 세련된 기본 컴포넌트 |
| 백엔드 | FastAPI + Uvicorn | ML 라이브러리와 궁합 좋음, 비동기 지원 |
| LLM 런타임 | Ollama | 모델 스왑 용이, OpenAI 호환 API |
| ASR | faster-whisper (large-v3) | GPU 가속, 단어 단위 타임스탬프 |
| 영상 다운로드 | yt-dlp | heatmap·메타 자동 포함, 다중 사이트 지원 |
| 영상 처리 | ffmpeg + moviepy | 업계 표준 |
| 얼굴 추적 | MediaPipe Face Landmarker | 경량, 실시간 |
| 오디오 분석 | librosa + panns_inference + Wav2Vec2-Emotion | 신호별 검증된 도구 |
| 작업 큐 | FastAPI BackgroundTasks | 단일 사용자 스케일에 충분 |
| 스케줄러 | APScheduler (cron) | 주 1회 지표 수집에 적합 |
| DB | SQLite | 단일 사용자, 이식성, 백업 편의 |
| 패키징 | Docker Compose | ollama+api+web 3개 서비스 통합 실행 |

### 2.3 로컬 파일 구조

```
/data/
├── videos/              # yt-dlp로 다운받은 원본 영상 (mp4)
│   └── {yt_video_id}/
│       ├── source.mp4
│       ├── info.json    # heatmap 포함
│       └── audio.wav
├── clips/               # 생성된 숏츠 결과물
│   └── {clip_id}/
│       ├── rendered_clean.mp4
│       ├── rendered_soft.mp4
│       ├── subtitles.ass
│       └── metadata.json
├── models/              # Ollama 모델 캐시 경로
└── k-shorts.db          # SQLite DB
```

### 2.4 LLM 모델

| 모델 | 역할 | VRAM (Q4_K_M) | 라이선스 |
|---|---|---|---|
| **Qwen3-8B-Instruct** (기본) | Primary (scoring·메타데이터 생성) | ~6.0GB | Apache 2.0 |
| **EXAONE-3.5-7.8B-Instruct** | Secondary (한국어 뉘앙스 비교용) | ~5.2GB | 비상업 (연구 OK) |

`DEFAULT_LLM_MODEL` 환경변수로 교체 가능. Qwen3.5 등 신형 태그가 로컬에 있으면 그대로 지정하면 된다 (`.env`). **Settings > Model 에서 편집 시 전환 가능**. 발표 데모에서 "같은 영상, 두 모델 결과 비교" 시연에 사용.

### 2.5 VRAM 관리 (RTX 3070 8GB)

**제약**: Whisper large-v3 (~2.5GB) + Qwen3.5-9B Q4 (~7GB) = 9.5GB → 동시 거주 불가.

**전략: 순차 로드**
```
[ASR 단계] Whisper 로드 → 자막 생성 → Whisper 언로드 (VRAM 회수)
[Scoring 단계] LLM 로드 → scoring → LLM 유지 (이후 메타 생성에도 재사용)
```
로드 오버헤드 약 5~10초/전환. 총 처리시간에 큰 영향 없음.

**백업 옵션 (M0 실측 후 결정)**: Whisper `large-v3-turbo` (~1.5GB) 사용 시 동시 거주 가능. 정확도 소폭 감소.

---

## 3. 재미 판단 엔진 (Scoring Engine)

### 3.1 접근 방식: Hybrid (오디오 신호 + LLM)

Pure LLM (자막만) 접근은 텍스트로 드러나지 않는 재미(웃음·탄성·반응)를 놓침. 5개 오디오/메타 신호로 "주목할 지점"을 추출하고, LLM이 자막 맥락과 함께 최종 구간을 선정한다.

### 3.2 입력 신호 5종

| 신호 | 산출 방법 | 특성 |
|---|---|---|
| **retention** | yt-dlp 추출 heatmap (YouTube "Most Replayed") | 수만 시청자 집단지성, **가장 강한 prior**, 없을 수 있음 |
| **laughter** | panns_inference (AudioSet pretrained audio event detection) | 웃음 감지 직접, 예능 핵심 |
| **volume** | librosa RMS envelope 피크 | 소리지름·박수·탄성 |
| **emotion** | Wav2Vec2-Emotion-Korean (joy / surprise 확률) | 음성 감정 전환 |
| **tempo** | 단어 밀도 (words / 10s window) 변화율 | 흥분·급가속 |

### 3.3 신호 통합 → `audio_interest_score(t)`

```
audio_interest_score(t) = 
      w_retention * retention(t)
    + w_laughter  * laughter(t)
    + w_volume    * volume(t)
    + w_emotion   * emotion(t)
    + w_tempo     * tempo(t)
```

**초기 가중치 (hypothesis, Phase 2에서 자동 조정됨)**:

| 신호 | 초기값 |
|---|---|
| retention | 0.35 |
| laughter | 0.25 |
| volume | 0.15 |
| emotion | 0.15 |
| tempo | 0.10 |

**가중치 정책**:
- `weight_history` 테이블에서 매 편집 시 최신값 로드
- `weights_snapshot` 필드로 각 clip 생성 시점 가중치 기록 (재현 가능성)
- Safety guard: 모든 가중치 `[0.05, 0.60]` 범위 clamp
- Phase 2 업데이트 시 합계 1.0 정규화

### 3.4 heatmap 폴백 정책

heatmap 미제공 영상 (비인기·신규·개인 채널 등) 인식 시:
- `w_retention = 0` 으로 처리
- 나머지 4개 신호 가중치는 기존 비율 유지하며 합계 1.0 정규화
- UI에 "retention 데이터 없음" 안내 배지 표시

### 3.5 피크 추출 알고리즘

```python
def extract_peaks(score: np.ndarray, sr=1) -> List[Peak]:
    """
    - 1초 단위 score 배열에서 지역 최대 탐지
    - 최소 간격 30초 (피크 간 겹침 방지)
    - threshold: score 상위 30% 이상만
    """
    peaks = scipy.signal.find_peaks(score, distance=30, 
                                     height=np.quantile(score, 0.7))
    return top_10(peaks)
```

### 3.6 LLM 프롬프트 템플릿

```
역할: 당신은 한국 예능 숏츠 편집자이다.

[전체 자막 — 단어 단위 타임스탬프]
00:00.1  안녕하세요
00:00.8  오늘은
...

[오디오 신호가 주목한 지점 10개]
- 02:15 (laughter 0.92, volume 0.81, surprise 0.74, retention 0.88)
- 04:30 (laughter 0.45, volume 0.95, retention 0.76)
- 07:45 (laughter 0.88, emotion_joy 0.82)
...

[사용자가 과거에 선호한 구간 예시 — Phase 1]
(few-shot 3개: 👍 2개 + 👎 1개)

[제약]
- 구간 길이 15~59초
- 구간끼리 최소 30초 간격
- 말 중간에서 시작/끝 금지 (단어 경계에 맞춤)

[출력 — JSON만]
{
  "clips": [
    {
      "start": "02:10.0",
      "end":   "02:58.5",
      "title": "...",
      "reason": "...",
      "score": 9.2
    },
    ...3개
  ]
}
```

### 3.7 경계 정밀 조정 (Snap Rules)

LLM이 제안한 `start/end` 를 후처리로 조정:
1. **앞쪽**: 가장 가까운 침묵 ≥ 0.3초 지점으로 당김
2. **뒤쪽**: 가장 가까운 침묵 ≥ 0.3초 지점으로 늘리고, 웃음·탄성 여운 1초 포함
3. **단어 경계**: Whisper word-timestamp에서 최근접 단어 시작·끝에 스냅
4. **길이 강제**: 15초 미만이면 앞뒤로 확장, 59초 초과면 핵심 중심 트림

---

## 4. 비디오 처리 파이프라인

### 4.1 파이프라인 순서

```
선정 구간 (start, end)
  ↓ [4A] 경계 스냅
자른 클립 (16:9)
  ↓ [4B] Layout 적용 (face-track / split / letterbox)
세로 클립 (1080×1920)
  ↓ [4C] Caption burn-in (Whisper + 템플릿 스타일)
완성 숏츠 mp4
```

### 4.2 9:16 Reframe 전략

**1차 범위: Face-track crop 단일**. (Split은 템플릿 선택 시에만 활성화)

**MediaPipe Face Landmarker** 로 프레임별 얼굴 검출 → 가장 큰 얼굴(또는 중앙에 가까운 얼굴) 중심으로 크롭 윈도우 배치 → **EMA smoothing** (α=0.85) 으로 부드럽게 이동.

```python
# 의사코드
for frame in clip:
    faces = mp_detector.detect(frame)
    target = pick_primary_face(faces)  # 가장 크고 중앙에 가까운
    target_x = target.center_x
    smoothed_x = alpha * prev_x + (1 - alpha) * target_x
    crop_window = compute_9_16_crop(smoothed_x, frame.height)
    yield frame.crop(crop_window).resize(1080, 1920)
```

**Cut detection**: 씬 전환 감지 시 EMA 리셋 (pyscene-detect 사용).

**Fallback**: 얼굴 검출 실패 시 center crop + letterbox.

### 4.3 자막 처리

**원본 예능에 이미 자막이 박혀있는 상황**을 전제로 설계.

- **목적**: 음소거 자동재생 시청자 대응 + YouTube 알고리즘 자막 파싱
- **원칙**: 원본 자막과 시각적으로 경쟁하지 않는 **보조적** 스타일
- **위치**: 하단 18~25% 고정 (원본 자막은 보통 중단 이상)
- **배경**: 반투명 검은 박스(opacity 0.4)로 가독성 확보
- **소스**: Whisper large-v3 한국어 모드의 word-timestamp
- **블록 구성**: 2~3 단어/줄, 1.5~2초 체류
- **포맷**: ASS subtitle → ffmpeg `-vf subtitles` 로 burn-in

### 4.4 폰트 번들링

한글 렌더링 환경 의존성 제거를 위해 OTF/TTF 를 repo `backend/fonts/` 에 포함 (런타임 경로는 JSON 템플릿 내 `fonts/` 상대 경로로 참조):
- `Pretendard-Medium.otf` (기본)
- `NanumSquare_acB.ttf` (Bold 강조)
- `NanumMyeongjo-Regular.ttf` (감성)

### 4.5 렌더 성능 목표

**RTX 3070 8GB 기준, 30분 원본 → 60초 숏츠 1개**:

| 단계 | 예상 시간 |
|---|---|
| 다운로드 | 30~60초 (네트워크 의존) |
| ASR (Whisper) | 30~45초 |
| 오디오 신호 분석 | 20~30초 |
| LLM scoring | 20~30초 |
| 9:16 reframe + 자막 렌더 | 40~60초 |
| **합계 (1개)** | **약 2~3분** |
| **3개 후보 동시 렌더** | **약 5~7분** |

---

## 5. 템플릿 시스템

### 5.1 설계 원칙

- 템플릿은 **렌더링 단계** 만 영향 (scoring은 공통)
- 같은 후보 구간을 여러 템플릿으로 재렌더 가능 — 재스코어링 없음
- 템플릿은 **JSON 파일**. 코드 변경 없이 추가/수정
- 효과음·BGM·이모지·키워드 강조 **제외** (원본 예능이 이미 편집된 완제품이므로 이중편집 회피)

### 5.2 템플릿 차원 (3개)

| 차원 | 설명 |
|---|---|
| **Layout** | 영상 배치: face-track / split / letterbox |
| **Caption** | 폰트·크기·색상·외곽선·위치·배경 |
| **Animation** | 자막 등장 효과: 팝업 / 페이드 / 슬라이드 / 없음 |

### 5.3 프리셋 4종

#### Clean (기본)
```json
{
  "id": "clean",
  "name": "Clean",
  "description": "음소거 대응 보조 자막, 원본 방해 최소",
  "layout": {
    "type": "face_track",
    "smoothing": {"alpha": 0.85, "method": "ema"}
  },
  "caption": {
    "font": "fonts/Pretendard-Medium.otf",
    "size": 62,
    "color": "#FFFFFF",
    "stroke": "#000000",
    "stroke_width": 3,
    "position": {"anchor": "bottom", "margin_y": 180},
    "background": {"color": "#000000", "opacity": 0.4, "padding": 12}
  },
  "animation": {"type": "none"}
}
```

#### Soft (감성)
```json
{
  "id": "soft",
  "layout": {
    "type": "face_track_letterbox",
    "letterbox_top": 0.10,
    "letterbox_bottom": 0.10,
    "letterbox_blur": 30
  },
  "caption": {
    "font": "fonts/NanumMyeongjo-Regular.ttf",
    "size": 58,
    "color": "#FFFFFF",
    "shadow": {"offset": [2, 2], "blur": 8, "opacity": 0.5},
    "position": {"anchor": "bottom", "margin_y": 160}
  },
  "animation": {"type": "fade", "duration": 0.4}
}
```

#### Bold (강조)
```json
{
  "id": "bold",
  "layout": {"type": "face_track", "zoom": 1.1},
  "caption": {
    "font": "fonts/NanumSquare_acB.ttf",
    "size": 75,
    "color": "#FFFFFF",
    "stroke": "#000000",
    "stroke_width": 5,
    "position": {"anchor": "bottom", "margin_y": 200}
  },
  "animation": {"type": "pop", "duration": 0.1, "scale_from": 1.15}
}
```

#### Split (투샷)
```json
{
  "id": "split",
  "layout": {
    "type": "split_screen",
    "orientation": "vertical",
    "require_two_faces": true,
    "fallback": {
      "type": "face_track",
      "smoothing": {"alpha": 0.85, "method": "ema"}
    }
  },
  "caption": {
    "font": "fonts/Pretendard-Medium.otf",
    "size": 55,
    "color": "#FFFFFF",
    "stroke": "#000000",
    "stroke_width": 3,
    "position": {"anchor": "center", "margin_y": 0}
  },
  "animation": {"type": "none"}
}
```

### 5.4 렌더 엔진 분기 로직

```python
def render(clip, template_id: str, signals: ClipSignals) -> Path:
    tpl = TemplateLoader.load(template_id)
    
    # Layout
    if tpl.layout.type == "face_track":
        frames = face_track_pipeline(clip, tpl.layout)
    elif tpl.layout.type == "face_track_letterbox":
        frames = letterbox_pipeline(clip, tpl.layout)
    elif tpl.layout.type == "split_screen":
        if not has_stable_two_faces(clip):
            # Fallback
            frames = face_track_pipeline(clip, tpl.layout.fallback)
        else:
            frames = split_pipeline(clip, tpl.layout)
    
    # Caption
    subtitle_file = build_ass_subtitle(
        words=signals.whisper_words,
        style=tpl.caption,
        animation=tpl.animation
    )
    
    # Render
    return ffmpeg_render(frames, subtitle_file, template_id)
```

### 5.5 재렌더 흐름 (캐시)

```
[첫 편집]
URL → download → ASR → signals → scoring → [cache: signals, candidates]
        → render with Clean → display

[템플릿 변경 요청]
cache hit → render with Soft (scoring 재실행 없음) → 30초 내 완료
```

캐시 키: `hash(source_url + clip_start + clip_end)`.

---

## 6. UI / UX

### 6.1 페이지 구성 (4개)

| 페이지 | 경로 | 역할 |
|---|---|---|
| Edit | `/` | URL 입력·편집·결과 보기·업로드 (메인) |
| History | `/history` | 과거 편집·YT 지표 테이블 |
| Evolution | `/evolution` | 가중치 변화·성과 시각화 (발표 킬러 페이지) |
| Settings | `/settings` | 모델 전환·OAuth·경로·수동 가중치 override |

### 6.2 Edit 페이지 상태 흐름

```
[상태 A — 입력 전]
상단에 로고·탭 / 중앙에 URL 입력 / 하단에 Model 드롭다운·편집 시작 버튼

↓ 편집 시작

[상태 B — 처리 중 (5~7분)]
- 스테이지 목록 (다운로드 / ASR / 신호분석 / scoring / 렌더)
- 현재 스테이지 프로그래스바 + 세부 텍스트
- WebSocket 실시간 업데이트
- 취소 버튼

↓ 완료

[상태 C — 결과]
- 3개 카드 (세로 미리보기·hover 자동재생)
- 각 카드: 제목·타임스탬프·점수·LLM 이유·👍👎·템플릿 드롭다운·다운로드·YT 업로드
```

### 6.3 Edit 페이지 — 결과 카드 상세

```
┌──────────────┐
│  9:16 미리보기 │ hover 시 자동재생 (음소거)
│              │
│              │
├──────────────┤
│ 게스트의 의외  │  title
│ 발언           │
│ 02:15→03:10   │  시작→끝
│ ⭐ 9.2        │  LLM score
│               │
│ 🧠 이유:      │
│ 대화 맥락에서 │  LLM의 선정 근거
│ 반전이 있고   │
│ 폭소 반응...  │
│               │
│ 🎨 템플릿:     │
│ [Clean ▼]    │  드롭다운 변경 시 즉시 재렌더
│               │
│ 👍  👎       │  Phase 1 피드백
│               │
│ [다운로드]    │
│ [YT 업로드]   │
└──────────────┘
```

### 6.4 History 페이지

```
┌──────────────────────────────────────────────────────────────┐
│ 날짜      | 원본(썸네일+제목) | 제목    | 조회수 | 좋아요 | 평균시청 | 템플릿 │
├──────────────────────────────────────────────────────────────┤
│ 2026-04-20| [런닝맨 #585]    | 의외발언 | 12,453| 412   | 47초    | Clean │
│ ...                                                             │
└──────────────────────────────────────────────────────────────┘
```
- 컬럼 정렬 가능
- 행 클릭 시 상세 모달 (자막·이유·사용된 가중치 스냅샷)
- 지표는 Phase 2 cron으로 자동 새로고침

### 6.5 Evolution 페이지 (발표 킬러)

**상단 요약 카드**
```
총 편집: 47개  |  총 조회수: 342,181  |  누적 피드백: 41건
학습 후 평균 성과 +183%  |  가중치 업데이트 4회
```
자동 생성 메시지. `generate_insights()` 함수가 DB 쿼리 결과로 문구 조립.

**차트 3종**
1. **가중치 변화** — Stacked Area (5개 신호 색상 코드로 구분)
2. **성과 트렌드** — Line (주별 평균 `performance_score`)
3. **상위 vs 하위 신호 비교** — Grouped Bar (top 25% / bot 25% 클립의 각 신호 평균)

라이브러리: Recharts.

### 6.6 Settings 페이지

- **Model**: Qwen3.5-9B / EXAONE-3.5-7.8B 라디오
- **YouTube 연결**: OAuth 버튼, 현재 연결 상태
- **스타일 프리셋**: 예능 (현재 1개, 확장 슬롯)
- **Advanced**
  - 수동 가중치 override (5개 슬라이더, 합계 자동 정규화)
  - 지표 수동 새로고침 버튼
  - 가중치 업데이트 수동 트리거
  - 데이터 경로 확인

### 6.7 디자인 톤

- **다크 모드 기본** (배경 `#0a0a0a`, 카드 `#1a1a1a`, 포인트 `#FFE100`)
- **폰트**: Pretendard (한글 가독성 우수)
- **아이콘**: Lucide (shadcn/ui 기본)
- **애니메이션**: Framer Motion (카드 fade-in, 진행률)

---

## 7. Self-improving Feedback Loop

### 7.1 전체 흐름

```
편집 → 👍/👎 클릭 ────────────→ Phase 1: 즉시 LLM 프롬프트 few-shot
     ↓
 YT 업로드
     ↓
주 1회 APScheduler cron
  → YT Analytics API 호출
  → metrics DB 누적
     ↓
+10개 누적 시
  → performance_score 계산
  → 상위 25% vs 하위 25% 분석
  → 가중치 자동 조정 (Phase 2)
  → weight_history 기록
     ↓
다음 편집부터 새 가중치 적용
```

### 7.2 데이터 모델 (SQLite)

#### `clips`
```sql
CREATE TABLE clips (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  source_url TEXT NOT NULL,
  source_video_id TEXT NOT NULL,
  start_time REAL NOT NULL,
  end_time REAL NOT NULL,
  title TEXT,
  reason TEXT,
  template_id TEXT NOT NULL,
  llm_model TEXT NOT NULL,
  llm_score REAL,
  weights_snapshot TEXT NOT NULL,  -- JSON
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  yt_video_id TEXT
);
CREATE INDEX idx_clips_source ON clips(source_video_id);
CREATE INDEX idx_clips_yt ON clips(yt_video_id);
```

#### `clip_signals`
```sql
CREATE TABLE clip_signals (
  clip_id INTEGER PRIMARY KEY REFERENCES clips(id),
  retention_avg REAL,            -- NULL if heatmap unavailable
  laughter_peak REAL,
  volume_peak REAL,
  emotion_joy_peak REAL,
  emotion_surprise_peak REAL,
  tempo_change REAL,
  clip_duration REAL,
  whisper_text TEXT
);
```

#### `preferences` (Phase 1)
```sql
CREATE TABLE preferences (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  clip_id INTEGER NOT NULL REFERENCES clips(id),
  label INTEGER NOT NULL CHECK (label IN (-1, 1)),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `metrics` (Phase 2, 시계열)
```sql
CREATE TABLE metrics (
  clip_id INTEGER NOT NULL REFERENCES clips(id),
  collected_at TIMESTAMP NOT NULL,
  views INTEGER,
  likes INTEGER,
  comments INTEGER,
  avg_view_duration REAL,        -- 초
  avg_view_percentage REAL,      -- 0~100
  impressions INTEGER,
  swipe_away_rate REAL,
  PRIMARY KEY (clip_id, collected_at)
);
```

#### `weight_history`
```sql
CREATE TABLE weight_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  effective_from TIMESTAMP NOT NULL,
  w_retention REAL NOT NULL,
  w_laughter REAL NOT NULL,
  w_volume REAL NOT NULL,
  w_emotion REAL NOT NULL,
  w_tempo REAL NOT NULL,
  update_reason TEXT NOT NULL,    -- 'initial' | 'auto_phase2' | 'manual'
  trigger_clip_count INTEGER,
  notes TEXT
);
```

### 7.3 Phase 1 — 즉시 선호

**기록**: `POST /preferences/record { clip_id, label }` → DB insert.

**활용 — Few-shot 주입**:
- 매 편집마다 DB에서 선호 3개 샘플링 (👍 2개 + 👎 1개)
- 다양성 기준: 같은 `source_video_id` 중복 회피
- LLM 프롬프트 `[사용자가 과거에 선호한 구간 예시]` 섹션에 삽입

**콜드스타트**: 누적 선호 < 5 시 few-shot 생략.

### 7.4 Phase 2 — 가중치 자동 조정

#### 지표 수집 cron
```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

@scheduler.scheduled_job('cron', day_of_week='sun', hour=3)
def refresh_all_metrics():
    clips = db.query(Clips).filter(yt_video_id.isnot(None)).all()
    for clip in clips:
        try:
            stats = youtube_analytics.get_stats(clip.yt_video_id)
            db.insert(Metrics, clip_id=clip.id, 
                      collected_at=datetime.utcnow(), **stats)
        except QuotaExceeded:
            break
        except Exception as e:
            log.warning(f"metric fetch failed: {clip.yt_video_id}: {e}")
    
    maybe_update_weights()
```

#### Performance score
```python
def performance_score(m: MetricsRow) -> float:
    dur_norm = clamp(m.avg_view_percentage / 100, 0, 1)
    like_rate = min((m.likes or 0) / max(m.views or 1, 1) * 10, 1.0)
    comment_rate = min((m.comments or 0) / max(m.views or 1, 1) * 100, 1.0)
    view_norm = min(math.log1p(m.views or 0) / math.log(10_000), 1.0)
    
    return (0.50 * dur_norm
          + 0.25 * like_rate
          + 0.15 * comment_rate
          + 0.10 * view_norm)
```

#### 가중치 업데이트 알고리즘
```python
LEARNING_RATE = 0.15
WEIGHT_MIN = 0.05
WEIGHT_MAX = 0.60

def maybe_update_weights():
    clips_w_metric = db.query(
        Clips, ClipSignals, Metrics
    ).join(...).filter(
        Metrics.collected_at >= Clips.created_at + timedelta(days=7)
    ).all()
    
    # 마지막 업데이트 이후 +10개 누적 확인
    last_update = db.query(WeightHistory).order_by(...).first()
    if last_update.trigger_clip_count and \
       len(clips_w_metric) < last_update.trigger_clip_count + 10:
        return
    
    if len(clips_w_metric) < 10:
        return  # 최소 샘플 미달
    
    scored = [(c, s, performance_score(m)) for c, s, m in clips_w_metric]
    scored.sort(key=lambda x: -x[2])
    
    n = len(scored)
    top = scored[:max(n // 4, 3)]
    bot = scored[-max(n // 4, 3):]
    
    signal_fields = {
        'retention': 'retention_avg',
        'laughter':  'laughter_peak',
        'volume':    'volume_peak',
        'emotion':   'emotion_joy_peak',
        'tempo':     'tempo_change',
    }
    
    old_w = current_weights()
    new_w = {}
    for sig, field in signal_fields.items():
        top_vals = [getattr(s, field) for _, s, _ in top if getattr(s, field) is not None]
        bot_vals = [getattr(s, field) for _, s, _ in bot if getattr(s, field) is not None]
        if not top_vals or not bot_vals:
            new_w[sig] = old_w[sig]
            continue
        ratio = (mean(top_vals) + 1e-3) / (mean(bot_vals) + 1e-3)
        new_w[sig] = old_w[sig] * (1 + LEARNING_RATE * (ratio - 1))
    
    # Clamp + 정규화
    new_w = {k: clamp(v, WEIGHT_MIN, WEIGHT_MAX) for k, v in new_w.items()}
    total = sum(new_w.values())
    new_w = {k: v / total for k, v in new_w.items()}
    
    db.insert(WeightHistory,
              effective_from=datetime.utcnow(),
              w_retention=new_w['retention'],
              w_laughter=new_w['laughter'],
              w_volume=new_w['volume'],
              w_emotion=new_w['emotion'],
              w_tempo=new_w['tempo'],
              update_reason='auto_phase2',
              trigger_clip_count=n)
```

#### 조건 요약
- 지표 수집 7일 경과 클립만 대상 (지표 안정화 대기)
- 최소 10개 이상 누적 필요
- 마지막 업데이트 이후 +10개 추가 누적 시 재실행

### 7.5 Evolution 페이지 — 자동 인사이트

```python
def generate_insights() -> dict:
    first = WeightHistory.first()
    last  = WeightHistory.last()
    signals = ['retention', 'laughter', 'volume', 'emotion', 'tempo']
    
    biggest_grower = max(
        ((getattr(last, f'w_{s}') - getattr(first, f'w_{s}'), s) for s in signals)
    )
    
    recent_perf = avg_weekly_performance(weeks=[-4, -3, -2, -1])
    early_perf  = avg_weekly_performance(weeks=[0, 1, 2, 3])
    improvement = (recent_perf / early_perf - 1) * 100 if early_perf else 0
    
    return {
        'total_clips': count_clips(),
        'total_views': sum_views(),
        'total_feedbacks': count_preferences(),
        'biggest_grower': biggest_grower,
        'improvement_pct': improvement,
        'weight_updates': count_weight_updates(),
        'learning_status': '자기진화 작동 중 ✓' if improvement > 10 else '데이터 축적 중'
    }
```

---

## 8. 마일스톤 로드맵

3~3.5개월 예상. 순서는 **Phase 2 데이터 조기 축적**을 위해 업로드(M2) 를 scoring 강화(M3) 보다 앞에 배치.

### M0. 환경 셋업 (3~5일)
- 프로젝트 스캐폴드 (FastAPI + Next.js 15 + Docker Compose)
- Ollama + Qwen3.5-9B-Q4_K_M + EXAONE-3.5-7.8B-Q4_K_M 설치
- faster-whisper large-v3 + CUDA 동작 검증
- **VRAM 실측** → 순차 로드 전략 확정 (또는 Whisper turbo 대체)
- yt-dlp heatmap 추출 검증 (예능 영상 3~4개)
- MediaPipe 얼굴 검출 동작 확인
- Git repo, pre-commit, 기본 CI
- YouTube Data API OAuth 앱 등록 + 테스트 업로드

**Exit criteria**: 모든 외부 의존성 로컬에서 실행되고, 더미 영상 다운·업로드 성공.

### M1. MVP 엔드투엔드 (2~3주)
- `/edit` API + job 시스템
- yt-dlp 다운로드 (heatmap 포함)
- faster-whisper ASR
- Naive LLM scoring (자막만)
- ffmpeg 컷 + 경계 스냅
- MediaPipe face-track 9:16 reframe (Clean 템플릿만)
- Whisper 자막 burn-in
- WebSocket 진행률
- Next.js 기본 UI: URL → 진행률 → 결과 1개 → 다운로드
- 에러 처리 기본

**Exit criteria**: "URL 입력 → 60초 숏츠 mp4 출력" 성공.

### M2. YT 업로드 + History (1주)
**이유**: 여기 끝내야 실제 업로드 시작 → Phase 2 데이터 축적 개시.

- YouTube OAuth 플로우
- 업로드 모달 (제목 LLM 자동생성, `#Shorts` 자동)
- `google-api-python-client` 로 업로드
- `clips.yt_video_id` 저장
- History 페이지 기본 테이블 뷰
- YT 링크 이동 버튼

**Exit criteria**: 생성한 숏츠가 실제 YT 본인 채널에 Shorts로 업로드됨. **여기서부터 주간 업로드 시작.**

### M3. Scoring 강화 + 템플릿 4종 (2주)
**Scoring**:
- 5개 오디오 신호 추출 모듈 (librosa, panns_inference, Wav2Vec2-Emotion)
- heatmap 파싱 + 정규화
- `audio_interest_score(t)` 가중합
- 피크 추출
- LLM 프롬프트에 오디오 피크 통합
- 경계 스냅 로직

**템플릿**:
- JSON 스키마 + loader
- 4개 프리셋 파일 (clean/soft/bold/split)
- Layout·Caption·Animation 엔진 분기
- 템플릿 선택 UI + 재렌더 흐름
- 템플릿 미리보기 스틸 4장

**Exit criteria**: 5개 신호 반영 scoring, 4개 템플릿 전부 작동, 재렌더 30초 내.

### M4. Phase 1 선호 피드백 (3~4일)
- 👍/👎 버튼 UI
- `/preferences/record` API
- `preferences` 테이블
- Few-shot 선택 알고리즘 (다양성)
- LLM 프롬프트 주입
- 콜드스타트 처리

**Exit criteria**: 선호 기록이 다음 편집 결과에 관측 가능한 영향 (A/B 비교).

### M5. Phase 2 지표 수집 + 가중치 조정 (1.5~2주)
- YouTube Analytics API 연동
- `metrics` 테이블 + 시계열 insert
- APScheduler 주 1회 cron
- Settings 수동 새로고침 버튼
- `performance_score` 함수
- 가중치 업데이트 알고리즘 + safety guard
- `weight_history` 테이블
- Scoring 엔진이 DB에서 가중치 로드
- Settings > Advanced 수동 override UI

**Exit criteria**: 주기적 지표 수집, 10개 누적 시 가중치 자동 업데이트, 이력 기록.

### M6. Evolution 페이지 (4~5일)
- 상단 요약 카드 (자동 생성 인사이트)
- 차트 1: Stacked Area (가중치 변화)
- 차트 2: Line (주별 performance 평균)
- 차트 3: Grouped Bar (상위 vs 하위 신호 비교)

**Exit criteria**: 발표 스크린샷 가능한 완성도.

### M7. 폴리싱 + 발표 준비 (1~2주)
- Edit 페이지 Model 전환 드롭다운 (Qwen ↔ EXAONE)
- 다크모드 톤 정리
- 에러 처리 완성 (heatmap 없음·ASR 실패·LLM 타임아웃·업로드 실패)
- 취소 기능
- Docker Compose 원클릭 실행
- README + 데모 스크립트
- **발표 리허설**:
  - 실패 없는 영상 2~3개 선별 미리 테스트
  - Qwen vs EXAONE 비교 데모 준비
  - Evolution 최신 데이터 확인
  - 백업 스크린샷 준비

**Exit criteria**: 심사위원 앞 5분 라이브 데모 리허설 통과.

### 스코프 컷 계획 (시간 부족 시 희생 순서)

1. **M7 폴리싱 축소** — 기능은 유지, UI 디테일 감소
2. **Split 템플릿 삭제** — Clean/Soft/Bold 3개만 유지
3. **Evolution 차트 3 생략** — 차트 1+2만
4. **EXAONE 비교 삭제** — Qwen 단일 모델
5. **Phase 2 자동 cron 삭제** — 수동 버튼만

---

## 9. 리스크 및 완화

| # | 리스크 | 영향 | 가능성 | 완화책 |
|---|---|---|---|---|
| R1 | Whisper + LLM 동시 VRAM 부족 | 높음 | 중 | 순차 로드, 불가 시 Whisper turbo (M0에서 실측) |
| R2 | 유튜브 heatmap 미제공 영상 처리 | 중 | 낮음 | `w_retention=0` 폴백 + UI 안내 |
| R3 | YouTube API quota 초과 | 낮음 | 낮음 | 본인 채널만 조회, quota 10,000 units/day 충분 |
| R4 | Phase 2 데이터 부족 (10개 미달) | 중 | 중 | M2 조기 완성 + 주간 업로드 강제 리듬 |
| R5 | 웃음 탐지 오탐/미탐 | 중 | 중 | panns threshold 튜닝 + 볼륨 교차검증 |
| R6 | MediaPipe 얼굴 검출 실패 | 중 | 중 | center crop 폴백, cut detection으로 리셋 |
| R7 | LLM JSON 포맷 이탈 | 중 | 중 | pydantic validation + retry (최대 2회) + fallback parser |
| R8 | yt-dlp heatmap 필드명 변동 | 중 | 낮음 | yt-dlp 버전 pin + 방어적 파싱 |
| R9 | 순차 로드로 인한 응답 지연 | 낮음 | 높음 | UI 진행률로 UX 보완, 배치 처리 |
| R10 | EXAONE 비상업 라이선스 | 낮음 | 확정 | 연구·학술 목적 용도 명시, 상업 전환 시 모델 교체 경로 명문화 |

---

## 10. 향후 확장 (Out of Scope, 참고용)

캡스톤 범위 외, 발표 Q&A 대비용.

- **다장르 확장**: 장르 자동 감지 + 장르별 가중치 프리셋 (게임 스트림·브이로그·리뷰)
- **커스텀 템플릿 생성기**: UI로 폰트·색상·레이아웃 드래그 편집
- **다중 구간 컴필레이션**: 한 숏츠 안에 3~5개 짧은 구간 이어붙이기
- **LoRA 파인튜닝 (Phase 3)**: 데이터 100개 이상 시 Qwen3.5-7B LoRA 학습
- **썸네일 자동 생성**: 감정 피크 프레임 + LLM이 제목 오버레이
- **다중 계정**: 여러 YT 채널 관리
- **커뮤니티 템플릿 공유**: 사용자끼리 JSON 템플릿 공유
- **실시간 편집 (스트림)**: 라이브 스트림을 실시간으로 모니터하며 숏츠 자동 생성
- **음성 TTS 내레이션**: 원본에 AI 해설 더빙
- **이중언어 자막**: 원본 한국어 + 자동 영문 번역 병기

---

## 11. 부록

### 11.1 주요 의존성 버전 (M0에서 고정)

```
python>=3.11
fastapi>=0.110
faster-whisper>=1.0
ollama>=0.1.40
yt-dlp>=2026.1
mediapipe>=0.10
librosa>=0.10
panns-inference>=0.1
torch>=2.3 (CUDA 12.x)
transformers>=4.40
google-api-python-client>=2.100
google-auth-oauthlib>=1.2
moviepy>=1.0.3
apscheduler>=3.10

# frontend
next==15.x
react==19.x
tailwindcss==3.x
shadcn-ui (최신)
recharts==2.x
framer-motion==11.x
```

### 11.2 디렉토리 구조 (생성 시점)

```
capstone/
├── docker-compose.yml
├── README.md
├── .env.example
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/         # FastAPI 라우터
│   │   ├── pipeline/    # 다운로드·ASR·scoring·render
│   │   ├── templates/   # JSON 템플릿 파일
│   │   ├── models/      # Pydantic + SQLAlchemy
│   │   ├── services/    # YT API·Ollama·etc
│   │   └── db/
│   ├── migrations/
│   ├── tests/
│   ├── fonts/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── app/             # Next.js App Router
│   ├── components/
│   ├── lib/
│   ├── public/
│   ├── package.json
│   └── Dockerfile
├── data/                # .gitignore
│   ├── videos/
│   ├── clips/
│   ├── models/
│   └── k-shorts.db
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-21-korean-shorts-autoeditor-design.md  ← 본 문서
```

### 11.3 용어 정의

- **heatmap / retention**: YouTube "Most Replayed" 데이터. yt-dlp info.json 의 `heatmap` 필드.
- **scoring 가중치**: 5개 오디오 신호 통합 시 사용되는 `w_*` 값. Phase 2로 자동 조정.
- **performance_score**: Phase 2에서 각 클립 성과 평가용 스칼라. scoring 가중치와 별개.
- **snap**: 구간 경계를 단어·침묵 지점으로 조정.
- **cold start**: 피드백 데이터 누적 전 초기 상태.
