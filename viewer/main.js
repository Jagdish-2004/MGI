import * as THREE from 'three';
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

// UI Elements
const statusDot = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const statusModal = document.getElementById('status-modal');
const modalSpinner = document.getElementById('modal-spinner');
const modalTitle = document.getElementById('modal-title');
const modalDesc = document.getElementById('modal-desc');
const modalProgress = document.getElementById('modal-progress');
const progressContainer = document.getElementById('progress-container');
const btnRetry = document.getElementById('modal-btn-retry');
const btnReset = document.getElementById('btn-reset');
const fileInput = document.getElementById('file-input');
const viewerContainer = document.getElementById('viewer-container');

// Camera defaults for Apple ML-SHARP OpenCV coordinate convention:
// Center is roughly (0, 0, +1.2), Y down, Z forward.
const INITIAL_CAMERA_POS = [0, 0, -0.4];
const INITIAL_LOOK_AT = [0, 0, 1.2];
const CAMERA_UP = [0, -1, 0];

let viewer = null;
let currentScenePath = null;

function setStatus(state, message) {
    statusDot.className = 'status-dot ' + state;
    statusText.textContent = message;
}

function showModal(title, desc, isError = false) {
    statusModal.classList.remove('hidden');
    modalTitle.textContent = title;
    modalDesc.textContent = desc;
    if (isError) {
        modalSpinner.style.display = 'none';
        progressContainer.style.display = 'none';
        btnRetry.style.display = 'inline-block';
        setStatus('error', 'Error: ' + title);
    } else {
        modalSpinner.style.display = 'block';
        progressContainer.style.display = 'block';
        btnRetry.style.display = 'none';
    }
}

function hideModal() {
    statusModal.classList.add('hidden');
}

function initViewer() {
    try {
        viewer = new GaussianSplats3D.Viewer({
            rootElement: viewerContainer,
            cameraUp: CAMERA_UP,
            initialCameraPosition: INITIAL_CAMERA_POS,
            initialCameraLookAt: INITIAL_LOOK_AT,
            selfDrivenMode: true,
            useBuiltInControls: true,
            sharedMemoryForWorkers: false,
            gpuAcceleratedSort: false,
            antialiased: false,
            dynamicScene: false
        });

        setStatus('ready', 'Viewer initialized. Starting load...');
        return true;
    } catch (err) {
        console.error('Failed to initialize GaussianSplats3D Viewer:', err);
        showModal('Viewer Initialization Failed', err.message || 'WebGL / Three.js failure', true);
        return false;
    }
}

async function loadSplatScene(url) {
    if (!viewer) return;
    currentScenePath = url;
    showModal('Loading 3D Gaussian Splat', 'Fetching data from ' + url);
    setStatus('', 'Downloading scene data...');
    modalProgress.style.width = '0%';

    try {
        await viewer.addSplatScene(url, {
            format: GaussianSplats3D.SceneFormat.Ply,
            splatAlphaRemovalThreshold: 1,
            showLoadingUI: false,
            onProgress: (percent) => {
                const p = Math.round(percent);
                modalProgress.style.width = `${p}%`;
                modalDesc.textContent = `Downloading & parsing PLY (${p}%)...`;
                setStatus('', `Loading scene (${p}%)...`);
            }
        });

        viewer.start();
        hideModal();

        const splatMesh = viewer.getSplatMesh();
        const splatCount = splatMesh ? splatMesh.getSplatCount() : '1,179,648';
        setStatus('ready', `Active scene: ${Number(splatCount).toLocaleString()} Gaussians`);
        console.log(`[PhotoDepth 3D] Successfully loaded scene from ${url} with ${splatCount} splats.`);
    } catch (err) {
        console.error('[PhotoDepth 3D] Failed to load splat scene:', err);
        showModal('Scene Loading Failed', `Could not load ${url}: ${err.message || err}`, true);
    }
}

async function loadLocalFile(file) {
    if (!viewer || !file) return;
    showModal('Reading Local File', `Reading ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)...`);
    setStatus('', `Reading ${file.name}...`);
    modalProgress.style.width = '20%';

    try {
        const arrayBuffer = await file.arrayBuffer();
        modalProgress.style.width = '60%';
        modalDesc.textContent = 'Parsing PLY vertex data into Gaussian Splat buffer...';

        const splatBuffer = GaussianSplats3D.PlyParser.parseToUncompressedSplatBuffer(arrayBuffer);
        modalProgress.style.width = '90%';

        // Clear existing scenes
        if (viewer.splatMesh) {
            viewer.dispose();
            viewerContainer.innerHTML = '';
            initViewer();
        }

        await viewer.addSplatBuffers([splatBuffer]);
        viewer.start();
        hideModal();

        const count = splatBuffer.getSplatCount();
        setStatus('ready', `Loaded ${file.name}: ${count.toLocaleString()} Gaussians`);
        console.log(`[PhotoDepth 3D] Local file ${file.name} loaded with ${count} splats.`);
    } catch (err) {
        console.error('[PhotoDepth 3D] Failed to parse local PLY file:', err);
        showModal('Parsing Error', `Could not parse ${file.name}: ${err.message || err}`, true);
    }
}

function resetCamera() {
    if (!viewer) return;
    try {
        if (viewer.camera && viewer.controls) {
            viewer.camera.position.set(...INITIAL_CAMERA_POS);
            viewer.camera.up.set(...CAMERA_UP);
            viewer.controls.target.set(...INITIAL_LOOK_AT);
            viewer.controls.update();
            console.log('[PhotoDepth 3D] Camera view reset to initial pose.');
        }
    } catch (e) {
        console.warn('Error resetting camera:', e);
    }
}

// Event Listeners
btnReset.addEventListener('click', resetCamera);

btnRetry.addEventListener('click', () => {
    if (currentScenePath) {
        loadSplatScene(currentScenePath);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
        loadLocalFile(e.target.files[0]);
    }
});

// Window resize handling
window.addEventListener('resize', () => {
    if (viewer && viewer.onWindowResize) {
        viewer.onWindowResize();
    }
});

// PostMessage communication for iframe embedding
window.addEventListener('message', (event) => {
    if (event.data && typeof event.data === 'object') {
        if (event.data.action === 'load' && event.data.file) {
            loadSplatScene(event.data.file);
        } else if (event.data.action === 'reset') {
            resetCamera();
        }
    }
});

// Auto-start on load
window.addEventListener('DOMContentLoaded', () => {
    if (initViewer()) {
        // Query param override or default to /api/ply
        const urlParams = new URLSearchParams(window.location.search);
        const sceneUrl = urlParams.get('file') || '/api/ply';
        loadSplatScene(sceneUrl);
    }
});

