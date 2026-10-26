# PhotoDepth 3D — Monocular 3D Gaussian Splatting Studio

An interactive, local desktop web application that transforms single photographs into real-time 3D Gaussian Splatting (3DGS) scenes using Apple's official ML-SHARP neural model.

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.40+-FF4B4B?logo=streamlit)
![PyTorch](https://img.shields.io/badge/PyTorch-2.4+-EE4C2C?logo=pytorch)
![Three.js](https://img.shields.io/badge/Three.js-0.168-black?logo=threedotjs)
![3DGS](https://img.shields.io/badge/3DGS-Gaussian--Splats--3D-brightgreen)

---

## 🌟 Key Features

- **Monocular 3D Reconstruction**: Convert standard single RGB images (JPEG, PNG, HEIF/HEIC) into full 3D Gaussian Splats.
- **Apple ML-SHARP Engine**: Powered by Apple's open-source sharp monocular view synthesis architecture.
- **Embedded WebGL 3DGS Viewer**: Built with Three.js and `@mkkellogg/gaussian-splats-3d` supporting Orbit, Pan, Dolly Zoom, and camera reset.
- **100% Local & Private**: Operates strictly on `127.0.0.1` with zero data sent to external cloud APIs.
- **Streamlit Studio UI**: Responsive dashboard with live job progression, point cloud statistics (Gaussian count, bounding boxes, file size), inspection history, and 3D previewing.

---

## 🏗️ Architecture

```
PhotoDepth-3D/
├── app.py                      # Main Streamlit web application & job management
├── download_checkpoint.py      # Resilient downloader for ML-SHARP weights
├── run_app.ps1                 # One-click launcher for Windows (Viewer + App)
├── requirements.txt            # Python dependencies
├── ml-sharp/                   # Apple ML-SHARP monocular synthesis framework
│   ├── src/                    # Neural architecture & inference pipelines
│   └── data/teaser.jpg         # Sample benchmark scene
├── viewer/                     # Standalone WebGL 3DGS Viewer
│   ├── index.html              # Viewer DOM interface
│   ├── main.js                 # Three.js + GaussianSplats3D renderer
│   ├── serve_viewer.py         # Local HTTP server with streaming PLY endpoint
│   └── libs/                   # Self-contained ESM libraries
├── outputs/                    # Exported 3D Gaussian PLY point clouds
└── uploads/                    # Temporary staged upload directories
```

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python**: 3.12 or compatible 3.10+
- **Git**

### 2. Setup Virtual Environment & Dependencies

```bash
# Clone the repository
git clone https://github.com/Jagdish-2004/MGI.git
cd MGI

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -e ./ml-sharp
```

### 3. Download the Neural Model Checkpoint

```bash
python download_checkpoint.py
```
This downloads `sharp_2572gikvuh.pt` (~1.4 GB) directly to `.cache/torch/hub/checkpoints/`.

### 4. Run the Application

On Windows:
```powershell
.\run_app.ps1
```

Or manually:
```bash
# Terminal 1: Start 3DGS Viewer Server (Port 8080)
python viewer/serve_viewer.py 8080

# Terminal 2: Start Streamlit Web Studio (Port 8501)
streamlit run app.py
```

Navigate to `http://127.0.0.1:8501/` to open the studio!

---

## 🎮 3D Viewer Navigation Controls

| Action | Mouse / Trackpad |
| :--- | :--- |
| **Orbit / Rotate** | Left Click + Drag |
| **Pan** | Right Click + Drag *(or Shift + Left Click)* |
| **Zoom (Dolly)** | Mouse Scroll Wheel *(or Trackpad Pinch)* |
| **Reset View** | Click **Reset Camera** button |
| **Import External PLY** | Click **Open PLY** in viewer toolbar |

---

## 📄 License & Acknowledgments

- Built upon [Apple ML-SHARP](https://github.com/apple/ml-sharp) (Apache 2.0 / Apple Sample Code License).
- WebGL 3D rendering uses [gaussian-splats-3d](https://github.com/mkkellogg/GaussianSplats3D) by Mark Kellogg (MIT License).
