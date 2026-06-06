"""
Qwen3-TTS Voice Clone Demo Server
고객 목소리로 AI 전화상담 데모
"""
import os
import uuid
import tempfile
import asyncio
from pathlib import Path


def _load_dotenv():
    """의존성 없이 같은 폴더의 .env 파일을 환경변수로 로드"""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AI 전화상담 Voice Clone Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("temp_audio")
OUTPUT_DIR = Path("output_audio")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# 미리 작성된 고객응대 스크립트
SCRIPTS = {
    "greeting": "안녕하세요, 고객님! 저는 AI 상담 어시스턴트입니다. 무엇을 도와드릴까요?",
    "inquiry": "네, 고객님. 문의 주신 내용 잘 접수했습니다. 잠시만 기다려 주시면 바로 확인해 드리겠습니다.",
    "product": "저희 서비스는 24시간 연중무휴로 운영되고 있으며, 언제든지 편하게 문의해 주세요. 빠르고 정확하게 도와드리겠습니다.",
    "closing": "이용해 주셔서 감사합니다, 고객님. 더 궁금하신 점이 있으시면 언제든지 다시 연락해 주세요. 좋은 하루 되세요!",
    "full": (
        "안녕하세요, 고객님! 저는 AI 전화상담 어시스턴트입니다. "
        "문의 주신 내용 잘 접수했습니다. "
        "저희 서비스는 365일 24시간 운영되며, "
        "고객님의 소중한 시간을 아껴드리기 위해 최선을 다하고 있습니다. "
        "궁금하신 점이 있으시면 언제든지 말씀해 주세요. "
        "더 도움이 필요하신 사항이 있으신가요?"
    ),
}


def convert_to_wav(input_path: str, output_path: str) -> bool:
    """webm/ogg → wav 변환 (ffmpeg 사용)"""
    try:
        import subprocess
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", input_path, "-ar", "22050", "-ac", "1", output_path],
            capture_output=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"[CONV] ffmpeg 변환 실패: {e}")
        return False


def clone_voice_elevenlabs(reference_audio_path: str, target_text: str, output_path: str) -> bool:
    """ElevenLabs Instant Voice Cloning API"""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("[EL] ELEVENLABS_API_KEY 환경변수가 없습니다.")
        return False
    try:
        import requests

        # webm → wav 변환 (ElevenLabs는 wav/mp3 선호)
        wav_path = reference_audio_path.replace(".webm", "_converted.wav")
        if reference_audio_path.endswith(".webm") or reference_audio_path.endswith(".ogg"):
            if not convert_to_wav(reference_audio_path, wav_path):
                wav_path = reference_audio_path  # 변환 실패시 원본 사용
        else:
            wav_path = reference_audio_path

        print("[EL] 목소리 등록 중...")
        # 1. Instant Voice Clone 생성
        with open(wav_path, "rb") as f:
            clone_resp = requests.post(
                "https://api.elevenlabs.io/v1/voices/add",
                headers={"xi-api-key": api_key},
                data={
                    "name": f"demo_voice_{uuid.uuid4().hex[:6]}",
                    "description": "AI 전화상담 데모용 임시 목소리",
                },
                files={"files": (Path(wav_path).name, f, "audio/wav")},
                timeout=60,
            )

        if clone_resp.status_code != 200:
            print(f"[EL] 목소리 등록 실패: {clone_resp.status_code} {clone_resp.text}")
            return False

        voice_id = clone_resp.json()["voice_id"]
        print(f"[EL] 목소리 등록 완료: {voice_id}")

        # 2. 등록된 목소리로 TTS 생성
        tts_resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json",
            },
            json={
                "text": target_text,
                "model_id": "eleven_multilingual_v2",
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.85,
                    "style": 0.2,
                    "use_speaker_boost": True,
                },
            },
            timeout=60,
        )

        if tts_resp.status_code != 200:
            print(f"[EL] TTS 생성 실패: {tts_resp.status_code} {tts_resp.text}")
            # 사용한 임시 목소리 삭제
            requests.delete(
                f"https://api.elevenlabs.io/v1/voices/{voice_id}",
                headers={"xi-api-key": api_key},
            )
            return False

        # mp3로 저장 (ElevenLabs 기본 출력)
        mp3_path = str(output_path).replace(".wav", ".mp3")
        with open(mp3_path, "wb") as f:
            f.write(tts_resp.content)

        # output_path를 mp3로 교체 (get_audio에서 탐색)
        Path(output_path).write_bytes(tts_resp.content)

        print(f"[EL] TTS 생성 완료")

        # 임시 목소리 삭제 (크레딧 절약)
        requests.delete(
            f"https://api.elevenlabs.io/v1/voices/{voice_id}",
            headers={"xi-api-key": api_key},
        )
        return True

    except Exception as e:
        print(f"[EL] ElevenLabs 오류: {e}")
        return False


def clone_voice_mock(reference_audio_path: str, target_text: str, output_path: str) -> bool:
    """개발/테스트용 mock"""
    import shutil
    shutil.copy(reference_audio_path, output_path)
    return True


@app.post("/api/synthesize")
async def synthesize(
    audio: UploadFile = File(...),
    reference_text: str = Form(...),
    script_key: str = Form(default="full"),
    custom_text: str = Form(default=""),
):
    """
    고객 목소리(reference_audio) + 레퍼런스 텍스트 → 스크립트를 고객 목소리로 합성
    script_key="custom" 이면 custom_text 를 그대로 합성
    """
    if script_key == "custom":
        target_text = custom_text.strip()
        if not target_text:
            raise HTTPException(status_code=400, detail="직접 입력 텍스트가 비어 있습니다.")
        if len(target_text) > 1000:
            raise HTTPException(status_code=400, detail="텍스트는 최대 1000자까지 입력할 수 있습니다.")
    else:
        if script_key not in SCRIPTS:
            raise HTTPException(
                status_code=400,
                detail=f"script_key must be one of: {list(SCRIPTS.keys()) + ['custom']}",
            )
        target_text = SCRIPTS[script_key]

    session_id = str(uuid.uuid4())[:8]

    # 업로드된 오디오 저장
    ext = Path(audio.filename).suffix if audio.filename else ".webm"
    ref_path = UPLOAD_DIR / f"ref_{session_id}{ext}"
    content = await audio.read()
    with open(ref_path, "wb") as f:
        f.write(content)

    output_path = OUTPUT_DIR / f"out_{session_id}.wav"

    # Voice cloning 시도 (우선순위: elevenlabs → mock)
    success = clone_voice_elevenlabs(str(ref_path), target_text, str(output_path))
    if not success:
        success = clone_voice_mock(str(ref_path), target_text, str(output_path))

    if not success or not output_path.exists():
        raise HTTPException(status_code=500, detail="음성 합성에 실패했습니다.")

    return JSONResponse({
        "session_id": session_id,
        "audio_url": f"/api/audio/{session_id}",
        "script": target_text,
    })


@app.get("/api/audio/{session_id}")
async def get_audio(session_id: str):
    # wav 우선, 없으면 webm
    for ext in [".wav", ".webm", ".mp3"]:
        path = OUTPUT_DIR / f"out_{session_id}{ext}"
        if path.exists():
            return FileResponse(path, media_type="audio/wav")
    raise HTTPException(status_code=404, detail="오디오 파일을 찾을 수 없습니다.")


@app.get("/api/scripts")
async def get_scripts():
    return SCRIPTS


# 정적 파일 (프론트엔드)
app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
