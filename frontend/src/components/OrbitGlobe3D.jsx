import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { Eye, RotateCcw, Sun, Moon, Orbit } from 'lucide-react';

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

    // Earth Group
    const earthGroup = new THREE.Group();
    const earthRadius = 5.0;

    scene.add(earthGroup);
    earthGroupRef.current = earthGroup;

    const texLoader = new THREE.TextureLoader();

    // 1. Photorealistic NASA Blue Marble Earth Surface & Specular Oceans
    const earthMap = texLoader.load('/textures/earth/earth_atmos_2048.jpg');
    earthMap.colorSpace = THREE.SRGBColorSpace;
    const earthSpecular = texLoader.load('/textures/earth/earth_specular_2048.jpg');
    const earthNormal = texLoader.load('/textures/earth/earth_normal_2048.jpg');

    const earthGeo = new THREE.SphereGeometry(earthRadius, 64, 64);
    const earthMat = new THREE.MeshPhongMaterial({
      map: earthMap,
      specularMap: earthSpecular,
      specular: new THREE.Color(0x334d66),
      shininess: 28,
      normalMap: earthNormal,
      normalScale: new THREE.Vector2(0.85, 0.85),
    });
    const earthMesh = new THREE.Mesh(earthGeo, earthMat);
    earthGroup.add(earthMesh);

    // 2. High-Resolution Atmospheric Cloud Layer (Drifts independently)
    const cloudGeo = new THREE.SphereGeometry(earthRadius * 1.015, 64, 64);
    const cloudTex = texLoader.load('/textures/earth/earth_clouds_1024.png');
    const cloudMat = new THREE.MeshStandardMaterial({
      map: cloudTex,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const cloudMesh = new THREE.Mesh(cloudGeo, cloudMat);
    earthGroup.add(cloudMesh);
    cloudMeshRef.current = cloudMesh;

    // 3. Inner Atmospheric Rim Scatter (Daylight edge haze)
    const innerAtmoGeo = new THREE.SphereGeometry(earthRadius * 1.019, 64, 64);
    const innerAtmoMat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        void main() {
          float intensity = 1.05 - dot(vNormal, vec3(0.0, 0.0, 1.0));
          vec3 atmosphere = vec3(0.25, 0.65, 1.0) * pow(intensity, 2.8);
          gl_FragColor = vec4(atmosphere, intensity * 0.7);
        }
      `,
      blending: THREE.AdditiveBlending,
      side: THREE.FrontSide,
      transparent: true,
      depthWrite: false,
    });
    const innerAtmoMesh = new THREE.Mesh(innerAtmoGeo, innerAtmoMat);
    earthGroup.add(innerAtmoMesh);

    // 4. Outer Atmospheric Rayleigh Corona (Limb halo glow)
    const atmoGeo = new THREE.SphereGeometry(earthRadius * 1.12, 64, 64);
    const atmoMat = new THREE.ShaderMaterial({
      vertexShader: `
        varying vec3 vNormal;
        varying vec3 vPosition;
        void main() {
          vNormal = normalize(normalMatrix * normal);
          vPosition = (modelViewMatrix * vec4(position, 1.0)).xyz;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: `
        varying vec3 vNormal;
        varying vec3 vPosition;
        void main() {
          vec3 viewDir = normalize(-vPosition);
          float intensity = pow(0.68 - dot(vNormal, viewDir), 2.2);
          vec3 atmosphere = vec3(0.18, 0.62, 1.0) * intensity;
          gl_FragColor = vec4(atmosphere, intensity * 0.8);
        }
      `,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      transparent: true,
      depthWrite: false,
    });
    const atmoMesh = new THREE.Mesh(atmoGeo, atmoMat);
    earthGroup.add(atmoMesh);

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
        // Rotate Earth and Clouds (realistic orbital drift)
        if (earthGroupRef.current) {
          earthGroupRef.current.rotation.y += 0.00015;
        }
        if (cloudMeshRef.current) {
          cloudMeshRef.current.rotation.y += 0.00022; // Atmospheric winds drift over surface
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
        starsGeo?.dispose();
        starsMat?.dispose();
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
          <span style={{ color: '#38bdf8', fontWeight: '600' }}>SAT: ISS-25544</span>
          <span style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '4px',
            color: isSun ? 'var(--status-nominal)' : 'var(--status-caution)',
            background: isSun ? 'var(--status-nominal-bg)' : 'var(--status-caution-bg)',
            padding: '2px 5px',
            borderRadius: 'var(--radius-xs)',
            fontSize: '0.625rem'
          }}>
            {isSun ? <Sun size={11} /> : <Moon size={11} />}
            {isSun ? 'SUNLIT' : 'ECLIPSE'}
          </span>
        </div>
        <div style={{ color: 'var(--text-muted)' }}>LAT: <span style={{ color: 'var(--text-main)' }}>{satLat >= 0 ? `${satLat}° N` : `${Math.abs(satLat)}° S`}</span></div>
        <div style={{ color: 'var(--text-muted)' }}>LON: <span style={{ color: 'var(--text-main)' }}>{satLon >= 0 ? `${satLon}° E` : `${Math.abs(satLon)}° W`}</span></div>
        <div style={{ color: 'var(--text-muted)' }}>ALT: <span style={{ color: '#38bdf8' }}>{satAlt} km</span> | VEL: <span style={{ color: '#38bdf8' }}>{velMag} km/s</span></div>
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