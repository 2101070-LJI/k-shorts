# M0 로컬 설치 가이드 & 실측 체크리스트

이 문서는 K-Shorts 스캐폴드 위에서 M1 작업을 시작하기 전에 **사용자가 직접** 해야 하는 환경 셋업을 정리한 것이다. 모든 단계는 Windows 11 + RTX 3070 8GB 기준.

## 1. NVIDIA 드라이버 / CUDA

```powershell
nvidia-smi
```
- CUDA 12.x 이상이면 OK. 버전 낮으면 최신 Studio Driver 설치.
- `torch` 설치 시 `--index-url https://download.pytorch.org/whl/cu121` 사용.

## 2. Ollama 설치 & 모델 pull

1. https://ollama.com/download/windows 에서 설치.
2. 서비스 자동 시작 확인 (`http://localhost:11434`).
3. 모델 pull:
   ```powershell
   ollama search qwen                # 사용 가능한 태그 확인
   ollama pull qwen3:8b              # 기본값
   # 더 큰 모델 (qwen3:14b 등) 이나 Qwen3.5 가 로컬에 있으면 .env 의 DEFAULT_LLM_MODEL 에 지정
   # EXAONE 은 커뮤니티 변환 태그 확인 후 pull
   ```
4. 동작 테스트:
   ```powershell
   ollama run qwen3:8b "한 줄로 자기소개"
   ```

## 3. Python 3.11 + 백엔드 의존성

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip

# Torch (CUDA 12.1 휠)
pip install torch==2.3.* --index-url https://download.pytorch.org/whl/cu121

# 나머지
pip install -e .
pip install -e ".[dev]"
```

### 동작 확인

```powershell
pytest tests/ -q             # 템플릿 로더·헬스 라우터 통과 확인
uvicorn app.main:app --reload --port 8000
curl http://localhost:8000/health
curl http://localhost:8000/templates
```

## 4. Node 20 + 프론트엔드

```powershell
cd frontend
npm install --legacy-peer-deps
npm run dev
```
브라우저에서 `http://localhost:3000` → "API 연결 확인 중…" 버튼이 성공으로 바뀌면 통합 OK.

## 5. YouTube Data API OAuth 등록

1. https://console.cloud.google.com/ 에서 새 프로젝트 생성.
2. **YouTube Data API v3** + **YouTube Analytics API** 활성화.
3. **OAuth 동의 화면** → 앱 등록 (테스트 사용자에 본인 이메일 추가).
4. **사용자 인증 정보** → OAuth 클라이언트 ID (데스크탑 앱).
5. 다운로드한 `client_secret_*.json` 을 `backend/client_secret.json` 으로 저장.
6. M2에서 첫 업로드 시 브라우저 인증 → `backend/token.json` 자동 생성.

## 6. 폰트 배치

`backend/fonts/` 아래 다음 파일을 배치 (라이선스 때문에 repo 포함 지양):

- `Pretendard-Medium.otf` — https://github.com/orioncactus/pretendard
- `NanumMyeongjo-Regular.ttf` — 네이버 나눔 폰트
- `NanumSquare_acB.ttf` — 네이버 나눔 폰트

## 7. VRAM 실측 (M0 Exit Criteria)

아래 시나리오를 직접 돌려보고 수치를 기록. 결과에 따라 전략 확정.

| 테스트 | 명령 | 목표 |
|---|---|---|
| 1. Ollama idle | `nvidia-smi` | baseline 확인 |
| 2. Ollama + Qwen 로드 | `ollama run qwen2.5:7b-instruct-q4_K_M "hi"` → 유지 | 약 7GB |
| 3. Whisper large-v3 단독 | `python -c "from faster_whisper import WhisperModel; m = WhisperModel('large-v3', device='cuda', compute_type='float16'); input()"` | 약 2.5GB |
| 4. 동시 실행 (2 + 3) | 두 창 동시 | OOM? 기록 |

**판정**:
- 동시 거주 가능 → 파이프라인 병렬화 가능
- OOM 발생 → 순차 로드 (스펙 2.5) 또는 Whisper `large-v3-turbo` (약 1.5GB) 로 다운그레이드

측정 결과는 `docs/M0_MEASUREMENTS.md` 에 기록 (M1 시작 시 참고).

## 8. yt-dlp heatmap 검증

```powershell
yt-dlp --dump-json "https://www.youtube.com/watch?v=<인기_예능_URL>" | python -c "import json,sys; d=json.loads(sys.stdin.read()); print('heatmap:', len(d.get('heatmap') or []), '포인트')"
```
- 인기 예능 3~4개 돌려서 `heatmap` 필드 존재 확인.
- 없으면 해당 영상은 `w_retention=0` 폴백 경로로 간다.

## 9. MediaPipe Face Landmarker 샘플

```python
# tools/check_mediapipe.py (만들어서 한 번 돌리기)
import cv2, mediapipe as mp
from mediapipe.tasks import python as mpp
from mediapipe.tasks.python import vision

base = mpp.BaseOptions(model_asset_path='face_landmarker.task')
# https://developers.google.com/mediapipe/solutions/vision/face_landmarker 에서 다운
opts = vision.FaceLandmarkerOptions(base_options=base, num_faces=2)
detector = vision.FaceLandmarker.create_from_options(opts)
# 예능 썸네일·샘플 프레임 1장 넣고 결과 출력
```
- 얼굴 1~2개 검출되면 OK.

## Exit Criteria

- [ ] `pytest tests/ -q` 통과
- [ ] `/health`, `/templates` 엔드포인트 200 반환
- [ ] 프론트엔드 `/` 에서 "API 연결 OK" 확인
- [ ] VRAM 실측 결과 기록
- [ ] Ollama + 1개 이상 한국어 모델 로드 성공
- [ ] yt-dlp 로 예능 샘플 3개 다운·heatmap 확인
- [ ] YouTube OAuth `client_secret.json` 배치

여기까지 완료되면 M1 (MVP 파이프라인) 착수.
