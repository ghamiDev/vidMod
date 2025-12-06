import os
import streamlit as st
import tempfile
import random
from moviepy.editor import VideoFileClip, ImageClip, concatenate_videoclips, vfx
import cv2
import numpy as np
import time

st.set_page_config(page_title="VidMod", layout="wide")

# ==========================
# LOGIN SYSTEM (STABIL + AUTO-LOGOUT 10 MENIT)
# ==========================
VALID_USERNAME = "demitri"
VALID_PASSWORD = "12345..DMT"
AUTO_LOGOUT_SECONDS = 600  # 10 menit

# init session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = None
if "last_activity" not in st.session_state:
    st.session_state.last_activity = time.time()
if "user_temp_dir" not in st.session_state:
    st.session_state.user_temp_dir = tempfile.mkdtemp()

def update_activity():
    st.session_state.last_activity = time.time()

def auto_logout_check():
    if st.session_state.logged_in:
        if time.time() - st.session_state.last_activity > AUTO_LOGOUT_SECONDS:
            st.session_state.logged_in = False
            st.session_state.username = None
            st.warning("⏳ Otomatis logout karena 10 menit tidak ada aktivitas.")
            st.stop()

def login_screen():
    st.subheader("🔐 Login untuk Mengakses VidMod")
    update_activity()
    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    if st.button("Login", on_click=update_activity):
        if username == VALID_USERNAME and password == VALID_PASSWORD:
            st.session_state.logged_in = True
            st.session_state.username = username
            st.success("Login berhasil!")
            st.rerun()
        else:
            st.error("Username / password salah!")
            st.stop()

def do_logout():
    # clear relevant keys but keep temp dir if needed
    keys = list(st.session_state.keys())
    for k in keys:
        # keep user_temp_dir so temporary files can be managed until cleaned by UI if desired
        if k not in ("user_temp_dir",):
            del st.session_state[k]
    # ensure defaults
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.last_activity = time.time()
    st.success("Berhasil logout.")
    st.rerun()

# Run auto-logout check & show login if needed
auto_logout_check()
if not st.session_state.logged_in:
    login_screen()
    st.stop()

# Sidebar user info + logout
st.sidebar.success(f"Login sebagai: {st.session_state.username}")
if st.sidebar.button("Logout"):
    do_logout()

update_activity()  # mark activity on page load/interact

# ==========================================================
# APP TITLE
# ==========================================================
st.title("🎞️ Vid-Mod Optimized Stable Edition 🎞️")

# ==========================================================
# TEMP DIR helper
# ==========================================================
USER_TEMP = st.session_state.user_temp_dir

def user_temp_file(ext=".mp4", label="temp"):
    rand = random.randint(100000, 999999)
    return os.path.join(USER_TEMP, f"{label}_{rand}{ext}")

# ==========================================================
# EFFECT: CINEMATIC (ULTRA LIGHT)
# ==========================================================
def cinematic_effect(frame):
    # pastikan frame dalam uint8
    if frame.dtype != np.uint8:
        frame = np.clip(frame, 0, 255).astype("uint8")

    img = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

    # exposure
    img = cv2.convertScaleAbs(img, alpha=1.04, beta=6)

    # vignette
    rows, cols = img.shape[:2]
    kernel_x = cv2.getGaussianKernel(cols, 420)
    kernel_y = cv2.getGaussianKernel(rows, 420)
    mask = kernel_y @ kernel_x.T
    mask = (mask / mask.max()) * 0.55 + 0.45

    vignette = (img * mask[:, :, None]).astype("uint8")
    return cv2.cvtColor(vignette, cv2.COLOR_BGR2RGB)


# ==========================================================
# FORCE 9:16 (1080x1920) helper
# ==========================================================
def force_9_16(clip, target_w=1080, target_h=1920):
    # scale to target height then center crop/pad to target width
    h = clip.h
    if h == 0:
        return clip
    scale = target_h / h
    new_w = int(clip.w * scale)
    resized = clip.resize((new_w, target_h))
    if new_w > target_w:
        crop_x = (new_w - target_w) // 2
        final = resized.crop(x1=crop_x, y1=0, x2=crop_x + target_w, y2=target_h)
    else:
        pad_left = (target_w - new_w) // 2
        pad_right = target_w - new_w - pad_left
        final = resized.margin(left=pad_left, right=pad_right, top=0, bottom=0, color=(0,0,0))
    return final.set_position(("center","center"))

# ==========================================================
# AUDIO EXTRACT
# ==========================================================
def extract_audio(video_path):
    clip = VideoFileClip(video_path, audio=True)
    audio_path = user_temp_file(".mp3", "audio")
    clip.audio.write_audiofile(audio_path, fps=44100, bitrate="192k")
    clip.close()
    return audio_path

# ==========================================================
# INSERT CLIP
# ==========================================================
def load_insert_clip(file):
    if not file:
        return None
    filename = file.name.lower()
    data = file.read()
    if filename.endswith((".jpg", ".jpeg", ".png")):
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        # normalisasi image jadi uint8
        if img.dtype != np.uint8:
            img = np.clip(img, 0, 255).astype("uint8")

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        clip = ImageClip(img).set_duration(2)
        clip = clip.fx(vfx.fadein, 0.25).fx(vfx.fadeout, 0.25)
        clip = force_9_16(clip)
        return clip
    if filename.endswith((".mp4", ".mov", ".avi")):
        temp = user_temp_file(".mp4", "insert")
        with open(temp, "wb") as f:
            f.write(data)
        vid = VideoFileClip(temp)
        vid = vid.fx(vfx.fadein, 0.25).fx(vfx.fadeout, 0.25)
        vid = force_9_16(vid)
        return vid
    return None

# ==========================================================
# SAFE ZOOM — RASIO SELALU 9:16
# ==========================================================
def safe_zoom(clip, zoom=1.05):
    def _zoom(frame):
        if frame.dtype != np.uint8:
            frame = np.clip(frame, 0, 255).astype("uint8")
        h, w = frame.shape[:2]
        nw = int(w / zoom)
        nh = int(h / zoom)
        x1 = (w - nw) // 2
        y1 = (h - nh) // 2
        cropped = frame[y1:y1+nh, x1:x1+nw]
        return cv2.resize(cropped, (w, h))
    return clip.fl_image(_zoom)

# ==========================================================
# MAIN APP UI
# ==========================================================
uploaded_video = st.file_uploader("Upload Video Utama", type=["mp4", "mov", "avi"])
insert_file = st.file_uploader("Upload Image / Video Tambahan (opsional)")
# load insert clip if provided
insert_clip = load_insert_clip(insert_file) if insert_file else None

if uploaded_video:
    update_activity()
    temp_input = user_temp_file(".mp4", "input")
    with open(temp_input, "wb") as f:
        f.write(uploaded_video.read())

    clip = None
    final_out = None
    try:
        clip = VideoFileClip(temp_input)
        # force input to 9:16 early to avoid misalignment
        clip = force_9_16(clip)
        duration = clip.duration
        fps = clip.fps or 30
        st.info(f"Durasi video: **{duration:.2f} detik** — FPS: {fps}")

        if st.button("Proses Video", on_click=update_activity):
            progress = st.progress(0)
            status = st.empty()
            # extract audio
            status.text("Extract audio...")
            audio_original = extract_audio(temp_input)
            progress.progress(0.05)

            # cut into parts
            status.text("Membuat potongan part...")
            part_len = duration / 10
            parts = []
            safe_effects = ["none", "mirror", "colorlight", "rotate"]

            for i in range(10):
                start = i * part_len
                end = min((i+1)*part_len, duration)
                sub = clip.subclip(start, end).set_fps(fps)
                sub = sub.fl_image(cinematic_effect)

                effect = random.choice(safe_effects)
                if effect == "mirror":
                    sub = sub.fx(vfx.mirror_x)
                elif effect == "colorlight":
                    sub = sub.fx(vfx.colorx, 1.03)
                elif effect == "rotate":
                    sub = sub.rotate(1)

                # ensure each sub is 9:16 and keep its duration
                sub = force_9_16(sub).set_duration(end - start)
                parts.append(sub)

                progress.progress(0.05 + (i/10)*0.4)
                status.text(f"Part {i+1}/10 — Efek: {effect}")

            # zoom halus aman (selected parts)
            if len(parts) >= 3:
                zoom_idxs = random.sample(range(1, len(parts)), 2)
                for z in zoom_idxs:
                    parts[z] = safe_zoom(parts[z], zoom=1.08)

            # insert clip (already forced 9:16)
            if insert_clip:
                parts.insert(2, insert_clip)
                parts.insert(len(parts)//2, insert_clip)

            random.shuffle(parts)

            # merge video
            status.text("Menggabungkan part...")
            final = concatenate_videoclips(parts, method="compose")
            final = final.set_fps(fps)

            progress.progress(0.8)

            # resize final to 9:16 (height 1920) and ensure even dims
            final = force_9_16(final)
            final = final.resize(height=1920)
            final_w = int(final.w // 2 * 2)
            final_h = int(final.h // 2 * 2)
            final = final.resize((final_w, final_h))

            out_path = user_temp_file(".mp4", "final")

            status.text("Render final (akan memakan waktu)...")
            # safe export settings for broad compatibility
            final.write_videofile(
                out_path,
                codec="libx264",
                audio=False,
                fps=fps,
                preset="medium",
                ffmpeg_params=[
                    "-profile:v", "baseline",
                    "-level", "3.0",
                    "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart"
                ]
            )

            final_out = out_path
            progress.progress(1.0)
            st.success("Selesai tanpa error!")
            st.video(final_out)

            with open(final_out, "rb") as fp:
                st.download_button("Download Video", fp, "final_video.mp4")

    except Exception as e:
        st.error(f"Terjadi error saat memproses video: {e}")
    finally:
        # cleanup: close objects if exist
        try:
            if clip is not None:
                clip.close()
        except Exception:
            pass
        try:
            if final_out is not None:
                pass  # keep final for download; user can clear via UI if needed
        except Exception:
            pass

# footer / help
st.markdown("---")
st.caption("Tip: tunggu hingga proses selesai sebelum menutup tab. Jika ingin membersihkan file temporer, restart aplikasi.")
