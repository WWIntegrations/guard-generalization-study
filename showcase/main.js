import { createMotion, focusVisibleTarget, motionPolicy } from './controller.mjs';
import { createArtwork } from './artwork.js';
import { mountInspector } from './inspector.js';

const payload = JSON.parse(document.getElementById('study-data').textContent);
// Data and controls are mounted synchronously; fonts never gate access to results.
const inspector = mountInspector(payload);
const scroller=document.getElementById('scroller'), query=matchMedia('(prefers-reduced-motion: reduce)'), motion=createMotion(query.matches);
const menu=document.getElementById('menu'), toggle=document.getElementById('menu-toggle'), pause=document.getElementById('pause');
let fontFallback=false,fallbackReason=null,scene='hero',previous=performance.now(),raf=null,artwork=null,ready=false,selectedTarget=null;
function meta(){return {ready,scene,...motion.snapshot(),internalScroll:scroller.scrollTop,viewport:{width:scroller.clientWidth,height:scroller.clientHeight},renderer:artwork?.renderer??'static-svg',fallbackReason,fontFallback,inspector};}
function updatePause(){const policy=motionPolicy(motion.snapshot(),fallbackReason);pause.textContent=policy.text;pause.setAttribute('aria-label',policy.label);pause.disabled=policy.disabled;}
function draw(){artwork?.draw(motion.snapshot());window.showcaseMeta=meta();}
function resize(){artwork?.resize(scroller.clientWidth,scroller.clientHeight);draw();}
function tick(now){raf=null;motion.tick(now-previous);previous=now;draw();if(motionPolicy(motion.snapshot(),fallbackReason).playing && !document.hidden && scroller.scrollTop<scroller.clientHeight*1.2)raf=requestAnimationFrame(tick);}
function wake(){previous=performance.now();if(raf===null&&motionPolicy(motion.snapshot(),fallbackReason).playing&&!document.hidden&&scroller.scrollTop<scroller.clientHeight*1.2)raf=requestAnimationFrame(tick);}
function stop(){if(raf!==null)cancelAnimationFrame(raf);raf=null;}
pause.addEventListener('click',()=>{if(motionPolicy(motion.snapshot(),fallbackReason).disabled)return;if(motion.snapshot().motionPaused){motion.resume();wake();}else{motion.pause();stop();}updatePause();draw();});
query.addEventListener('change',event=>{motion.setReduced(event.matches);stop();updatePause();draw();});
window.addEventListener('resize',resize);
document.addEventListener('visibilitychange',()=>{if(document.hidden)stop();else wake();});
document.addEventListener('pointermove',event=>{motion.pointer(event.clientX/innerWidth*2-1,event.clientY/innerHeight*2-1);if(raf===null)draw();},{passive:true});
scroller.addEventListener('scroll',()=>{const sections=[...document.querySelectorAll('main>section')];scene=sections.filter(el=>el.getBoundingClientRect().top<innerHeight*.4).at(-1)?.id??'hero';if(scroller.scrollTop>=scroller.clientHeight*1.2)stop();else wake();window.showcaseMeta=meta();},{passive:true});
toggle.addEventListener('click',()=>{selectedTarget=null;menu.showModal();});
document.getElementById('menu-close').addEventListener('click',()=>menu.close());
menu.addEventListener('close',()=>{if(selectedTarget){selectedTarget.focus({preventScroll:true});selectedTarget=null;}else focusVisibleTarget(toggle,document.querySelector('.brand'));});
document.querySelectorAll('a[href^="#"]').forEach(link=>link.addEventListener('click',event=>{
  const target=document.getElementById(link.getAttribute('href').slice(1));if(!target)return;event.preventDefault();
  const top=target.getBoundingClientRect().top-scroller.getBoundingClientRect().top+scroller.scrollTop;
  scroller.scrollTo({top:Math.max(0,top- (innerWidth<=700?40:60)),behavior:'instant'});
  if(menu.open){selectedTarget=target;menu.close();}else target.focus({preventScroll:true});
}));
window.showcaseFrame=ms=>{stop();motion.frame(ms);draw();return meta();};
window.showcaseScroll=px=>{scroller.scrollTop=Math.max(0,px);draw();return meta();};
window.showcaseScene=id=>{const target=document.getElementById(id);if(!target||!target.matches('main>section'))throw new Error('Unknown scene');scroller.scrollTop+=target.getBoundingClientRect().top-scroller.getBoundingClientRect().top;scene=id;draw();return meta();};
window.showcaseFallback=()=>{artwork?.fallback();draw();return meta();};
updatePause();
window.showcaseReady=(async()=>{
  try {await Promise.race([document.fonts.load('48px Anton'),new Promise((_,reject)=>setTimeout(()=>reject(new Error('font_timeout')),3000))]);fontFallback=!document.fonts.check('48px Anton');}catch{fontFallback=true;}
  artwork=createArtwork(document.getElementById('artwork'),reason=>{fallbackReason=reason;motion.pause();stop();updatePause();document.getElementById('render-status').hidden=false;});
  ready=true;resize();wake();return meta();
})();
