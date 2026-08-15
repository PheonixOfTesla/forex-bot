"use strict";
/* ===========================================================================
   EIDOLON - the avatar system

   A component library rather than a single procedural blob: sculpted hair
   styles, drawn facial features, layered outfits, and a toon outline pass.
   Everything is generated at runtime, so there is nothing to download and
   nothing to license.

   Honest about the ceiling: Bitmoji and Fortnite avatars are hand-authored by
   artists. This is the same *structure* - a parts library driven by a
   customiser - built with geometry instead of art. It gets a long way, and it
   is the right skeleton to drop real artwork into later.

   One config object describes a character completely, so the maker preview and
   the characters walking around the island are built by the same code.
   =========================================================================== */

const Avatar = (() => {

  const INK = 0x2A2333;          // outline and line-art colour

  /* ---------------------------------------------------------------------
     Palettes
     --------------------------------------------------------------------- */
  const SKIN = ["#FFDCBC","#F2C9A0","#E8B187","#C68642","#A9673B","#8D5524","#63391F","#4A2A17"];
  const HAIR = ["#1C1410","#3B2417","#5A3825","#8B5A2B","#B87333","#D9A441","#E8C87A",
                "#B33A3A","#3B5BA5","#2E7D5B","#8E5FA8","#E86FA8","#9AA0A6","#F2EFE6"];
  const CLOTH = ["#E05B4B","#3B82C4","#4CAF6E","#E8A33D","#8E5FA8","#E86FA8","#38B2AC",
                 "#F2F0E6","#3A4657","#C7643C","#6E8E3F","#D64F7A"];
  const PANTS = ["#3A4657","#2F3A46","#5A6B7D","#7A6A55","#31445E","#4A3B52","#8A8175","#2B2438"];
  const SHOES = ["#2B2438","#F2F0E6","#E05B4B","#3B82C4","#7A6A55","#4CAF6E"];

  const HAIR_STYLES = ["crop","buzz","bob","long","ponytail","curls","bun","topknot"];
  const EYE_STYLES  = ["round","almond","wide","happy","sleepy","wink"];
  const BROW_STYLES = ["soft","flat","arched","thick"];
  const MOUTH_STYLES = ["smile","grin","smirk","open","calm"];

  function defaults(){
    const pick = (a) => a[Math.floor(Math.random()*a.length)];
    return {
      skin: pick(SKIN), hair: pick(HAIR), hairStyle: pick(HAIR_STYLES),
      shirt: pick(CLOTH), pants: pick(PANTS), shoes: pick(SHOES),
      eyes: pick(EYE_STYLES), brows: pick(BROW_STYLES), mouth: pick(MOUTH_STYLES),
      glasses: Math.random() < 0.22, face: null
    };
  }

  /* ---------------------------------------------------------------------
     The face

     Drawn on a transparent canvas holding only the features, so the head mesh
     supplies the skin tone and changing skin never needs a redraw.
     --------------------------------------------------------------------- */
  const S = 512;

  function faceTexture(cfg){
    const c = document.createElement("canvas");
    c.width = c.height = S;
    const g = c.getContext("2d");
    g.clearRect(0, 0, S, S);

    // A photo, if the player supplied one, sits under the drawn features.
    if (cfg.face && cfg.faceImage){
      g.save();
      g.beginPath(); g.arc(S/2, S/2, S/2, 0, Math.PI*2); g.clip();
      g.drawImage(cfg.faceImage, 0, 0, S, S);
      g.restore();
      return finish(c);
    }

    const eyeY = S * 0.455, eyeDx = S * 0.142, eyeR = S * 0.060;
    drawBrows(g, cfg, eyeY - eyeR * 2.5, eyeDx);
    drawEyes(g, cfg, eyeY, eyeDx, eyeR);
    drawNose(g, cfg, eyeY + eyeR * 1.7);
    drawMouth(g, cfg, S * 0.655);
    drawBlush(g, eyeY + eyeR * 1.9, eyeDx * 1.55);
    if (cfg.glasses) drawGlasses(g, eyeY, eyeDx, eyeR);
    return finish(c);
  }

  function finish(canvas){
    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    tex.needsUpdate = true;
    return tex;
  }

  function drawEyes(g, cfg, y, dx, r){
    [-1, 1].forEach(side => {
      const x = S/2 + side * dx;
      const closed = cfg.eyes === "happy" || (cfg.eyes === "wink" && side === 1);

      if (closed){
        // A closed, upturned lash line reads as a smile from across a room.
        g.strokeStyle = "#2A2333";
        g.lineWidth = r * 0.42; g.lineCap = "round";
        g.beginPath();
        g.arc(x, y + r*0.35, r * 0.95, Math.PI * 1.12, Math.PI * 1.88);
        g.stroke();
        return;
      }

      let rx = r, ry = r * 1.12;
      if (cfg.eyes === "almond"){ rx = r * 1.06; ry = r * 0.82; }
      if (cfg.eyes === "wide")  { rx = r * 1.10; ry = r * 1.30; }
      if (cfg.eyes === "sleepy"){ rx = r * 1.02; ry = r * 0.66; }

      // White, iris, pupil, highlight - the four layers that make an eye read.
      g.fillStyle = "#FFFFFF";
      g.beginPath(); g.ellipse(x, y, rx, ry, 0, 0, Math.PI*2); g.fill();

      g.fillStyle = cfg.eyeColor || "#5B4636";
      g.beginPath(); g.ellipse(x, y + ry*0.06, rx*0.62, ry*0.62, 0, 0, Math.PI*2); g.fill();

      g.fillStyle = "#1C1622";
      g.beginPath(); g.ellipse(x, y + ry*0.06, rx*0.34, ry*0.36, 0, 0, Math.PI*2); g.fill();

      g.fillStyle = "rgba(255,255,255,0.95)";
      g.beginPath(); g.ellipse(x - rx*0.26, y - ry*0.32, rx*0.20, ry*0.20, 0, 0, Math.PI*2); g.fill();

      // Lash line across the top, heavier on the outside.
      g.strokeStyle = "#2A2333";
      g.lineWidth = r * 0.20; g.lineCap = "round";
      g.beginPath();
      g.ellipse(x, y, rx, ry, 0, Math.PI * 1.05, Math.PI * 1.95);
      g.stroke();
    });
  }

  function drawBrows(g, cfg, y, dx){
    const w = S * 0.115;
    let thickness = S * 0.020, lift = 0, tilt = 0;
    if (cfg.brows === "thick")  thickness = S * 0.032;
    if (cfg.brows === "arched"){ lift = -S * 0.012; tilt = 0.16; }
    if (cfg.brows === "flat")   tilt = 0;
    else if (cfg.brows === "soft") tilt = 0.09;

    g.strokeStyle = shade(cfg.hair, -0.18);
    g.lineWidth = thickness; g.lineCap = "round";
    [-1, 1].forEach(side => {
      const x = S/2 + side * dx;
      g.beginPath();
      g.moveTo(x - w/2, y + lift + tilt * w * side * 0.35);
      g.quadraticCurveTo(x, y + lift - w * (cfg.brows === "arched" ? 0.42 : 0.24),
                         x + w/2, y + lift - tilt * w * side * 0.35);
      g.stroke();
    });
  }

  function drawNose(g, cfg, y){
    g.strokeStyle = "rgba(90,60,45,0.45)";
    g.lineWidth = S * 0.013; g.lineCap = "round";
    g.beginPath();
    g.moveTo(S/2 - S*0.012, y);
    g.quadraticCurveTo(S/2 + S*0.016, y + S*0.030, S/2 - S*0.006, y + S*0.040);
    g.stroke();
  }

  function drawMouth(g, cfg, y){
    g.lineCap = "round"; g.lineJoin = "round";
    const w = S * 0.115;

    if (cfg.mouth === "open"){
      g.fillStyle = "#8E3B3B";
      g.beginPath(); g.ellipse(S/2, y + S*0.012, w*0.72, S*0.052, 0, 0, Math.PI*2); g.fill();
      g.fillStyle = "#FFFFFF";
      g.beginPath();
      g.ellipse(S/2, y - S*0.028, w*0.62, S*0.020, 0, 0, Math.PI*2);
      g.fill();
      return;
    }
    if (cfg.mouth === "grin"){
      g.fillStyle = "#FFFFFF";
      g.strokeStyle = "#2A2333"; g.lineWidth = S*0.016;
      g.beginPath();
      g.moveTo(S/2 - w, y - S*0.010);
      g.quadraticCurveTo(S/2, y + S*0.062, S/2 + w, y - S*0.010);
      g.closePath(); g.fill(); g.stroke();
      return;
    }
    g.strokeStyle = "#7A3B32";
    g.lineWidth = S * 0.019;
    g.beginPath();
    if (cfg.mouth === "smirk"){
      g.moveTo(S/2 - w*0.75, y);
      g.quadraticCurveTo(S/2, y + S*0.030, S/2 + w*0.95, y - S*0.018);
    } else if (cfg.mouth === "calm"){
      g.moveTo(S/2 - w*0.6, y);
      g.quadraticCurveTo(S/2, y + S*0.012, S/2 + w*0.6, y);
    } else {
      g.moveTo(S/2 - w*0.85, y - S*0.008);
      g.quadraticCurveTo(S/2, y + S*0.055, S/2 + w*0.85, y - S*0.008);
    }
    g.stroke();
  }

  function drawBlush(g, y, dx){
    g.fillStyle = "rgba(228,110,105,0.26)";
    [-1, 1].forEach(side => {
      g.beginPath();
      g.ellipse(S/2 + side*dx, y, S*0.055, S*0.034, 0, 0, Math.PI*2);
      g.fill();
    });
  }

  function drawGlasses(g, y, dx, r){
    g.strokeStyle = "#2A2333";
    g.lineWidth = S * 0.014;
    [-1, 1].forEach(side => {
      const x = S/2 + side*dx;
      g.beginPath();
      g.roundRect ? g.roundRect(x - r*1.5, y - r*1.25, r*3, r*2.5, r*0.7)
                  : g.rect(x - r*1.5, y - r*1.25, r*3, r*2.5);
      g.stroke();
    });
    g.beginPath();
    g.moveTo(S/2 - dx + r*1.5, y);
    g.lineTo(S/2 + dx - r*1.5, y);
    g.stroke();
  }

  /* Lighten or darken a hex colour. */
  function shade(hex, amount){
    const n = parseInt(String(hex).slice(1), 16);
    let r = (n>>16)&255, g = (n>>8)&255, b = n&255;
    const t = amount < 0 ? 0 : 255;
    const p = Math.abs(amount);
    r = Math.round((t - r) * p + r);
    g = Math.round((t - g) * p + g);
    b = Math.round((t - b) * p + b);
    return "#" + ((1<<24) + (r<<16) + (g<<8) + b).toString(16).slice(1);
  }

  /* ---------------------------------------------------------------------
     Geometry
     --------------------------------------------------------------------- */
  let ramp = null;
  function gradientMap(){
    if (ramp) return ramp;
    // Five steps rather than three: three bands make a limb read as a flat
    // panel, five keeps the toon look while letting cylinders read as round.
    const data = new Uint8Array([104,104,104, 150,150,150, 190,190,190, 226,226,226, 255,255,255]);
    ramp = new THREE.DataTexture(data, 5, 1, THREE.RGBFormat);
    ramp.minFilter = ramp.magFilter = THREE.NearestFilter;
    ramp.generateMipmaps = false;
    ramp.needsUpdate = true;
    return ramp;
  }

  function toon(color){
    return new THREE.MeshToonMaterial({ color: new THREE.Color(color), gradientMap: gradientMap() });
  }

  /* The inverted-hull outline: the single biggest quality jump available
     without art. Draw the shape again, inside out and slightly bigger, in ink.
     Applied only to the large silhouette pieces to keep the draw count sane. */
  function outlined(geo, mat, thickness){
    const group = new THREE.Group();
    const solid = new THREE.Mesh(geo, mat);
    group.add(solid);
    const ink = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({
      color: INK, side: THREE.BackSide
    }));
    ink.scale.setScalar(1 + (thickness || 0.055));
    group.add(ink);
    group.userData.solid = solid;
    return group;
  }

  /* --- hair ------------------------------------------------------------ */
  function buildHair(style, color, R){
    const g = new THREE.Group();
    const mat = toon(color);
    const cap = (coverage, scaleY, lift) => {
      const shell = outlined(
        new THREE.SphereGeometry(R * 1.05, 24, 18, 0, Math.PI*2, 0, Math.PI * coverage),
        mat, 0.038);
      shell.scale.set(1, scaleY, 1);
      shell.position.y = lift || 0;
      // Nudged back so the fringe clears the brow rather than covering the eyes.
      shell.position.z = -R * 0.05;
      g.add(shell);
      return shell;
    };

    if (style === "buzz"){ cap(0.40, 0.94, 0); }
    else if (style === "crop"){ cap(0.45, 1.0, 0.01); }
    else if (style === "bob"){
      cap(0.48, 1.0, 0.01);
      [-1, 1].forEach(s => {
        const side = outlined(new THREE.SphereGeometry(R*0.42, 14, 12), mat, 0.04);
        side.position.set(s * R * 0.82, -R * 0.34, 0);
        side.scale.set(0.62, 1.25, 0.9);
        g.add(side);
      });
    }
    else if (style === "long"){
      cap(0.47, 1.0, 0.01);
      const back = outlined(new THREE.SphereGeometry(R*0.82, 16, 14), mat, 0.04);
      back.position.set(0, -R * 0.60, -R * 0.22);
      back.scale.set(0.94, 1.35, 0.72);
      g.add(back);
    }
    else if (style === "ponytail"){
      cap(0.44, 1.0, 0.01);
      const tail = outlined(new THREE.SphereGeometry(R*0.34, 14, 12), mat, 0.045);
      tail.position.set(0, -R * 0.28, -R * 1.02);
      tail.scale.set(0.72, 1.9, 0.72);
      tail.rotation.x = -0.35;
      g.add(tail);
    }
    else if (style === "curls"){
      cap(0.40, 0.92, 0.01);
      for (let i = 0; i < 9; i++){
        const a = (i/9) * Math.PI * 2;
        const curl = outlined(new THREE.SphereGeometry(R*0.30, 10, 9), mat, 0.05);
        curl.position.set(Math.cos(a) * R * 0.78, R * 0.34 + Math.sin(i*2.1) * R * 0.16,
                          Math.sin(a) * R * 0.78);
        g.add(curl);
      }
    }
    else if (style === "bun"){
      cap(0.44, 1.0, 0.01);
      const bun = outlined(new THREE.SphereGeometry(R*0.36, 14, 12), mat, 0.05);
      bun.position.set(0, R * 0.92, -R * 0.30);
      g.add(bun);
    }
    else if (style === "topknot"){
      cap(0.38, 0.9, 0.01);
      const knot = outlined(new THREE.SphereGeometry(R*0.24, 12, 10), mat, 0.055);
      knot.position.set(0, R * 1.05, 0);
      knot.scale.set(1, 1.5, 1);
      g.add(knot);
    }
    return g;
  }

  /* --- the whole character -------------------------------------------- */
  function build(cfg, opts){
    const o = opts || {};
    const outline = o.outline !== false;
    const root = new THREE.Group();
    // Everything hangs off this, lifted so the soles rest on y = 0 rather
    // than sinking the feet through the ground.
    const rig = new THREE.Group();
    rig.position.y = 0.10;
    root.add(rig);

    const skinMat  = toon(cfg.skin);
    const shirtMat = toon(cfg.shirt);
    const pantMat  = toon(cfg.pants);
    const shoeMat  = toon(cfg.shoes);

    const wrap = outline ? outlined : (geo, mat) => new THREE.Mesh(geo, mat);
    const HEAD_R = 0.50;

    /* Torso: a tapered barrel with a collar, so clothing reads as clothing. */
    const torso = wrap(new THREE.CylinderGeometry(0.27, 0.335, 0.74, 18), shirtMat, 0.075);
    torso.position.y = 1.06;
    rig.add(torso);

    const collar = wrap(new THREE.SphereGeometry(0.275, 16, 12), shirtMat, 0.075);
    collar.position.y = 1.40; collar.scale.set(1, 0.55, 1);
    rig.add(collar);

    // A short neck stops the head reading as a ball balanced on a barrel.
    const neck = wrap(new THREE.CylinderGeometry(0.115, 0.125, 0.16, 12), skinMat, 0.10);
    neck.position.y = 1.51;
    rig.add(neck);

    const hips = wrap(new THREE.CylinderGeometry(0.325, 0.275, 0.20, 16), pantMat, 0.075);
    hips.position.y = 0.60;
    rig.add(hips);

    /* Head. */
    const head = new THREE.Group();
    head.position.y = 1.90;
    const skull = wrap(new THREE.SphereGeometry(HEAD_R, 26, 20), skinMat, 0.052);
    skull.scale.set(1, 1.07, 0.95);
    head.add(skull);

    // The drawn features sit on a shallow cap across the front of the head.
    const faceGeo = new THREE.SphereGeometry(HEAD_R * 1.008, 30, 24,
      -Math.PI/2 - 0.78, 1.56, Math.PI * 0.16, Math.PI * 0.66);
    const faceMat = new THREE.MeshBasicMaterial({
      transparent: true, map: cfg.faceTexture || faceTexture(cfg), depthWrite: false
    });
    const face = new THREE.Mesh(faceGeo, faceMat);
    face.rotation.y = Math.PI;
    face.scale.set(1, 1.07, 0.95);
    head.add(face);

    // Ears.
    [-1, 1].forEach(s => {
      const ear = wrap(new THREE.SphereGeometry(HEAD_R*0.17, 10, 8), skinMat, 0.06);
      ear.position.set(s * HEAD_R * 0.96, -HEAD_R*0.06, 0);
      ear.scale.set(0.55, 1, 0.8);
      head.add(ear);
    });

    head.add(buildHair(cfg.hairStyle, cfg.hair, HEAD_R));
    rig.add(head);

    /* Limbs, pivoted so they swing from shoulder and hip. */
    function limb(x, y, upperLen, lowerLen, upperMat, lowerMat, endMat, endScale, rad){
      const pivot = new THREE.Group();
      pivot.position.set(x, y, 0);

      const R0 = rad || 0.105;
      const upper = wrap(new THREE.CylinderGeometry(R0, R0*0.94, upperLen, 12), upperMat, 0.16);
      upper.position.y = -upperLen/2;
      pivot.add(upper);

      const knee = new THREE.Group();
      knee.position.y = -upperLen;
      const lower = wrap(new THREE.CylinderGeometry(R0*0.94, R0*0.88, lowerLen, 12), lowerMat, 0.16);
      lower.position.y = -lowerLen/2;
      knee.add(lower);

      const end = wrap(new THREE.SphereGeometry(R0*1.30, 12, 10), endMat, 0.12);
      end.position.y = -lowerLen - 0.02;
      if (endScale) end.scale.set(endScale[0], endScale[1], endScale[2]);
      knee.add(end);

      pivot.add(knee);
      rig.add(pivot);
      pivot.userData.knee = knee;
      return pivot;
    }

    const sleeveMat = toon(shade(cfg.shirt, -0.14));
    const armL = limb(-0.415, 1.33, 0.34, 0.36, sleeveMat, skinMat, skinMat, [1.05, 1.05, 1.05], 0.092);
    const armR = limb( 0.415, 1.33, 0.34, 0.36, sleeveMat, skinMat, skinMat, [1.05, 1.05, 1.05], 0.092);
    const legL = limb(-0.155, 0.56, 0.34, 0.32, pantMat, pantMat, shoeMat, [1.2, 0.75, 1.6], 0.115);
    const legR = limb( 0.155, 0.56, 0.34, 0.32, pantMat, pantMat, shoeMat, [1.2, 0.75, 1.6], 0.115);

    return {
      root, rig, head, face, faceMat, torso, collar, hips,
      armL, armR, legL, legR,
      height: 2.45
    };
  }

  return {
    build, faceTexture, defaults, toon, gradientMap, shade,
    SKIN, HAIR, CLOTH, PANTS, SHOES,
    HAIR_STYLES, EYE_STYLES, BROW_STYLES, MOUTH_STYLES
  };
})();
