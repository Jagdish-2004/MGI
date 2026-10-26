import os
import sys
import time
import json
import uuid
import subprocess
import urllib.request
from pathlib import Path
from PIL import Image
import threading
import streamlit as st
import streamlit.components.v1 as components
from plyfile import PlyData

# Global process lock to protect against duplicate inference jobs across sessions
_INFERENCE_LOCK = threading.Lock()

# Paths
PROJECT_ROOT = Path(__file__).parent.resolve()
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
SHARP_CLI = PROJECT_ROOT / ".venv" / "Scripts" / "sharp.exe"
CHECKPOINT_PATH = PROJECT_ROOT / ".cache" / "torch" / "hub" / "checkpoints" / "sharp_2572gikvuh.pt"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
UPLOADS_DIR = PROJECT_ROOT / "uploads"
VIEWER_DIR = PROJECT_ROOT / "viewer"
VIEWER_SERVER_SCRIPT = VIEWER_DIR / "serve_viewer.py"
SAMPLE_TEASER = PROJECT_ROOT / "ml-sharp" / "data" / "teaser.jpg"
VIEWER_URL = "http://127.0.0.1:8080"

OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Page configuration
st.set_page_config(
    page_title="PhotoDepth 3D — Gaussian Splatting",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished interface
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #60a5fa 0%, #a855f7 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #94a3b8;
        margin-bottom: 1.5rem;
    }
    .metric-badge {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 8px 14px;
        margin-bottom: 8px;
    }
    .hardware-alert {
        background: rgba(14, 165, 233, 0.1);
        border-left: 4px solid #0284c7;
        padding: 10px 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 20px;
        font-size: 0.9rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

def check_viewer_server(timeout=1.0) -> bool:
    """Check if the local viewer server is running and responding."""
    try:
        with urllib.request.urlopen(f"{VIEWER_URL}/", timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_viewer_server():
    """Ensure the viewer server is running, or start it in background."""
    if check_viewer_server():
        return True
    
    # Try starting the server
    try:
        subprocess.Popen(
            [str(PYTHON_EXE), str(VIEWER_SERVER_SCRIPT), "8080"],
            cwd=str(PROJECT_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
        )
        # Wait up to 3 seconds for server to bind
        for _ in range(6):
            time.sleep(0.5)
            if check_viewer_server():
                return True
    except Exception as e:
        st.error(f"Failed to start viewer server: {e}")
    return False

def validate_ply_file(file_path: Path) -> dict:
    """Validate that a generated PLY file is genuine and readable."""
    if not file_path.is_file():
        raise FileNotFoundError(f"Output file does not exist: {file_path}")
    
    file_size = file_path.stat().st_size
    if file_size < 1_000_000:
        raise ValueError(f"File size too small for 3DGS ({file_size} bytes)")
    
    ply_data = PlyData.read(str(file_path))
    if "vertex" not in ply_data:
        raise ValueError("Invalid PLY: Missing 'vertex' element")
    
    vertex_count = len(ply_data["vertex"])
    if vertex_count < 10_000:
        raise ValueError(f"Abnormally low Gaussian count: {vertex_count}")
    
    properties = [p.name for p in ply_data["vertex"].properties]
    required_props = ["x", "y", "z", "f_dc_0", "opacity", "scale_0", "rot_0"]
    missing = [rp for rp in required_props if rp not in properties]
    if missing:
        raise ValueError(f"Missing essential 3DGS properties: {missing}")
    
    return {
        "file_size": file_size,
        "vertex_count": vertex_count,
        "properties_count": len(properties),
    }

def get_history_items():
    """Scan outputs directory for valid PLY files."""
    items = []
    for p in OUTPUTS_DIR.glob("*.ply"):
        try:
            stat = p.stat()
            items.append({
                "path": p,
                "name": p.name,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "mtime": stat.st_mtime,
                "time_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            })
        except Exception:
            continue
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items

# Initialize Session State
if "is_generating" not in st.session_state:
    st.session_state["is_generating"] = False
if "selected_ply" not in st.session_state:
    st.session_state["selected_ply"] = "sample_teaser.ply"
if "last_error" not in st.session_state:
    st.session_state["last_error"] = None
if "last_stats" not in st.session_state:
    st.session_state["last_stats"] = None

# Ensure server is running
server_ok = ensure_viewer_server()

# Sidebar: Controls & History
with st.sidebar:
    st.markdown("### ⚙️ System Status")
    if server_ok:
        st.success(f"Viewer Server: Active ({VIEWER_URL})")
    else:
        st.error("Viewer Server: Offline")
        if st.button("Restart Viewer Server"):
            ensure_viewer_server()
            st.rerun()

    st.markdown("---")
    st.markdown("### 📂 Generated Models History")
    history_items = get_history_items()
    
    if not history_items:
        st.info("No generated models in outputs yet.")
    else:
        names = [item["name"] for item in history_items]
        # Match current selection
        current_idx = 0
        if st.session_state["selected_ply"] in names:
            current_idx = names.index(st.session_state["selected_ply"])
        
        selected_name = st.radio(
            "Select 3DGS Scene:",
            names,
            index=current_idx,
            format_func=lambda n: f"{n} ({next(item['size_mb'] for item in history_items if item['name'] == n)} MB)"
        )
        if selected_name != st.session_state["selected_ply"]:
            st.session_state["selected_ply"] = selected_name
            st.rerun()
            
        # Delete management
        with st.expander("🗑️ Delete Selected Model"):
            if selected_name == "sample_teaser.ply":
                st.caption("Baseline sample model cannot be deleted.")
            else:
                confirm = st.checkbox("Confirm deletion of this model", key=f"del_{selected_name}")
                if st.button("Delete Permanently", disabled=not confirm):
                    target_file = OUTPUTS_DIR / selected_name
                    if target_file.exists() and target_file.is_file():
                        target_file.unlink()
                        st.session_state["selected_ply"] = "sample_teaser.ply"
                        st.success(f"Deleted {selected_name}")
                        st.rerun()

    st.markdown("---")
    st.markdown("### 📖 About PhotoDepth 3D")
    st.markdown(
        """
        - **Model**: Apple ML-SHARP (Monocular View Synthesis)
        - **Format**: 3D Gaussian Splatting (`.ply`)
        - **Coordinate System**: OpenCV ($X$ right, $Y$ down, $Z$ forward)
        - **Host**: Local execution only (No cloud APIs)
        """
    )

# Main Application Layout
st.markdown('<h1 class="main-header">PhotoDepth 3D</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Convert single real photographs into interactive 3D Gaussian Splats using Apple ML-SHARP.</p>',
    unsafe_allow_html=True,
)

# Hardware Notice
st.markdown(
    """
    <div class="hardware-alert">
        <strong>Hardware Execution Notice:</strong> This machine runs on an Intel CPU with integrated Intel Iris Xe graphics (no discrete NVIDIA CUDA GPU). 
        Prediction uses optimized CPU tensor operations and takes approximately <strong>1.5 to 2 minutes</strong> per photograph. 
        Camera trajectory MP4 video rendering is unavailable as it requires a CUDA GPU.
    </div>
    """,
    unsafe_allow_html=True,
)

col_input, col_viewer = st.columns([1, 1.3], gap="large")

with col_input:
    st.markdown("### 1. Select Input Photograph")
    
    input_source = st.radio(
        "Input Source:",
        ["Upload Photograph", "Use Repository Sample (teaser.jpg)"],
        horizontal=True,
    )
    
    input_image_path = None
    input_image_obj = None

    if input_source == "Upload Photograph":
        uploaded_file = st.file_uploader(
            "Upload Image (JPEG, PNG, HEIC)",
            type=["jpg", "jpeg", "png", "heic"],
            help="High-contrast, well-lit real photographs produce the best 3D splats.",
        )
        if uploaded_file is not None:
            try:
                input_image_obj = Image.open(uploaded_file)
                # Verify image can be decoded
                input_image_obj.verify()
                # Reopen after verify
                uploaded_file.seek(0)
                input_image_obj = Image.open(uploaded_file)
                
                # Save sanitized upload
                safe_id = f"img_{uuid.uuid4().hex[:8]}"
                save_ext = Path(uploaded_file.name).suffix.lower() or ".jpg"
                input_image_path = UPLOADS_DIR / f"{safe_id}{save_ext}"
                with open(input_image_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
            except Exception as e:
                st.error(f"Invalid image file: {e}")
                input_image_path = None
    else:
        if SAMPLE_TEASER.exists():
            input_image_path = SAMPLE_TEASER
            input_image_obj = Image.open(SAMPLE_TEASER)
        else:
            st.error("Sample image not found in repository.")

    # Image Preview & Info
    if input_image_obj is not None:
        st.image(input_image_obj, caption="Input Preview", use_container_width=True)
        w, h = input_image_obj.size
        st.markdown(
            f"""
            <div class="metric-badge">
                <strong>Resolution:</strong> {w} × {h} px &nbsp;|&nbsp; 
                <strong>Format:</strong> {input_image_obj.format} &nbsp;|&nbsp; 
                <strong>Mode:</strong> {input_image_obj.mode}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### 2. Run Monocular 3DGS Inference")
    
    can_generate = (
        input_image_path is not None
        and not st.session_state["is_generating"]
        and not _INFERENCE_LOCK.locked()
    )
    
    if _INFERENCE_LOCK.locked():
        st.warning("⏳ An inference job is currently running on the CPU. Please wait for it to complete.")

    btn_generate = st.button(
        "✨ Generate 3D Gaussian Splat",
        type="primary",
        disabled=not can_generate,
        use_container_width=True,
    )

    if btn_generate and can_generate:
        if not _INFERENCE_LOCK.acquire(blocking=False):
            st.warning("⚠️ An inference job was just started. Please wait.")
            st.rerun()

        st.session_state["is_generating"] = True
        st.session_state["last_error"] = None
        
        job_id = f"sharp_{time.strftime('%Y%m%d_%H%M%S')}"
        job_temp_dir = UPLOADS_DIR / f"job_{job_id}"
        job_temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare CLI command
        cli_cmd = [
            str(SHARP_CLI),
            "predict",
            "-i", str(input_image_path),
            "-o", str(job_temp_dir),
            "-c", str(CHECKPOINT_PATH),
            "--device", "cpu",
            "--no-render",
            "-v"
        ]
        
        status_text = st.empty()
        progress_bar = st.empty()
        status_text.info("🚀 Launching ML-SHARP CPU neural inference... Please wait ~1.5 to 2 minutes.")
        progress_bar.progress(0.1)

        start_time = time.time()
        
        try:
            env = os.environ.copy()
            env["TORCH_HOME"] = str(PROJECT_ROOT / ".cache" / "torch")
            env["OMP_NUM_THREADS"] = "4"
            env["MKL_NUM_THREADS"] = "4"
            
            log_file_path = job_temp_dir / "inference.log"
            with open(log_file_path, "w", encoding="utf-8", errors="replace") as log_file:
                process = subprocess.Popen(
                    cli_cmd,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    env=env,
                    cwd=str(PROJECT_ROOT),
                )
                
                # Non-blocking poll loop with honest elapsed time
                while process.poll() is None:
                    elapsed = time.time() - start_time
                    status_text.info(f"⏳ Running CPU inference... Elapsed: {int(elapsed)} seconds (Typical: 100–120s)")
                    # Simulate smooth activity indicator
                    pct = min(0.90, 0.1 + (elapsed / 120.0) * 0.8)
                    progress_bar.progress(pct)
                    time.sleep(1.0)
            
            total_elapsed = time.time() - start_time
            
            if process.returncode != 0:
                log_content = ""
                if log_file_path.exists():
                    log_content = log_file_path.read_text(encoding="utf-8", errors="replace")
                raise RuntimeError(f"CLI exited with code {process.returncode}:\n{log_content}")
            
            # Find generated PLY
            generated_plys = list(job_temp_dir.glob("*.ply"))
            if not generated_plys:
                raise FileNotFoundError("CLI exited with 0 but no output .ply was created.")
            
            raw_ply = generated_plys[0]
            
            # Rigorous PLY validation
            stats = validate_ply_file(raw_ply)
            
            # Move to permanent outputs
            final_ply_name = f"{job_id}.ply"
            final_ply_path = OUTPUTS_DIR / final_ply_name
            raw_ply.rename(final_ply_path)
            
            st.session_state["selected_ply"] = final_ply_name
            st.session_state["last_stats"] = {
                "elapsed_sec": round(total_elapsed, 1),
                "gaussians": stats["vertex_count"],
                "size_mb": round(stats["file_size"] / (1024 * 1024), 2),
            }
            
            status_text.success(
                f"✅ Generation complete in {round(total_elapsed, 1)}s! "
                f"Created {stats['vertex_count']:,} Gaussians ({round(stats['file_size'] / (1024*1024), 2)} MB)."
            )
            progress_bar.progress(1.0)
            
        except Exception as err:
            st.session_state["last_error"] = str(err)
            status_text.error(f"❌ Inference failed: {err}")
        finally:
            if _INFERENCE_LOCK.locked():
                try:
                    _INFERENCE_LOCK.release()
                except RuntimeError:
                    pass
            st.session_state["is_generating"] = False
            # Clean up temp job dir
            try:
                for f in job_temp_dir.glob("*"):
                    f.unlink()
                job_temp_dir.rmdir()
            except Exception:
                pass
            time.sleep(1.0)
            st.rerun()

    # Display error if last job failed
    if st.session_state["last_error"]:
        with st.expander("⚠️ Error Diagnostic Trace"):
            st.code(st.session_state["last_error"])

# Column 2: 3D Interactive Viewer & Download
with col_viewer:
    st.markdown("### 3. Interactive 3D Scene Viewer")
    
    active_ply_name = st.session_state.get("selected_ply", "sample_teaser.ply")
    active_ply_path = OUTPUTS_DIR / active_ply_name
    
    if not active_ply_path.exists():
        # Fallback to test_output if outputs has no file
        active_ply_path = PROJECT_ROOT / "test_output" / "teaser.ply"
        active_ply_name = "teaser.ply"
    
    # Active Model Metadata & Actions
    if active_ply_path.exists():
        stat = active_ply_path.stat()
        size_mb = round(stat.st_size / (1024 * 1024), 2)
        
        c_meta1, c_meta2 = st.columns([1, 1])
        with c_meta1:
            st.markdown(f"**Viewing:** `{active_ply_name}` ({size_mb} MB)")
        with c_meta2:
            download_url = f"{VIEWER_URL}/api/download?file={active_ply_name}"
            st.link_button(
                label="💾 Download 3DGS (.ply)",
                url=download_url,
                type="primary",
                use_container_width=True,
            )


        # Embed local WebGL viewer iframe
        # Pass file param and timestamp to force browser update on selection
        mtime = int(stat.st_mtime)
        viewer_frame_url = f"{VIEWER_URL}/?file=/data/{active_ply_name}&t={mtime}"
        
        if hasattr(st, "iframe"):
            st.iframe(src=viewer_frame_url, height=660)
        else:
            components.iframe(src=viewer_frame_url, height=660, scrolling=False)


        
        st.caption(
            "💡 **Controls:** Left-Click + Drag to **Orbit** | Right-Click + Drag to **Pan** | Scroll to **Zoom** | Use **Reset Camera** inside viewer to re-center."
        )
    else:
        st.warning("No 3D Gaussian Splat model available to render. Run inference or select a model.")
