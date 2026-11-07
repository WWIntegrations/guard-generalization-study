import * as THREE from 'three';
import { layout } from './controller.mjs';

// Original cylindrical paper geometry; no source meshes or imagery from the reference.
function curvedPaper(radius, centerAngle, span, height) {
  const columns = 36, rows = 8, positions = [], uvs = [], indices = [];
  for (let row = 0; row <= rows; row++) {
    for (let col = 0; col <= columns; col++) {
      const u = col / columns, v = row / rows, theta = centerAngle + (u - .5) * span;
      positions.push(radius * Math.sin(theta), (.5 - v) * height, radius * Math.cos(theta));
      uvs.push(u, 1 - v);
    }
  }
  for (let row = 0; row < rows; row++) for (let col = 0; col < columns; col++) {
    const a = row * (columns + 1) + col, b = a + 1, c = a + columns + 1, d = c + 1;
    indices.push(a, c, b, b, c, d);
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
  geometry.setIndex(indices); geometry.computeVertexNormals(); return geometry;
}

const labels = [
  ['Benign', 'corpus', 'NotInject', 'All source labels: CLEAN'],
  ['Base', 'model', 'Qwen3-1.7B', 'First-token contrast'],
  ['LoRA', 'v2', 'Frozen checkpoint', 'Same original prompt'],
  ['Fixed', 'threshold', 'Probability 0.5', 'No threshold search'],
  ['Exposure', 'audit', 'Declared inventory', 'Unknown is not clear'],
  ['Exact', 'bytes', 'Recorded artifacts', 'Replay the metrics'],
  ['Missing', 'counts', 'Coverage stays visible', 'No silent CLEAN'],
  ['Paired', 'prompts', 'Both predictions OK', 'Shared denominator'],
  ['Single', 'class', 'Benign-only study', 'Attack recall unavailable'],
  ['Honest', 'limits', 'A local experiment', 'Not a safety guarantee']
];

function cardTexture(label) {
  const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 720;
  const ctx = canvas.getContext('2d'); if (!ctx) throw new Error('canvas2d_unavailable');
  ctx.fillStyle = '#000'; ctx.fillRect(0, 0, 512, 720);
  ctx.fillStyle = '#fff'; ctx.font = '48px Arial'; ctx.fillText(label[0], 28, 65); ctx.fillText(label[1], 28, 118);
  ctx.font = '22px Arial'; ctx.fillText(label[2], 28, 260);
  ctx.strokeStyle = '#777'; ctx.lineWidth = 1; ctx.beginPath();ctx.moveTo(28, 282);ctx.lineTo(484, 282);ctx.stroke();
  ctx.strokeStyle = '#f4793a';ctx.lineWidth = 4;
  // An abstract document-and-boundary diagram, with no invented quantitative axis.
  ctx.strokeRect(47, 340, 170, 205);ctx.strokeRect(255, 380, 170, 205);
  for(let line = 0; line < 4; line++) {ctx.beginPath();ctx.moveTo(70, 376 + line * 28);ctx.lineTo(190 - line * 12, 376 + line * 28);ctx.stroke();}
  ctx.beginPath();ctx.moveTo(279, 447);ctx.lineTo(320, 480);ctx.lineTo(400, 419);ctx.stroke();
  ctx.fillStyle = '#fff';ctx.font = '21px Arial';ctx.fillText(label[3], 28, 654);
  ctx.font = '18px Arial';ctx.fillStyle = '#aaa';ctx.fillText('Guard Generalization Study', 28, 690);
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace; texture.anisotropy = 2; return texture;
}

export function createArtwork(container, onFallback) {
  let renderer, scene, camera, orbit, dimensions, failed = false;
  const textures = [], geometries = [], materials = [];
  function fail(reason) {
    failed = true; container.classList.remove('ready'); onFallback(reason);
    if (renderer) renderer.domElement.style.display = 'none';
  }
  try {
    renderer = new THREE.WebGLRenderer({ alpha: true, antialias: true, powerPreference: 'low-power' });
    renderer.setClearColor(0x000000, 0); renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    scene = new THREE.Scene(); camera = new THREE.OrthographicCamera(-720, 720, 450, -450, 1, 6000);camera.position.set(0, 0, 2500);camera.lookAt(0,0,0);
    orbit = new THREE.Group();scene.add(orbit);
    labels.forEach((label, i) => {
      const geometry = curvedPaper(440, i * Math.PI * 2 / labels.length, .585, 350); geometries.push(geometry);
      const texture = cardTexture(label);textures.push(texture);
      const front = new THREE.MeshBasicMaterial({map:texture,side:THREE.FrontSide});
      const back = new THREE.MeshBasicMaterial({color:0xab542b,side:THREE.BackSide});materials.push(front,back);
      orbit.add(new THREE.Mesh(geometry,front));orbit.add(new THREE.Mesh(geometry,back));
    });
    renderer.domElement.setAttribute('aria-hidden','true');
    renderer.domElement.addEventListener('webglcontextlost',event=>{event.preventDefault();fail('context_lost');});
    container.append(renderer.domElement);container.classList.add('ready');
  } catch (error) { fail(error.message === 'canvas2d_unavailable' ? error.message : 'webgl_unavailable'); }
  return {
    resize(width, height) {
      dimensions = layout(width,height);
      if (failed) return;
      renderer.setSize(width,height,false);camera.left=-width/2;camera.right=width/2;camera.top=height/2;camera.bottom=-height/2;camera.updateProjectionMatrix();
    },
    draw(state) {
      if (failed || !dimensions) return;
      const {ribbon} = dimensions;
      orbit.scale.setScalar(ribbon.scale);
      orbit.position.set(ribbon.x-dimensions.width/2,dimensions.height/2-ribbon.y,0);
      orbit.rotation.set(.05 + state.pointerY * .03, state.motionMs / 50000 * Math.PI * 2 + .1 + state.pointerX * .05, -ribbon.rotation,'ZYX');
      renderer.render(scene,camera);
    },
    fallback(reason='requested_fallback') {fail(reason);},
    dispose() {textures.forEach(x=>x.dispose());geometries.forEach(x=>x.dispose());materials.forEach(x=>x.dispose());renderer?.dispose();},
    get renderer() {return failed?'static-svg':'webgl';}
  };
}
