const API=window.location.origin;
const $=s=>document.querySelector(s);
const el=(t,a={},...k)=>{const e=document.createElement(t);for(const[x,v]of Object.entries(a)){if(x==='class')e.className=v;else if(x==='href'){if(/^https?:\/\//i.test(v)){e.href=v;e.target='_blank';e.rel='noopener noreferrer'}}else e.setAttribute(x,v)}for(const c of k.flat(Infinity))if(c!=null&&c!==false)e.append(c.nodeType?c:document.createTextNode(String(c)));return e};
const host=u=>{try{return new URL(u).hostname.replace(/^www\./,'')}catch(e){return 'source'}};
const src=u=>u?el('a',{class:'src',href:u},'↗ '+host(u)):null;
const empty=t=>el('p',{class:'muted'},t);
const card=(title,cls,...body)=>el('section',{class:'card '+(cls||'')},el('h3',{},title),...body);
const list=(rows,fn,none)=>rows&&rows.length?el('ul',{},rows.map(r=>el('li',{},fn(r)))):empty(none);
const initials=n=>n.split(/\s+/).slice(0,2).map(w=>w[0]).join('').toUpperCase();
const pick=(A,label)=>(A.profile.find(p=>p[0]===label)||[])[1];

function render(B){
 const A=B.analysis,out=$('#out');out.replaceChildren();
 const qs=new URLSearchParams(new FormData($('#f'))).toString();
 const badges=['Size class','Sector (inferred)','Data confidence'].map(l=>pick(A,l)&&el('span',{class:'badge'},pick(A,l)));

 // 1. header with company name and actions
 out.append(el('div',{class:'hero'},
  el('div',{class:'hero-main'},
   el('h2',{},B.matched||B.query),
   el('div',{class:'meta'},'Generated '+B.generated+(B.why?' · matched: '+B.why:'')),
   el('div',{class:'badges'},badges)),
  el('div',{class:'bar'},
   el('a',{class:'btn',href:API+'/api/pdf?'+qs},'⬇ PDF'),
   el('a',{class:'btn',href:API+'/api/xlsx?'+qs},'⬇ Excel'),
   el('button',{type:'button',class:'btn',id:'copy'},'Copy brief'))));

 // 2. What they do: always the first card
 out.append(card('What they do','lead',
  B.overview?el('p',{class:'lead-text'},B.overview[0],src(B.overview[1])):empty('No description found.'),
  A.summary?el('p',{class:'quick'},el('strong',{},'Quick read: '),A.summary):null));

 // 3. the rest, in the order of the brief
 const g=el('div',{class:'grid'});
 g.append(
  card('Size, locations and facts','',B.facts.length?el('dl',{},B.facts.map(f=>[el('dt',{},f[0]),el('dd',{},f[1],src(f[2]))])):empty('No facts found.')),
  card('Recent news','',list(B.news,n=>[el('a',{class:'headline',href:n[1]},n[0]),el('div',{class:'muted small'},[n[2],n[3]].filter(Boolean).join(' · '))],'No recent news retrieved.')),
  card('Decision-makers','',list(B.people,p=>el('div',{class:'person'},
    el('span',{class:'avatar'},initials(p[0])),
    el('div',{},el('strong',{},p[0]),el('div',{class:'muted small'},p[1],src(p[2])))),'None publicly listed.')),
  card('Contact details','',list(B.contacts,c=>[el('span',{class:'muted'},c[0]+': '),c[1],src(c[2])],'No public contacts found.')),
  card('Three talking points for a first meeting','wide',el('ol',{class:'points'},B.talking.map(t=>el('li',{},t[0],src(t[1]))))),
  card('Analysis','wide',
   el('div',{class:'chips'},A.profile.map(p=>el('span',{class:'chip'},p[0]+': '+p[1]))),
   list(A.signals,s=>[el('span',{class:'tag '+s[0]},s[0]),s[1],src(s[2])],'No signals detected.')),
  card('More sources','wide',list(B.more,m=>[el('a',{href:m[1]},m[0]),m[2]?el('div',{class:'muted small'},m[2]):null],'No extra sources found.'))
 );
 out.append(g);
 if(B.notes.length)out.append(card('Notes','notes',B.notes.map(n=>el('div',{class:'note'},n[0],n[1]?el('a',{class:'src',href:n[1]},'open link'):null))));
 $('#copy').onclick=async e=>{try{await navigator.clipboard.writeText(B.text);e.target.textContent='Copied'}catch(x){e.target.textContent='Copy failed'}};
}

function recents(){let r=[];try{r=JSON.parse(localStorage.getItem('recent')||'[]')}catch(e){}
 $('#recent').replaceChildren(...r.map(n=>el('button',{type:'button',class:'chip'},n)));
 document.querySelectorAll('#recent .chip').forEach(b=>b.onclick=()=>{$('#q').value=b.textContent;$('#f').requestSubmit()})}
function remember(n){try{let r=JSON.parse(localStorage.getItem('recent')||'[]').filter(x=>x!==n);r.unshift(n);localStorage.setItem('recent',JSON.stringify(r.slice(0,6)))}catch(e){}recents()}

const STEPS=['Checking Wikipedia and Wikidata…','Reading the company website…','Checking startup directories…','Searching for decision-makers…','Collecting recent news…','Putting the brief together…'];
$('#f').addEventListener('submit',async ev=>{ev.preventDefault();
 const qs=new URLSearchParams(new FormData(ev.target)).toString(),st=$('#status'),go=$('#go');
 go.disabled=true;$('#out').replaceChildren();st.className='';
 let i=0;const msg=el('span',{},STEPS[0]);
 st.replaceChildren(el('span',{class:'spin'}),msg,el('span',{class:'muted'},' This takes about 10 to 40 seconds.'));
 const timer=setInterval(()=>{i=Math.min(i+1,STEPS.length-1);msg.textContent=STEPS[i]},6000);
 try{const r=await fetch(API+'/api/brief?'+qs);
  if(!r.ok){let m='Server error '+r.status;try{m=(await r.json()).error||m}catch(_){}throw new Error(m)}
  const B=await r.json();st.textContent='';render(B);remember($('#q').value.trim());
 }catch(e){st.className='err';st.textContent='Could not build the brief: '+e.message}
 clearInterval(timer);go.disabled=false});
recents();
