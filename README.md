# AI 전화상담 Voice Clone Demo

고객이 자신의 목소리를 녹음하면, Qwen3-TTS가 그 목소리로 고객응대 스크립트를 읽어주는 체험 데모입니다.

## 구조

```
qwen-tts-demo/
├── server.py           # FastAPI 백엔드 (voice cloning API)
├── requirements.txt    # Python 의존성
├── static/
│   └── index.html     # 프론트엔드 (녹음 → 생성 → 재생)
├── temp_audio/        # 업로드된 레퍼런스 오디오 (자동 생성)
└── output_audio/      # 생성된 TTS 오디오 (자동 생성)
```

## 실행 방법

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

GPU가 있으면 Qwen3-TTS 로컬 모델이 자동으로 사용됩니다.  
없으면 DashScope API 또는 mock 모드로 동작합니다.

### 2. 환경변수 설정 (DashScope API 사용 시)

```bash
export DASHSCOPE_API_KEY="your-dashscope-api-key"
```

### 3. 서버 실행

```bash
python server.py
```

브라우저에서 http://localhost:8000 접속

## Voice Cloning 우선순위

1. **로컬 Qwen3-TTS** (GPU 필요, 최고 품질)
2. **DashScope API** (Alibaba Cloud, DASHSCOPE_API_KEY 필요)
3. **Mock 모드** (개발/테스트용, 레퍼런스 오디오를 그대로 재생)

## 고객응대 스크립트

| key | 내용 |
|-----|------|
| greeting | 첫 인사 |
| inquiry | 문의 접수 |
| product | 서비스 안내 |
| closing | 마무리 인사 |
| full | 전체 시나리오 (기본값) |
