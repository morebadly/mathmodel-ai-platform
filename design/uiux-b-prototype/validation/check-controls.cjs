const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=require('path').resolve(__dirname,'..');
class El{constructor(){this.attrs={};this.dataset={};this.handlers={};this.children=[];this.textContent='';this.value=''}setAttribute(k,v){this.attrs[k]=v}getAttribute(k){return this.attrs[k]??null}addEventListener(k,fn){this.handlers[k]=fn}insertAdjacentElement(_,el){this.inserted=el}querySelector(q){return q==='.language-window'?this.face:this.label}querySelectorAll(){return this.buttons||[]}set innerHTML(s){this.html=s;if(s.includes('language-step')){this.face=new El;this.label=new El;this.buttons=[-1,1].map(n=>{const e=new El;e.dataset.direction=String(n);return e})}else this.buttons=['light','dark','system'].map(t=>{const e=new El;e.dataset.themeChoice=t;return e})}setPointerCapture(id){this.pointer=id}hasPointerCapture(id){return this.pointer===id}releasePointerCapture(){this.pointer=null}dispatchEvent(e){this.onchange?.(e)}closest(q){return (q.includes('direction')&&this.dataset.direction)||(q.includes('theme-choice')&&this.dataset.themeChoice)?this:null}}
const language=new El,theme=new El;let captures=0,saves=0,renders=0;
const M3={data:{preferences:{language:'zh',theme:'light'}},capture(){captures++},render(){renders++},applyTheme(){}};
language.onchange=()=>{M3.data.preferences.language=language.value;saves++;M3.render()};theme.onchange=()=>{M3.data.preferences.theme=theme.value;saves++;M3.applyTheme()};
const attrs=new WeakMap,context={document:{getElementById:id=>id==='language'?language:theme,createElement:()=>new El},M3,L10N:{attrs},matchMedia:()=>({matches:true}),Event:class{constructor(type,options){this.type=type;this.bubbles=options.bubbles}}};
vm.runInNewContext(fs.readFileSync(root+'/preference-controls.js','utf8'),context);
const c=language.inserted,t=theme.inserted,face=c.face,label=c.label,checks=[];
function test(name,fn){fn();checks.push({name,pass:true})}function step(n){c.handlers.click({target:c.buttons[n>0?1:0]})}function swipe(dx,dy=0){face.handlers.pointerdown({button:0,pointerId:1,clientX:100,clientY:100});face.handlers.pointerup({pointerId:1,clientX:100+dx,clientY:100+dy})}
test('One current language visible',()=>assert.equal(label.textContent,'中文'));
test('Original selects hidden but retained',()=>assert.ok(language.hidden&&theme.hidden));
test('Right arrow advances English',()=>{step(1);assert.equal(label.textContent,'English')});
test('Next advances Russian',()=>{step(1);assert.equal(label.textContent,'Русский')});
test('Three-language wrap',()=>{step(1);assert.equal(M3.data.preferences.language,'zh')});
test('Previous wraps Russian',()=>{step(-1);assert.equal(M3.data.preferences.language,'ru')});
test('Leftward swipe advances',()=>{swipe(-40);assert.equal(label.textContent,'中文')});
test('Rightward swipe reverses',()=>{swipe(40);assert.equal(label.textContent,'Русский')});
test('Small movement does not switch',()=>{swipe(-10);assert.equal(label.textContent,'Русский')});
test('Vertical scroll does not switch',()=>{swipe(-40,80);assert.equal(label.textContent,'Русский')});
test('Cancelled gesture does not switch',()=>{face.handlers.pointerdown({button:0,pointerId:2,clientX:100,clientY:100});face.handlers.pointercancel();face.handlers.pointerup({pointerId:2,clientX:0,clientY:100});assert.equal(label.textContent,'Русский')});
test('Keyboard right advances',()=>{c.handlers.keydown({target:face,key:'ArrowRight',preventDefault(){}});assert.equal(label.textContent,'中文')});
test('Keyboard left reverses',()=>{c.handlers.keydown({target:face,key:'ArrowLeft',preventDefault(){}});assert.equal(label.textContent,'Русский')});
for(const mode of ['dark','system','light'])test('Theme '+mode+' uses existing preference path',()=>{t.handlers.click({target:t.buttons.find(b=>b.dataset.themeChoice===mode)});assert.equal(M3.data.preferences.theme,mode);assert.equal(t.buttons.filter(b=>b.attrs['aria-pressed']==='true').length,1);assert.equal(t.buttons.find(b=>b.dataset.themeChoice===mode).attrs['aria-pressed'],'true')});
test('Selection survives rerender',()=>{M3.render();assert.equal(label.textContent,'Русский');assert.equal(t.buttons[0].attrs['aria-pressed'],'true')});
test('Three language tooltips updated',()=>{assert.equal(c.buttons[0].attrs['aria-label'],'Предыдущий язык');step(1);assert.equal(c.buttons[0].attrs['aria-label'],'上一种语言');step(1);assert.equal(c.buttons[0].attrs['aria-label'],'Previous language')});
test('Localization cache follows current labels',()=>{attrs.set(face,{'aria-label':face.attrs['aria-label']});step(1);assert.ok(attrs.get(face)['aria-label'].includes('Русский'))});
test('Language changes capture edits and dispatch save handler',()=>assert.ok(captures>=10&&saves>=13&&renders>0));
fs.writeFileSync(root+'/validation/control-interaction-results.json',JSON.stringify({checks,total:checks.length,passed:checks.length,method:'Isolated control interaction checks; not a browser rendering test'},null,2));console.log(JSON.stringify({total:checks.length,passed:checks.length}));
