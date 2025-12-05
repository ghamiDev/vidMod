import streamlit as st
import tempfile
import random
import os
from moviepy.editor import (
    VideoFileClip,
    concatenate_videoclips,
    vfx
)
from PIL import Image
import cv2
import numpy as np

st.set_page_config(page_title="Acak Potongan Video", layout="wide")
st.title("🎞️ Aplikasi Acak Potongan Video + Upscale 1080 + Mute Audio")

# ==========================================================
# CINEMATIC EFFECT (vignette lembut)
# ==========================================================
def cinematic_effect(frame):
    img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # Brightness & Contrast
    alpha = 1.1
    beta = 10
    img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

    # Soft Vignette
    rows, cols = img.shape[:2]
    kernel_x = cv2.getGaussianKernel(cols, 400)
    kernel_y = cv2.getGaussianKernel(rows, 400)
    kernel = kernel_y * kernel_x.T

    mask = kernel / kernel.max()
    mask = 0.5 + (mask * 0.5)

    vignette = img.copy()
    for i in range(3):
        vignette[:, :, i] = vignette[:, :, i] * mask

    return cv2.cvtColor(vignette, cv2.COLOR_BGR2RGB)


# ==========================================================
# EKSTRAK AUDIO
# ==========================================================
def extract_audio(video_path):
    clip = VideoFileClip(video_path)
    audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3").name
    clip.audio.write_audiofile(audio_path)
    clip.close()
    return audio_path


# ==========================================================
# HAPUS AUDIO (MUTE)
# ==========================================================
def mute_video(video_path):
    clip = VideoFileClip(video_path)
    muted_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
    muted = clip.without_audio()
    muted.write_videofile(muted_path, codec="libx264", audio=False)
    clip.close()
    return muted_path


# ==========================================================
# MAIN
# ==========================================================
uploaded_video = st.file_uploader("Upload Video", type=["mp4", "mov", "avi"])

if uploaded_video:
    st.video(uploaded_video)

    temp_input = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_input.write(uploaded_video.read())
    temp_input.close()

    clip = VideoFileClip(temp_input.name)
    duration = clip.duration
    st.info(f"Durasi video: **{duration:.2f} detik**")

    # Tombol proses
    if st.button("Proses Acak Video"):
        st.warning("Memproses video, mohon tunggu...")

        # =================== PROGRESS BAR ===================
        progress = st.progress(0)
        status = st.empty()

        # ==========================================================
        # 1️⃣ EKSTRAK AUDIO
        # ==========================================================
        status.text("Mengekstrak audio...")
        audio_original = extract_audio(temp_input.name)
        progress.progress(0.1)

        # ==========================================================
        # 2️⃣ POTONG VIDEO PER 3 DETIK + EFEK ACAK + CINEMATIC
        # ==========================================================
        status.text("Memotong video per 3 detik...")

        part_length = 3
        clips = []
        start = 0
        part_index = 0
        total_parts = int(duration / part_length) + 1

        while start < duration:
            end = min(start + part_length, duration)

            subclip = clip.subclip(start, end)
            subclip = subclip.fl_image(cinematic_effect)

            # Efek acak
            effects = ["normal", "slow", "fast", "reverse", "mirror"]
            chosen = random.choice(effects)

            if chosen == "slow":
                subclip = subclip.fx(vfx.speedx, 0.9)
            elif chosen == "fast":
                subclip = subclip.fx(vfx.speedx, 1.1)
            elif chosen == "reverse":
                subclip = subclip.fx(vfx.time_mirror)
            elif chosen == "mirror":
                subclip = subclip.fx(vfx.mirror_x)

            if part_index != 0:
                subclip = subclip.fx(vfx.fadein, 0.15)  # 150ms transisi halus

            clips.append(subclip)

            part_index += 1
            progress.progress(0.1 + (part_index / total_parts) * 0.4)
            status.text(f"Proses part {part_index}/{total_parts} (Efek: {chosen})")

            start += part_length

        status.text("Potongan selesai.")
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
        # final_clip = concatenate_videoclips(final_list, method="compose")
        progress.progress(0.65)

        # ==========================================================
        # 5️⃣ UPSCALE KE 1080P VERTICAL (9:16)
        # ==========================================================
        status.text("Upscale ke 1080p (portrait)...")

        original_w, original_h = final_clip.size
        target_h = 1920
        scale = target_h / original_h
        target_w = int(original_w * scale)

        final_clip = final_clip.resize((target_w, target_h))
        progress.progress(0.75)

        # ==========================================================
        # 6️⃣ HAPUS AUDIO (MUTE)
        # ==========================================================
        status.text("Menghapus audio dari video (mute)...")
        muted_video_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name
        final_clip.write_videofile(muted_video_path, codec="libx264", audio=False)
        progress.progress(0.9)

        # ==========================================================
        # DONE
        # ==========================================================
        status.text("Selesai!")
        progress.progress(1.0)

        st.success("Video selesai diproses!")
        st.video(muted_video_path)

        with open(muted_video_path, "rb") as fp:
            st.download_button(
                label="Download Video Final",
                data=fp,
                file_name="video_final_1080p_muted.mp4",
                mime="video/mp4"
            )
