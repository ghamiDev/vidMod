import os
import streamlit as st
import tempfile
import random
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    vfx
)
import cv2
import numpy as np

st.set_page_config(page_title="Acak Potongan Video", layout="wide")
st.title("🎞️ Aplikasi Acak Potongan Video + Upscale 1080 + Mute Audio")

# Folder penyimpanan file sementara
PROJECT_TEMP_DIR = "videos_temp"
os.makedirs(PROJECT_TEMP_DIR, exist_ok=True)

def create_temp_file(extension=".mp4"):
    rand = str(random.randint(100000, 999999))
    return os.path.join(PROJECT_TEMP_DIR, f"temp_{rand}{extension}")

# ==========================================================
# CINEMATIC EFFECT (vignette lembut)
# ==========================================================
def cinematic_effect(frame):
    img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # Brightness & Contrast
    img = cv2.convertScaleAbs(img, alpha=1.1, beta=10)

    rows, cols = img.shape[:2]

    # Gunakan numpy untuk menghindari peringatan deprecation
    kernel_x = cv2.getGaussianKernel(cols, 400)
    kernel_y = cv2.getGaussianKernel(rows, 400)
    mask = kernel_y @ kernel_x.T
    mask = 0.5 + (mask / mask.max()) * 0.5

    mask = mask.astype("float32")

    vignette = img.copy()
    vignette = (vignette * mask[:, :, None]).astype("uint8")

    return cv2.cvtColor(vignette, cv2.COLOR_BGR2RGB)


# ==========================================================
# EKSTRAK AUDIO
# ==========================================================
def extract_audio(video_path):
    clip = VideoFileClip(video_path)
    audio_path = create_temp_file(".mp3")

    # MoviePy terbaru perlu param extra
    clip.audio.write_audiofile(
        audio_path,
        fps=44100,
        bitrate="192k",
        ffmpeg_params=["-preset", "fast"]
    )
    clip.close()
    return audio_path


# ==========================================================
# HAPUS AUDIO (MUTE)
# ==========================================================
def mute_video(video_path):
    clip = VideoFileClip(video_path)
    muted_path = create_temp_file(".mp4")

    clip.without_audio().write_videofile(
        muted_path,
        codec="libx264",
        audio=False,
        ffmpeg_params=["-preset", "medium"]
    )
    clip.close()
    return muted_path


# ==========================================================
# MAIN APP
# ==========================================================
uploaded_video = st.file_uploader("Upload Video", type=["mp4", "mov", "avi"])

if uploaded_video:
    st.video(uploaded_video)

    temp_input = create_temp_file(".mp4")
    with open(temp_input, "wb") as f:
        f.write(uploaded_video.read())

    clip = VideoFileClip(temp_input)
    duration = clip.duration

    st.info(f"Durasi video: **{duration:.2f} detik**")

    if st.button("Proses Acak Video"):
        st.warning("Memproses video, mohon tunggu...")

        progress = st.progress(0)
        status = st.empty()

        # ==========================================================
        # 1️⃣ EKSTRAK AUDIO
        # ==========================================================
        status.text("Mengekstrak audio...")
        audio_original = extract_audio(temp_input)
        progress.progress(0.1)

        # ==========================================================
        # 2️⃣ POTONG VIDEO PER 3 DETIK + EFEK + CINEMATIC
        # ==========================================================
        status.text("Memotong video per 3 detik...")

        part_length = 3
        clips = []
        start = 0
        index = 0
        total_parts = int(duration / part_length) + 1

        while start < duration:
            end = min(start + part_length, duration)

            sub = clip.subclip(start, end)
            sub = sub.fl_image(cinematic_effect)

            effect = random.choice(["normal", "slow", "fast", "reverse", "mirror"])

            match effect:
                case "slow":
                    sub = sub.fx(vfx.speedx, 0.9)
                case "fast":
                    sub = sub.fx(vfx.speedx, 1.1)
                case "reverse":
                    sub = sub.fx(vfx.time_mirror)
                case "mirror":
                    sub = sub.fx(vfx.mirror_x)

            if index > 0:
                sub = sub.fx(vfx.fadein, 0.15)

            clips.append(sub)

            index += 1
            progress.progress(0.1 + (index / total_parts) * 0.4)
            status.text(f"Proses part {index}/{total_parts} (Efek: {effect})")

            start += part_length

        progress.progress(0.5)

        # ==========================================================
        # 3️⃣ ACAK URUTAN
        # ==========================================================
        status.text("Mengacak urutan potongan...")
        random.shuffle(clips)
        progress.progress(0.55)

        # ==========================================================
        # 4️⃣ GABUNGKAN VIDEO
        # ==========================================================
        status.text("Menggabungkan video...")
        final_clip = concatenate_videoclips(clips, method="compose")
        progress.progress(0.65)

        # ==========================================================
        # 5️⃣ UPSCALE KE 1080p PORTRAIT
        # ==========================================================
        status.text("Upscale ke 1080p (portrait)...")

        w, h = final_clip.size
        target_h = 1920
        scale = target_h / h
        target_w = int(w * scale)

        final_clip = final_clip.resize((target_w, target_h))
        progress.progress(0.75)

        # ==========================================================
        # 6️⃣ EXPORT TANPA AUDIO
        # ==========================================================
        status.text("Export video mute...")

        output_path = create_temp_file(".mp4")

        final_clip.write_videofile(
            output_path,
            codec="libx264",
            audio=False,
            ffmpeg_params=["-preset", "medium"]
        )

        progress.progress(1.0)
        status.text("Selesai!")

        st.success("Video selesai diproses!")
        st.video(output_path)

        with open(output_path, "rb") as fp:
            st.download_button(
                label="Download Video Final",
                data=fp,
                file_name="video_final_1080p_muted.mp4",
                mime="video/mp4"
            )
