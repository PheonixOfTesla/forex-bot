"use strict";
/* ===========================================================================
   THE VILLAGE - a sunlit Greek island you can walk around

   Everything here is generated at runtime: no models, no textures, no assets
   to download. Characters are built from spheres and cylinders in a toon
   material, the island is scattered procedurally from a seeded shuffle so
   every player sees the same village, and shadows are cheap painted blobs
   rather than real shadow maps.
   =========================================================================== */

const Village = (() => {

  const SKY_TOP   = 0x2E8BC9;
  const SKY_BOT   = 0xCFEAF6;
  const SEA       = 0x2C7DA0;
  const SAND      = 0xE9D5A0;
  const GRASS     = 0x86A85E;
  const PLAZA     = 0xEFE3C4;
  const WHITEWASH = 0xFBF7EF;
  const DOME      = 0x2E6FA8;
  const TERRA     = 0xCF6A47;
  const TRUNK     = 0x8A6242;
  const LEAF      = 0x6F9350;
  const GOLD      = 0xE8A33D;

  const ISLAND_RADIUS  = 30;
  const VILLAGE_RADIUS = 26;

  let renderer, scene, camera, sun;
  let toonGradient = null;
  let avatars = new Map();       // pid -> rig
  let clock = 0;
  let quality = 1, fpsAvg = 60, lastFrame = performance.now();
  let camYaw = 0, camPitch = 0.52, camDist = 12.5;
  let followPid = null;
  let shakeAmount = 0, flashAmount = 0;
  let flashColor = { r: 1, g: 0.3, b: 0.25 };
  const flashOverlay = { mesh: null };

  /* A deterministic shuffle so every device builds the identical island. */
  function seeded(seed){
    let s = seed >>> 0;
    return () => {
      s = (s * 1664525 + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }

  /* ------------------------------------------------------------------
     Materials
     ------------------------------------------------------------------ */
  function gradientMap(){
    if (toonGradient) return toonGradient;
    // Three flat steps of light: the whole cartoon look rests on this.
    const data = new Uint8Array([90, 90, 90, 175, 175, 175, 255, 255, 255]);
    const tex = new THREE.DataTexture(data, 3, 1, THREE.RGBFormat);
    tex.minFilter = tex.magFilter = THREE.NearestFilter;
    tex.generateMipmaps = false;
    tex.needsUpdate = true;
    toonGradient = tex;
    return tex;
  }

  function toon(color, opts){
    return new THREE.MeshToonMaterial(
      Object.assign({ color, gradientMap: gradientMap() }, opts || {}));
  }

  /* ------------------------------------------------------------------
     Island
     ------------------------------------------------------------------ */
  function buildSky(){
    const geo = new THREE.SphereGeometry(180, 24, 16);
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: {
        top:    { value: new THREE.Color(SKY_TOP) },
        bottom: { value: new THREE.Color(SKY_BOT) }
      },
      vertexShader: `
        varying float vH;
        void main(){
          vec4 w = modelMatrix * vec4(position, 1.0);
          vH = normalize(w.xyz).y;
          gl_Position = projectionMatrix * viewMatrix * w;
        }`,
      fragmentShader: `
        varying float vH;
        uniform vec3 top; uniform vec3 bottom;
        void main(){
          float t = smoothstep(-0.06, 0.55, vH);
          gl_FragColor = vec4(mix(bottom, top, t), 1.0);
        }`
    });
    scene.add(new THREE.Mesh(geo, mat));
  }

  function buildIsland(){
    // Sea, out to the horizon.
    const sea = new THREE.Mesh(
      new THREE.CircleGeometry(170, 48),
      new THREE.MeshBasicMaterial({ color: SEA })
    );
    sea.rotation.x = -Math.PI/2;
    sea.position.y = -0.85;
    scene.add(sea);

    // Beach, then grass, then the paved square in the middle.
    const beach = new THREE.Mesh(new THREE.CircleGeometry(ISLAND_RADIUS + 3.5, 56), toon(SAND));
    beach.rotation.x = -Math.PI/2;
    beach.position.y = -0.34;
    scene.add(beach);

    const grass = new THREE.Mesh(new THREE.CircleGeometry(ISLAND_RADIUS - 1.5, 56), toon(GRASS));
    grass.rotation.x = -Math.PI/2;
    grass.position.y = -0.12;
    scene.add(grass);

    const plaza = new THREE.Mesh(new THREE.CircleGeometry(11, 40), toon(PLAZA));
    plaza.rotation.x = -Math.PI/2;
    plaza.position.y = -0.05;
    scene.add(plaza);

    // A ring of paving detail so the square does not read as a flat disc.
    for (let i = 0; i < 3; i++){
      const r = 4.5 + i * 3.0;
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(r, r + 0.16, 48),
        new THREE.MeshBasicMaterial({ color: 0xD9C79B, transparent: true, opacity: 0.75 })
      );
      ring.rotation.x = -Math.PI/2;
      ring.position.y = -0.04;
      scene.add(ring);
    }
  }

  function buildHouse(rand, x, z){
    const g = new THREE.Group();
    const w = 2.6 + rand() * 1.8;
    const h = 2.4 + rand() * 1.7;
    const d = 2.6 + rand() * 1.6;

    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), toon(WHITEWASH));
    body.position.y = h/2;
    g.add(body);

    // Half the houses get the blue dome, the rest a terracotta roof.
    if (rand() > 0.5){
      const dome = new THREE.Mesh(
        new THREE.SphereGeometry(w * 0.46, 16, 10, 0, Math.PI*2, 0, Math.PI/2), toon(DOME));
      dome.position.y = h;
      g.add(dome);
    } else {
      const roof = new THREE.Mesh(new THREE.ConeGeometry(w * 0.78, 1.15, 4), toon(TERRA));
      roof.position.y = h + 0.55;
      roof.rotation.y = Math.PI/4;
      g.add(roof);
    }

    // A door and a window, so the scale reads as a building.
    const door = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 1.15), toon(0x4A6FA0));
    door.position.set(0, 0.58, d/2 + 0.01);
    g.add(door);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.5), toon(0x7FB4D8));
    win.position.set(w * 0.28, h * 0.66, d/2 + 0.01);
    g.add(win);

    g.position.set(x, 0, z);
    g.rotation.y = rand() * Math.PI * 2;
    scene.add(g);
  }

  function buildTree(rand, x, z){
    const g = new THREE.Group();
    const th = 1.5 + rand() * 1.0;
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.24, th, 7), toon(TRUNK));
    trunk.position.y = th/2;
    g.add(trunk);
    // A few overlapping blobs make a nicer canopy than one sphere.
    for (let i = 0; i < 3; i++){
      const r = 0.85 + rand() * 0.55;
      const blob = new THREE.Mesh(new THREE.SphereGeometry(r, 10, 8), toon(LEAF));
      blob.position.set((rand()-0.5) * 1.1, th + 0.25 + rand() * 0.6, (rand()-0.5) * 1.1);
      blob.scale.y = 0.82;
      g.add(blob);
    }
    g.position.set(x, 0, z);
    scene.add(g);
  }

  /* The loom monument in the middle of the square - the game's namesake,
     and the thing everyone gathers around to vote. */
  function buildMonument(){
    const g = new THREE.Group();
    const base = new THREE.Mesh(new THREE.CylinderGeometry(2.0, 2.4, 0.5, 24), toon(0xE4D6B0));
    base.position.y = 0.25;
    g.add(base);
    const step = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.7, 0.4, 24), toon(0xEFE3C4));
    step.position.y = 0.68;
    g.add(step);

    const column = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.5, 3.4, 18), toon(WHITEWASH));
    column.position.y = 2.55;
    g.add(column);

    // Flutes down the column.
    for (let i = 0; i < 10; i++){
      const a = (i/10) * Math.PI * 2;
      const flute = new THREE.Mesh(new THREE.BoxGeometry(0.07, 3.3, 0.07), toon(0xE6DDCB));
      flute.position.set(Math.cos(a) * 0.44, 2.55, Math.sin(a) * 0.44);
      g.add(flute);
    }

    const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.5, 0.28, 18), toon(0xF4EEE0));
    cap.position.y = 4.35;
    g.add(cap);

    const spindle = new THREE.Mesh(new THREE.SphereGeometry(0.46, 18, 14), toon(GOLD));
    spindle.position.y = 4.95;
    g.add(spindle);
    monumentSpindle = spindle;

    scene.add(g);
  }
  let monumentSpindle = null;

  function scatter(){
    const rand = seeded(20250815);
    // Houses ring the square, trees fill the gaps out to the beach.
    for (let i = 0; i < 14; i++){
      const a = (i / 14) * Math.PI * 2 + rand() * 0.2;
      const r = 15 + rand() * 8;
      buildHouse(rand, Math.cos(a) * r, Math.sin(a) * r);
    }
    for (let i = 0; i < 26; i++){
      const a = rand() * Math.PI * 2;
      const r = 12.5 + rand() * 15;
      buildTree(rand, Math.cos(a) * r, Math.sin(a) * r);
    }
    // Benches around the plaza edge to make it feel inhabited.
    for (let i = 0; i < 6; i++){
      const a = (i / 6) * Math.PI * 2 + 0.5;
      const bench = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.24, 0.5), toon(0xB07A4E));
      bench.position.set(Math.cos(a) * 9.6, 0.42, Math.sin(a) * 9.6);
      bench.rotation.y = -a;
      scene.add(bench);
      const legs = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.4, 0.32), toon(0x9A683F));
      legs.position.set(Math.cos(a) * 9.6, 0.2, Math.sin(a) * 9.6);
      legs.rotation.y = -a;
      scene.add(legs);
    }
  }

  /* ------------------------------------------------------------------
     Characters
     ------------------------------------------------------------------ */
  let blobShadowTex = null;
  function blobShadow(){
    if (blobShadowTex) return blobShadowTex;
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const g = c.getContext("2d");
    const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grd.addColorStop(0,   "rgba(40,30,20,0.42)");
    grd.addColorStop(0.6, "rgba(40,30,20,0.18)");
    grd.addColorStop(1,   "rgba(40,30,20,0)");
    g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
    blobShadowTex = new THREE.CanvasTexture(c);
    return blobShadowTex;
  }

  function nameTag(name, tint){
    const c = document.createElement("canvas");
    c.width = 320; c.height = 80;
    const g = c.getContext("2d");
    g.clearRect(0, 0, 320, 80);
    const text = (name || "").slice(0, 14);
    g.font = "700 40px ui-rounded, -apple-system, 'Segoe UI', system-ui, sans-serif";
    g.textAlign = "center"; g.textBaseline = "middle";
    const w = Math.min(300, g.measureText(text).width + 40);

    // Rounded pill behind the name so it reads against sky, sea or grass.
    g.fillStyle = tint || "rgba(43,36,56,0.82)";
    const x = (320 - w) / 2, y = 14, h = 52, r = 26;
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath(); g.fill();

    g.fillStyle = "#FFFFFF";
    g.fillText(text, 160, 41);
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    return tex;
  }

  /* One Eidolon: head, face, hair, body, arms, legs, shadow, name tag. */
  function buildRig(player, eidolon){
    const rig = new THREE.Group();
    const colors = (eidolon && eidolon.colors) || {};
    const skin  = new THREE.Color(colors.skin  || 0xEBBE94);
    const hair  = new THREE.Color(colors.hair  || 0x3A2A1E);
    const shirt = new THREE.Color(colors.shirt || 0x3B82C4);

    const skinMat  = toon(skin);
    const shirtMat = toon(shirt);
    const hairMat  = toon(hair);
    const pantMat  = toon(new THREE.Color(shirt).multiplyScalar(0.55));

    // Body: a soft tapered barrel. Wii proportions - small body, big head.
    const body = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.42, 0.86, 14), shirtMat);
    body.position.y = 0.92;
    rig.add(body);
    const collar = new THREE.Mesh(new THREE.SphereGeometry(0.34, 14, 10), shirtMat);
    collar.position.y = 1.3; collar.scale.y = 0.6;
    rig.add(collar);

    // Head, oversized on purpose.
    const head = new THREE.Group();
    head.position.y = 1.78;
    const skull = new THREE.Mesh(new THREE.SphereGeometry(0.56, 22, 18), skinMat);
    skull.scale.set(1, 1.06, 0.94);
    head.add(skull);

    // The photo sits on a slightly domed disc on the front of the head.
    const faceGeo = new THREE.SphereGeometry(0.545, 26, 20,
      -Math.PI/2 - 0.72, 1.44, Math.PI * 0.18, Math.PI * 0.64);
    const faceMat = new THREE.MeshBasicMaterial({ transparent: true });
    if (eidolon && eidolon.faceTexture) faceMat.map = eidolon.faceTexture;
    else faceMat.color = skin;
    const face = new THREE.Mesh(faceGeo, faceMat);
    face.rotation.y = Math.PI;
    face.scale.set(1, 1.06, 0.94);
    head.add(face);

    // A hair shell over the back and top of the skull.
    const hairMesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.585, 20, 16, 0, Math.PI*2, 0, Math.PI * 0.56), hairMat);
    hairMesh.scale.set(1, 1.02, 0.98);
    hairMesh.position.y = 0.02;
    head.add(hairMesh);

    rig.add(head);

    // Limbs, pivoted at the shoulder and hip so they swing properly.
    function limb(len, rad, mat, x, y){
      const pivot = new THREE.Group();
      pivot.position.set(x, y, 0);
      const m = new THREE.Mesh(new THREE.CylinderGeometry(rad, rad * 0.86, len, 10), mat);
      m.position.y = -len/2;
      pivot.add(m);
      const tip = new THREE.Mesh(new THREE.SphereGeometry(rad * 1.02, 10, 8), mat);
      tip.position.y = -len;
      pivot.add(tip);
      rig.add(pivot);
      return pivot;
    }
    const armL = limb(0.62, 0.13, skinMat, -0.44, 1.24);
    const armR = limb(0.62, 0.13, skinMat,  0.44, 1.24);
    const legL = limb(0.55, 0.155, pantMat, -0.18, 0.52);
    const legR = limb(0.55, 0.155, pantMat,  0.18, 0.52);

    // Painted shadow: far cheaper than a shadow map, and it suits the look.
    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(1.5, 1.5),
      new THREE.MeshBasicMaterial({ map: blobShadow(), transparent: true, depthWrite: false })
    );
    shadow.rotation.x = -Math.PI/2;
    shadow.position.y = 0.02;
    rig.add(shadow);

    const tag = new THREE.Sprite(new THREE.SpriteMaterial({
      map: nameTag(player.name), transparent: true, depthWrite: false, depthTest: false
    }));
    tag.scale.set(1.7, 0.43, 1);
    // Stagger the height per player so tags on bunched-up characters do not
    // land exactly on top of each other.
    tag.position.y = 2.62 + ((player.seat || 0) % 4) * 0.32;
    rig.add(tag);

    // A ring under the feet, used to mark who you have voted for.
    const marker = new THREE.Mesh(
      new THREE.RingGeometry(0.52, 0.68, 24),
      new THREE.MeshBasicMaterial({ color: 0xE04B3C, transparent: true, opacity: 0, side: THREE.DoubleSide })
    );
    marker.rotation.x = -Math.PI/2;
    marker.position.y = 0.03;
    rig.add(marker);

    scene.add(rig);
    return {
      group: rig, head, face, faceMat, body, tag, marker, shadow,
      armL, armR, legL, legR,
      pid: player.pid,
      // Interpolation targets, fed by the movement frame.
      x: player.x || 0, z: player.z || 0, angle: 0,
      tx: player.x || 0, tz: player.z || 0, ta: 0,
      moving: false, alive: true, phase: Math.random() * 10,
      emote: "", emoteT: 0, ghost: false
    };
  }

  /* ------------------------------------------------------------------
     Public surface
     ------------------------------------------------------------------ */
  function init(canvas){
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    quality = Math.min(window.devicePixelRatio || 1, 2);
    renderer.setPixelRatio(quality);
    renderer.setSize(innerWidth, innerHeight, false);
    renderer.setClearColor(SKY_BOT, 1);

    scene = new THREE.Scene();
    scene.fog = new THREE.Fog(SKY_BOT, 52, 130);
    camera = new THREE.PerspectiveCamera(58, innerWidth/innerHeight, 0.1, 400);

    // Warm sun from above, cool bounce from the sky and sand.
    scene.add(new THREE.HemisphereLight(0xDCF0FF, 0xE0C98F, 0.95));
    sun = new THREE.DirectionalLight(0xFFF3D6, 0.85);
    sun.position.set(14, 22, 9);
    scene.add(sun);

    buildSky();
    buildIsland();
    scatter();
    buildMonument();

    addEventListener("resize", resize, { passive: true });
    renderer.setAnimationLoop(frame);
  }

  function resize(){
    if (!renderer) return;
    camera.aspect = innerWidth/innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight, false);
  }

  /* Rebuild the cast when the roster or somebody's Eidolon changes. */
  function sync(players, eidolonMap){
    const seen = new Set();
    players.forEach(p => {
      seen.add(p.pid);
      let rig = avatars.get(p.pid);
      const raw = eidolonMap && eidolonMap[p.pid];
      // Include the colours, not just the face: changing only a shirt would
      // otherwise leave the old rig standing.
      const stamp = raw
        ? [(raw.face || "").length, raw.skin, raw.hair, raw.shirt].join("|")
        : "none";
      if (rig && rig.stamp !== stamp){
        scene.remove(rig.group);
        avatars.delete(p.pid);
        rig = null;
      }
      if (!rig){
        rig = buildRig(p, raw ? {
          colors: raw,                                  // skin/hair/shirt live on the record
          faceTexture: raw.faceTexture || null
        } : null);
        rig.stamp = stamp;
        avatars.set(p.pid, rig);
      }
      rig.alive = p.alive;
    });
    // Anyone who left the room leaves the island.
    [...avatars.keys()].forEach(pid => {
      if (!seen.has(pid)){
        scene.remove(avatars.get(pid).group);
        avatars.delete(pid);
      }
    });
  }

  /* The movement frame: [pid, x, z, angle, moving, alive, emote] */
  function applyPositions(rows, selfPid){
    rows.forEach(([pid, x, z, a, m, alive, emote]) => {
      const rig = avatars.get(pid);
      if (!rig) return;
      if (pid === selfPid) return;          // your own body is driven locally
      rig.tx = x; rig.tz = z; rig.ta = a;
      rig.moving = !!m;
      rig.alive = !!alive;
      if (emote && emote !== rig.emote){ rig.emote = emote; rig.emoteT = 0; }
      if (!emote) rig.emote = "";
    });
  }

  function setSelf(pid, x, z, angle, moving){
    const rig = avatars.get(pid);
    if (!rig) return;
    rig.x = rig.tx = x; rig.z = rig.tz = z;
    rig.angle = rig.ta = angle;
    rig.moving = moving;
  }

  function setFollow(pid){ followPid = pid; }
  function selfRig(){ return avatars.get(followPid); }

  /* How far the local player has to be pushed to stop standing inside anyone.
     Returns a small nudge rather than hard collision, so crowds stay soft. */
  function separation(pid, x, z){
    let px = 0, pz = 0;
    // Heads are wide, so this has to be comfortably bigger than a body radius
    // or a crowd still reads as one pile with overlapping name tags.
    const MIN = 1.9;
    avatars.forEach((rig, other) => {
      if (other === pid) return;
      const dx = x - rig.x, dz = z - rig.z;
      const d = Math.hypot(dx, dz);
      if (d > 0.0001 && d < MIN){
        const push = (MIN - d) / MIN;
        px += (dx/d) * push;
        pz += (dz/d) * push;
      }
    });
    return [px, pz];
  }

  function setMarkers(map){
    avatars.forEach((rig, pid) => {
      const on = map && map[pid];
      rig.marker.material.opacity += ((on ? 0.85 : 0) - rig.marker.material.opacity) * 0.25;
    });
  }

  function faceTextureFor(dataUrl){
    return new Promise(resolve => {
      const img = new Image();
      img.onload = () => {
        const tex = new THREE.CanvasTexture(img);
        tex.minFilter = THREE.LinearFilter;
        tex.needsUpdate = true;
        resolve(tex);
      };
      img.onerror = () => resolve(null);
      img.src = dataUrl;
    });
  }

  function flash(hexColor, amount){
    const c = new THREE.Color(hexColor);
    flashColor = { r: c.r, g: c.g, b: c.b };
    flashAmount = amount;
    shakeAmount = Math.min(1, amount);
  }

  function orbit(dx, dy){
    camYaw -= dx * 0.005;
    camPitch = Math.max(0.06, Math.min(1.05, camPitch + dy * 0.004));
  }
  function zoom(delta){ camDist = Math.max(4.5, Math.min(16, camDist + delta)); }
  function heading(){ return camYaw; }

  /* ------------------------------------------------------------------
     Animation
     ------------------------------------------------------------------ */
  function animateRig(rig, dt){
    // Ease toward the networked position so 7 frames a second look smooth.
    const k = 1 - Math.pow(0.0001, dt);
    rig.x += (rig.tx - rig.x) * k;
    rig.z += (rig.tz - rig.z) * k;
    let da = ((rig.ta - rig.angle + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
    rig.angle += da * Math.min(1, dt * 12);

    rig.group.position.set(rig.x, 0, rig.z);
    rig.group.rotation.y = rig.angle;

    const speed = rig.moving ? 1 : 0;
    rig.phase += dt * (rig.moving ? 9.5 : 2.2);
    const swing = Math.sin(rig.phase);

    // Walk cycle: opposite arm to leg, plus a bob and a slight forward lean.
    rig.legL.rotation.x =  swing * 0.85 * speed;
    rig.legR.rotation.x = -swing * 0.85 * speed;
    rig.armL.rotation.x = -swing * 0.7 * speed;
    rig.armR.rotation.x =  swing * 0.7 * speed;
    rig.group.position.y = Math.abs(Math.sin(rig.phase)) * 0.07 * speed;
    rig.body.rotation.x = speed * 0.09;

    // Idle: gentle breathing and a slow head sway.
    if (!rig.moving){
      const idle = Math.sin(rig.phase * 0.6);
      rig.body.scale.y = 1 + idle * 0.022;
      rig.head.position.y = 1.78 + idle * 0.02;
      rig.head.rotation.z = idle * 0.05;
      rig.armL.rotation.x = idle * 0.1;
      rig.armR.rotation.x = -idle * 0.1;
    } else {
      rig.body.scale.y = 1;
      rig.head.position.y = 1.78;
      rig.head.rotation.z = 0;
    }

    // Emotes override the arms for a couple of seconds.
    if (rig.emote){
      rig.emoteT += dt;
      const e = rig.emoteT;
      if (rig.emote === "wave"){
        rig.armR.rotation.x = -2.5;
        rig.armR.rotation.z = Math.sin(e * 11) * 0.5 - 0.3;
      } else if (rig.emote === "cheer"){
        rig.armL.rotation.x = rig.armR.rotation.x = -2.8;
        rig.group.position.y += Math.abs(Math.sin(e * 7)) * 0.28;
      } else if (rig.emote === "dance"){
        rig.group.rotation.y += Math.sin(e * 6) * 0.5;
        rig.group.position.y += Math.abs(Math.sin(e * 9)) * 0.22;
        rig.armL.rotation.x = -1.7 + Math.sin(e * 9) * 0.9;
        rig.armR.rotation.x = -1.7 - Math.sin(e * 9) * 0.9;
      } else if (rig.emote === "point"){
        rig.armR.rotation.x = -1.55;
        rig.armR.rotation.z = -0.12;
      } else if (rig.emote === "shrug"){
        rig.armL.rotation.z =  0.9; rig.armR.rotation.z = -0.9;
        rig.armL.rotation.x = -0.5; rig.armR.rotation.x = -0.5;
      } else if (rig.emote === "sit"){
        rig.group.position.y -= 0.42;
        rig.legL.rotation.x = -1.5; rig.legR.rotation.x = -1.5;
      }
      if (e > 3.2) rig.emote = "";
    } else {
      rig.armL.rotation.z = rig.armR.rotation.z = 0;
    }

    // The dead drift as translucent shades, and stop casting a shadow.
    const wantGhost = !rig.alive;
    if (wantGhost !== rig.ghost){
      rig.ghost = wantGhost;
      rig.group.traverse(o => {
        if (o.material && o.material !== rig.tag.material){
          o.material.transparent = true;
          o.material.opacity = wantGhost ? 0.42 : 1;
        }
      });
      rig.shadow.visible = !wantGhost;
    }
    if (wantGhost) rig.group.position.y += 0.35 + Math.sin(clock * 1.6 + rig.phase) * 0.12;
  }

  function updateCamera(dt){
    const me = avatars.get(followPid);
    const target = me
      ? new THREE.Vector3(me.x, 1.9, me.z)
      : new THREE.Vector3(0, 2.2, 0);

    if (!me){
      // Nobody to follow yet: drift around the monument.
      camYaw += dt * 0.09;
    }

    const d = me ? camDist : 17;
    const p = me ? camPitch : 0.42;
    const want = new THREE.Vector3(
      target.x + Math.sin(camYaw) * Math.cos(p) * d,
      target.y + Math.sin(p) * d,
      target.z + Math.cos(camYaw) * Math.cos(p) * d
    );
    // Never let the camera drop below the ground.
    want.y = Math.max(1.1, want.y);

    camera.position.lerp(want, 1 - Math.pow(0.0005, dt));
    const s = shakeAmount * shakeAmount;
    camera.position.x += (Math.random()-0.5) * s * 0.5;
    camera.position.y += (Math.random()-0.5) * s * 0.5;
    camera.lookAt(target);
  }

  function frame(){
    const now = performance.now();
    const dt = Math.min(0.05, (now - lastFrame)/1000);
    lastFrame = now;
    clock += dt;

    fpsAvg = fpsAvg * 0.94 + (1/Math.max(dt, 0.001)) * 0.06;
    if (fpsAvg < 32 && quality > 1){ quality = 1; renderer.setPixelRatio(1); }

    if (monumentSpindle){
      monumentSpindle.rotation.y = clock * 0.6;
      monumentSpindle.position.y = 4.95 + Math.sin(clock * 1.4) * 0.09;
    }

    avatars.forEach(rig => animateRig(rig, dt));
    updateCamera(dt);

    shakeAmount = Math.max(0, shakeAmount - dt * 2.2);
    flashAmount = Math.max(0, flashAmount - dt * 1.6);

    // The flash is painted by the DOM layer, which is cheaper than a pass.
    const el = document.getElementById("flash");
    if (el){
      el.style.opacity = String(flashAmount * 0.62);
      el.style.background =
        `rgb(${flashColor.r*255|0},${flashColor.g*255|0},${flashColor.b*255|0})`;
    }

    renderer.render(scene, camera);
  }

  return {
    init, sync, applyPositions, setSelf, setFollow, selfRig, setMarkers,
    faceTextureFor, flash, orbit, zoom, heading, separation,
    VILLAGE_RADIUS
  };
})();
