import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Compass, Eye, RotateCcw, Sun, Moon, Orbit, Video } from 'lucide-react';

export default function OrbitGlobe3D({ telemetry, orbitPoints = [], isPlaying = false }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const earthGroupRef = useRef(null);
  const cloudMeshRef = useRef(null);
  const satMeshRef = useRef(null);
  const satGroupRef = useRef(null);
  const solarPanelsRef = useRef(null);
  const orbitLineRef = useRef(null);
  const sunLightRef = useRef(null);
  const animFrameId = useRef(null);

  // Smooth interpolation target and current state
  const targetPos = useRef(new THREE.Vector3(0, 0, 7.5));
  const currentPos = useRef(new THREE.Vector3(0, 0, 7.5));
  const targetQuat = useRef(new THREE.Quaternion());
  const currentQuat = useRef(new THREE.Quaternion());

  const [viewMode, setViewMode] = useState('satellite'); // 'orbit', 'satellite', 'earth'
  const viewModeRef = useRef('satellite');
  const isDraggingRef = useRef(false);
  const previousMousePosition = useRef({ x: 0, y: 0 });
  const cameraAngle = useRef({ theta: 1.2, phi: 0.8, distance: 16 });
  const targetDistance = useRef(16);
  const aliveRef = useRef(true);

  useEffect(() => {
    viewModeRef.current = viewMode;
  }, [viewMode]);

  // High-Resolution Procedural Photorealistic Earth Texture
  const createPhotorealisticEarthTexture = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 2048;
    canvas.height = 1024;
    const ctx = canvas.getContext('2d');

    // 1. Deep Oceanic Gradient Base
    const oceanGrad = ctx.createLinearGradient(0, 0, 0, 1024);
    oceanGrad.addColorStop(0, '#020b1e');
    oceanGrad.addColorStop(0.3, '#041738');
    oceanGrad.addColorStop(0.5, '#0a2e5c');
    oceanGrad.addColorStop(0.7, '#041738');
    oceanGrad.addColorStop(1, '#020b1e');
    ctx.fillStyle = oceanGrad;
    ctx.fillRect(0, 0, 2048, 1024);

    // 2. Realistic Continent Contours & Mountain Relief
    ctx.fillStyle = '#1e3a29'; // Forest green / terrain
    
    // Draw North America
    ctx.beginPath();
    ctx.moveTo(250, 180);
    ctx.bezierCurveTo(320, 150, 480, 160, 520, 260);
    ctx.bezierCurveTo(550, 340, 480, 420, 420, 480);
    ctx.bezierCurveTo(380, 520, 320, 480, 280, 400);
    ctx.bezierCurveTo(220, 340, 200, 240, 250, 180);
    ctx.fill();

    // Draw South America
    ctx.beginPath();
    ctx.moveTo(460, 490);
    ctx.bezierCurveTo(560, 520, 620, 600, 580, 720);
    ctx.bezierCurveTo(540, 840, 460, 920, 440, 880);
    ctx.bezierCurveTo(420, 780, 400, 640, 430, 540);
    ctx.fill();

    // Draw Eurasia
    ctx.fillStyle = '#2d4a34';
    ctx.beginPath();
    ctx.moveTo(850, 180);
    ctx.bezierCurveTo(1050, 120, 1450, 140, 1650, 220);
    ctx.bezierCurveTo(1750, 320, 1650, 480, 1450, 450);
    ctx.bezierCurveTo(1250, 420, 1100, 480, 950, 420);
    ctx.bezierCurveTo(820, 380, 780, 260, 850, 180);
    ctx.fill();

    // Draw Africa
    ctx.fillStyle = '#4a442d'; // Savanna/Desert tone
    ctx.beginPath();
    ctx.moveTo(920, 400);
    ctx.bezierCurveTo(1080, 390, 1150, 480, 1120, 620);
    ctx.bezierCurveTo(1080, 760, 980, 820, 940, 780);
    ctx.bezierCurveTo(900, 680, 860, 520, 920, 400);
    ctx.fill();

    // Draw Australia
    ctx.fillStyle = '#5c4326';
    ctx.beginPath();
    ctx.arc(1550, 680, 110, 0, Math.PI * 2);
    ctx.fill();

    // Draw Antarctica
    ctx.fillStyle = '#d0e5f5';
    ctx.fillRect(0, 920, 2048, 104);

    // 3. Coordinate Navigation Grid
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.12)';
    ctx.lineWidth = 1;
    for (let x = 0; x <= 2048; x += 128) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, 1024);
      ctx.stroke();
    }
    for (let y = 0; y <= 1024; y += 64) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(2048, y);
      ctx.stroke();
    }

    // Equator Line Highlight
    ctx.strokeStyle = 'rgba(0, 240, 255, 0.35)';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, 512);
    ctx.lineTo(2048, 512);
    ctx.stroke();

    return new THREE.CanvasTexture(canvas);
  };

  // High-Resolution Procedural Atmospheric Cloud Texture
  const createCloudTexture = () => {
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 512;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = 'rgba(0, 0, 0, 0)';
    ctx.fillRect(0, 0, 1024, 512);

    ctx.fillStyle = 'rgba(255, 255, 255, 0.45)';
    for (let i = 0; i < 90; i++) {
      const x = Math.random() * 1024;
      const y = Math.random() * 512;
      const rx = 30 + Math.random() * 90;
      const ry = 15 + Math.random() * 40;
      ctx.beginPath();
      ctx.ellipse(x, y, rx, ry, Math.random() * Math.PI, 0, Math.PI * 2);
      ctx.fill();
    }
    return new THREE.CanvasTexture(canvas);
  };

  // Build Detailed Satellite Mesh
  const buildSatelliteMesh = () => {
    const group = new THREE.Group();

    // 1. Central Bus with Golden Foil MLI Texture
    const busGeo = new THREE.BoxGeometry(0.5, 0.5, 0.7);
    const busMat = new THREE.MeshStandardMaterial({
      color: 0xdfa015,
      metalness: 0.92,
      roughness: 0.25,
      emissive: 0x332200,
      emissiveIntensity: 0.2
    });
    const busMesh = new THREE.Mesh(busGeo, busMat);
    group.add(busMesh);

    // 2. Solar Panel Wings (Left and Right)
    const solarGroup = new THREE.Group();
    const panelGeo = new THREE.BoxGeometry(1.6, 0.03, 0.55);
    const panelMat = new THREE.MeshStandardMaterial({
      color: 0x0a4fa0,
      metalness: 0.85,
      roughness: 0.2,
      emissive: 0x001833
    });
    
    // Left Wing
    const leftPanel = new THREE.Mesh(panelGeo, panelMat);
    leftPanel.position.set(-1.15, 0, 0);
    solarGroup.add(leftPanel);

    // Right Wing
    const rightPanel = new THREE.Mesh(panelGeo, panelMat);
    rightPanel.position.set(1.15, 0, 0);
    solarGroup.add(rightPanel);

    // Metallic panel frame mounts
    const mountGeo = new THREE.CylinderGeometry(0.04, 0.04, 2.5, 8);
    const mountMat = new THREE.MeshStandardMaterial({ color: 0x888888, metalness: 0.9, roughness: 0.3 });
    const mount = new THREE.Mesh(mountGeo, mountMat);
    mount.rotation.z = Math.PI / 2;
    solarGroup.add(mount);

    group.add(solarGroup);
    solarPanelsRef.current = solarGroup;

    // 3. High-Gain Parabolic Dish Antenna
    const dishGeo = new THREE.ConeGeometry(0.24, 0.16, 24, 1, true);
    const dishMat = new THREE.MeshStandardMaterial({ color: 0xffffff, metalness: 0.7, roughness: 0.3 });
    const dish = new THREE.Mesh(dishGeo, dishMat);
    dish.position.set(0, 0.38, 0.1);
    dish.rotation.x = Math.PI * 0.75;
    group.add(dish);

    // Feed Horn
    const hornGeo = new THREE.CylinderGeometry(0.02, 0.02, 0.2, 8);
    const hornMat = new THREE.MeshStandardMaterial({ color: 0xcccccc });
    const horn = new THREE.Mesh(hornGeo, hornMat);
    horn.position.set(0, 0.46, 0.18);
    group.add(horn);

    // 4. Thruster Nozzle
    const thrusterGeo = new THREE.CylinderGeometry(0.08, 0.14, 0.2, 16);
    const thrusterMat = new THREE.MeshStandardMaterial({ color: 0x333333, metalness: 0.8, roughness: 0.4 });
    const thruster = new THREE.Mesh(thrusterGeo, thrusterMat);
    thruster.position.set(0, 0, -0.42);
    thruster.rotation.x = Math.PI / 2;
    group.add(thruster);

    // 5. Glowing Beacon Pulse
    const beaconGeo = new THREE.SphereGeometry(0.1, 16, 16);
    const beaconMat = new THREE.MeshBasicMaterial({ color: 0x00f0ff });
    const beacon = new THREE.Mesh(beaconGeo, beaconMat);
    beacon.position.set(0, 0.3, 0);
    group.add(beacon);

    return group;
  };

  useEffect(() => {
    if (!mountRef.current) return;
    aliveRef.current = true;

    const mountEl = mountRef.current;
    // React StrictMode remounts effects — clear any leftover canvas first
    while (mountEl.firstChild) {
      mountEl.removeChild(mountEl.firstChild);
    }

    const width = mountEl.clientWidth || 640;
    const height = mountEl.clientHeight || 480;

    // Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(45, width / Math.max(height, 1), 0.1, 1000);
    camera.position.set(10, 8, 12);
    cameraRef.current = camera;

    // Renderer with High Dynamic Range settings
    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    } catch (err) {
      console.error('WebGL unavailable:', err);
      mountEl.innerHTML = '<div style="padding:24px;color:#f87171;font-family:monospace">WebGL unavailable — 3D globe disabled.</div>';
      return undefined;
    }
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    mountEl.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Lighting
    const ambientLight = new THREE.AmbientLight(0x1a2845, 1.4);
    scene.add(ambientLight);

    const sunLight = new THREE.DirectionalLight(0xffffff, 3.2);
    sunLight.position.set(50, 15, 25);
    scene.add(sunLight);
    sunLightRef.current = sunLight;

    // Earth Sphere Group
    const earthGroup = new THREE.Group();
    const earthRadius = 5.0;

    // Main Earth Globe
    const earthGeo = new THREE.SphereGeometry(earthRadius, 64, 64);
    const earthTex = createPhotorealisticEarthTexture();
    const earthMat = new THREE.MeshStandardMaterial({
      map: earthTex,
      roughness: 0.65,
      metalness: 0.15,
    });
    const earthMesh = new THREE.Mesh(earthGeo, earthMat);
    earthGroup.add(earthMesh);

    // Cloud Layer
    const cloudGeo = new THREE.SphereGeometry(earthRadius * 1.015, 64, 64);
    const cloudTex = createCloudTexture();
    const cloudMat = new THREE.MeshStandardMaterial({
      map: cloudTex,
      transparent: true,
      opacity: 0.4,
      blending: THREE.AdditiveBlending,
    });
    const cloudMesh = new THREE.Mesh(cloudGeo, cloudMat);
    earthGroup.add(cloudMesh);
    cloudMeshRef.current = cloudMesh;

    // Atmosphere Outer Glow
    const atmoGeo = new THREE.SphereGeometry(earthRadius * 1.05, 64, 64);
    const atmoMat = new THREE.MeshBasicMaterial({
      color: 0x00c8ff,
      transparent: true,
      opacity: 0.18,
      side: THREE.BackSide,
    });
    const atmoMesh = new THREE.Mesh(atmoGeo, atmoMat);
    earthGroup.add(atmoMesh);

    scene.add(earthGroup);
    earthGroupRef.current = earthGroup;

    // Starfield Background
    const starsGeo = new THREE.BufferGeometry();
    const starCount = 1200;
    const starPositions = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPositions[i] = (Math.random() - 0.5) * 150;
      starPositions[i + 1] = (Math.random() - 0.5) * 150;
      starPositions[i + 2] = (Math.random() - 0.5) * 150;
    }
    starsGeo.setAttribute('position', new THREE.BufferAttribute(starPositions, 3));
    const starsMat = new THREE.PointsMaterial({ color: 0xaaccff, size: 0.6, transparent: true, opacity: 0.7 });
    const starField = new THREE.Points(starsGeo, starsMat);
    scene.add(starField);

    // Satellite Mesh
    const satMesh = buildSatelliteMesh();
    scene.add(satMesh);
    satMeshRef.current = satMesh;

    // Orbit Path Line
    const orbitPathGeo = new THREE.BufferGeometry();
    const orbitPathMat = new THREE.LineBasicMaterial({
      color: 0x00f0ff,
      transparent: true,
      opacity: 0.7,
      linewidth: 2,
    });
    const orbitLine = new THREE.Line(orbitPathGeo, orbitPathMat);
    scene.add(orbitLine);
    orbitLineRef.current = orbitLine;

    // Mouse Controls
    const onMouseDown = (e) => {
      isDraggingRef.current = true;
      previousMousePosition.current = { x: e.clientX, y: e.clientY };
    };

    const onMouseMove = (e) => {
      if (!isDraggingRef.current) return;
      const deltaX = e.clientX - previousMousePosition.current.x;
      const deltaY = e.clientY - previousMousePosition.current.y;

      cameraAngle.current.theta -= deltaX * 0.007;
      cameraAngle.current.phi = Math.max(0.1, Math.min(Math.PI - 0.1, cameraAngle.current.phi + deltaY * 0.007));

      previousMousePosition.current = { x: e.clientX, y: e.clientY };
    };

    const onMouseUp = () => {
      isDraggingRef.current = false;
    };

    const onWheel = (e) => {
      e.preventDefault();
      targetDistance.current = Math.max(6, Math.min(32, targetDistance.current + e.deltaY * 0.015));
    };

    mountEl.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    mountEl.addEventListener('wheel', onWheel, { passive: false });

    // Smooth 60 FPS Render Loop with Interpolation
    const animate = () => {
      if (!aliveRef.current) return;
      animFrameId.current = requestAnimationFrame(animate);

      try {
        // Rotate Earth and Clouds
        if (earthGroupRef.current) {
          earthGroupRef.current.rotation.y += 0.0006;
        }
        if (cloudMeshRef.current) {
          cloudMeshRef.current.rotation.y += 0.0009;
        }

        // Smoothly interpolate satellite position & attitude (SLERP / LERP)
        currentPos.current.lerp(targetPos.current, 0.15);
        currentQuat.current.slerp(targetQuat.current, 0.15);

        if (satMeshRef.current) {
          satMeshRef.current.position.copy(currentPos.current);
          satMeshRef.current.quaternion.copy(currentQuat.current);

          // Orient solar panels toward Sun
          if (solarPanelsRef.current && sunLightRef.current) {
            const sunPos = sunLightRef.current.position.clone().normalize();
            solarPanelsRef.current.lookAt(sunPos);
          }
        }

        // Smooth camera damping
        cameraAngle.current.distance += (targetDistance.current - cameraAngle.current.distance) * 0.1;
        const { theta, phi, distance } = cameraAngle.current;
        const mode = viewModeRef.current;

        if (mode === 'satellite' && satMeshRef.current) {
          const satP = satMeshRef.current.position;
          camera.position.set(
            satP.x + distance * 0.35 * Math.sin(phi) * Math.sin(theta),
            satP.y + distance * 0.35 * Math.cos(phi),
            satP.z + distance * 0.35 * Math.sin(phi) * Math.cos(theta)
          );
          camera.lookAt(satP);
        } else {
          camera.position.set(
            distance * Math.sin(phi) * Math.sin(theta),
            distance * Math.cos(phi),
            distance * Math.sin(phi) * Math.cos(theta)
          );
          camera.lookAt(0, 0, 0);
        }

        renderer.render(scene, camera);
      } catch (err) {
        console.error('OrbitGlobe render frame error:', err);
        aliveRef.current = false;
      }
    };

    animate();

    const handleResize = () => {
      if (!aliveRef.current || !mountRef.current || !renderer || !camera) return;
      const newWidth = mountRef.current.clientWidth;
      const newHeight = mountRef.current.clientHeight || 480;
      camera.aspect = newWidth / Math.max(newHeight, 1);
      camera.updateProjectionMatrix();
      renderer.setSize(newWidth, newHeight);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      aliveRef.current = false;
      cancelAnimationFrame(animFrameId.current);
      window.removeEventListener('resize', handleResize);
      mountEl.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      mountEl.removeEventListener('wheel', onWheel);
      try {
        if (renderer?.domElement?.parentNode) {
          renderer.domElement.parentNode.removeChild(renderer.domElement);
        }
        renderer?.dispose();
      } catch (_) {
        /* ignore StrictMode double-cleanup races */
      }
      sceneRef.current = null;
      rendererRef.current = null;
      orbitLineRef.current = null;
      satMeshRef.current = null;
      earthGroupRef.current = null;
      cloudMeshRef.current = null;
    };
  }, []);

  // Update target position and quaternion when telemetry changes
  useEffect(() => {
    if (!telemetry) return;

    // Scale Earth R = 6378 km -> 5.0 scene units
    const scale = 5.0 / 6378.137;
    const posX = (telemetry.position_x || 6800) * scale;
    const posY = (telemetry.position_z || 0) * scale;
    const posZ = (telemetry.position_y || 0) * scale;

    targetPos.current.set(posX, posY, posZ);

    if (telemetry.orientation_q0 !== undefined) {
      targetQuat.current.set(
        telemetry.orientation_q1 || 0,
        telemetry.orientation_q3 || 0,
        telemetry.orientation_q2 || 0,
        telemetry.orientation_q0 || 1
      );
    }
  }, [telemetry]);

  // Update full orbit track line
  useEffect(() => {
    if (!Array.isArray(orbitPoints) || orbitPoints.length === 0 || !orbitLineRef.current) return;

    const scale = 5.0 / 6378.137;
    const pts = orbitPoints.map(p => new THREE.Vector3(
      (Number(p.position_x) || 0) * scale,
      (Number(p.position_z) || 0) * scale,
      (Number(p.position_y) || 0) * scale
    ));

    try {
      orbitLineRef.current.geometry.setFromPoints(pts);
    } catch (err) {
      console.error('Failed updating orbit path:', err);
    }
  }, [orbitPoints]);

  const satLat = Number(telemetry?.latitude ?? 0);
  const satLon = Number(telemetry?.longitude ?? 0);
  const satAlt = Number(telemetry?.altitude_km ?? 418);
  const isSun = Boolean(telemetry?.sunlit ?? true);
  const velMag = Math.sqrt(
    (Number(telemetry?.velocity_x) || 0) ** 2 +
    (Number(telemetry?.velocity_y) || 0) ** 2 +
    (Number(telemetry?.velocity_z) || 0) ** 2
  ).toFixed(2);

  return (
    <div className="globe-3d-wrap">
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />

      {/* Floating HUD Telemetry Overlay */}
      <div className="globe-hud-overlay">
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
          <span style={{ color: '#00f0ff', fontWeight: 'bold' }}>SAT: ISS-25544</span>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            color: isSun ? '#10b981' : '#f59e0b',
            background: isSun ? 'rgba(16,185,129,0.15)' : 'rgba(245,158,11,0.15)',
            padding: '2px 6px',
            borderRadius: '4px',
            fontSize: '0.68rem'
          }}>
            {isSun ? <Sun size={12} /> : <Moon size={12} />}
            {isSun ? 'SUNLIT' : 'ECLIPSE'}
          </span>
        </div>
        <div style={{ color: '#94a3b8' }}>LAT: <span style={{ color: '#ffffff' }}>{satLat >= 0 ? `${satLat}° N` : `${Math.abs(satLat)}° S`}</span></div>
        <div style={{ color: '#94a3b8' }}>LON: <span style={{ color: '#ffffff' }}>{satLon >= 0 ? `${satLon}° E` : `${Math.abs(satLon)}° W`}</span></div>
        <div style={{ color: '#94a3b8' }}>ALT: <span style={{ color: '#00f0ff' }}>{satAlt} km</span> | VEL: <span style={{ color: '#00f0ff' }}>{velMag} km/s</span></div>
      </div>

      {/* Camera View Mode Controls */}
      <div className="globe-controls-overlay">
        <button
          className={`btn-control ${viewMode === 'satellite' ? 'active' : ''}`}
          onClick={() => { setViewMode('satellite'); targetDistance.current = 8; }}
          title="Smooth Satellite Chase Cam"
        >
          <Eye size={14} /> Chase Sat
        </button>
        <button
          className={`btn-control ${viewMode === 'orbit' ? 'active' : ''}`}
          onClick={() => { setViewMode('orbit'); targetDistance.current = 17; }}
          title="Global Orbit View"
        >
          <Orbit size={14} /> Orbit
        </button>
        <button
          className="btn-control"
          onClick={() => { cameraAngle.current = { theta: 1.2, phi: 0.8, distance: 16 }; targetDistance.current = 16; }}
          title="Reset Camera Angle"
        >
          <RotateCcw size={14} />
        </button>
      </div>
    </div>
  );
}
