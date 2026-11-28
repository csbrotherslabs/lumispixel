(()=>{
const f=document.querySelector('[data-booking-form]');if(!f)return;
const steps=[...f.querySelectorAll('[data-step]')],labels=[...document.querySelectorAll('.booking-shell .steps li')],back=f.querySelector('[data-back]'),next=f.querySelector('[data-next]'),submit=f.querySelector('[data-submit]'),summary=f.querySelector('[data-summary]'),ack=f.elements.namedItem('acknowledge');
let index=Math.max(0,steps.findIndex(s=>s.querySelector('.errorlist'))),editing=false;
const value=name=>{const el=f.elements.namedItem(name);return el?.value||''};
const selected=name=>{const el=f.elements.namedItem(name);return el?.tagName==='SELECT'?el.selectedOptions[0]?.textContent||'':value(name)};
function renderSummary(){
 const raw=value('starts_at'),parts=raw.split('T'),date=new Date(raw+'Z'),validDate=raw&&parts.length===2&&!Number.isNaN(date.getTime());
 const minutes=Number(value('duration_minutes')),hours=Math.floor(minutes/60),rest=minutes%60;
 const first=value('first_name').trim(),last=value('last_name').trim();
 const values={session_type:value('session_type'),date:validDate?new Intl.DateTimeFormat('en-US',{dateStyle:'full',timeZone:'UTC'}).format(date):raw,time:validDate?new Intl.DateTimeFormat('en-US',{hour:'numeric',minute:'2-digit',timeZone:'UTC'}).format(date)+' ('+summary.dataset.timezone+')':'',duration_minutes:minutes?[hours?hours+' hour'+(hours===1?'':'s'):'',rest?rest+' minute'+(rest===1?'':'s'):''].filter(Boolean).join(' '):'',location:value('location'),guests:value('guests'),budget:selected('budget'),description:value('description'),name:[first,last].filter(Boolean).join(' '),initials:(first.charAt(0)+last.charAt(0)).toUpperCase(),email:value('email'),phone:value('phone'),contact_method:selected('contact_method')};
 for(const el of summary.querySelectorAll('[data-review]'))el.textContent=values[el.dataset.review]||'Not specified';
}
function show(focus=false){
 const count=f.querySelector('[data-step-count]');if(count)count.textContent='Step '+(index+1)+' of '+steps.length;
 steps.forEach((s,i)=>s.hidden=i!==index);
 labels.forEach((l,i)=>{l.classList.toggle('is-complete',i<index);i===index?l.setAttribute('aria-current','step'):l.removeAttribute('aria-current');const circle=l.querySelector('span');if(circle)circle.textContent=i<index?'✓':String(i+1)});
 back.hidden=index===0&&!editing;next.hidden=index===steps.length-1;submit.hidden=!next.hidden;
 next.textContent=editing?'Return to review →':'Continue →';
 if(next.hidden){summary.hidden=false;renderSummary()}
 submit.disabled=!!ack&&!ack.checked;
 if(focus){const legend=steps[index].querySelector('legend');if(legend){legend.tabIndex=-1;legend.focus()}}
}
function valid(s){for(const el of s.querySelectorAll('input,select,textarea'))if(!el.checkValidity()){el.reportValidity();return false}return true}
function advance(){if(valid(steps[index])){index=editing?steps.length-1:index+1;editing=false;show(true)}}
next.addEventListener('click',advance);
back.addEventListener('click',()=>{index=editing?steps.length-1:Math.max(0,index-1);editing=false;show(true)});
summary.addEventListener('click',e=>{const b=e.target.closest('[data-edit-step]');if(!b)return;index=Number(b.dataset.editStep);editing=true;show(true)});
if(ack)ack.addEventListener('change',()=>{submit.disabled=!ack.checked});
f.addEventListener('submit',e=>{if(index!==steps.length-1){e.preventDefault();advance();return}for(let i=0;i<steps.length;i++){const bad=[...steps[i].querySelectorAll('input,select,textarea')].find(el=>!el.checkValidity());if(bad){e.preventDefault();index=i;editing=false;show();bad.reportValidity();return}}});
const phone=f.elements.namedItem('phone'),method=f.elements.namedItem('contact_method');
function syncPhone(){if(!phone||!method)return;const required=method.value==='phone';phone.required=required;const star=f.querySelector('[data-phone-required]'),optional=f.querySelector('[data-phone-optional]');if(star)star.hidden=!required;if(optional)optional.hidden=required}
if(method)method.addEventListener('change',syncPhone);syncPhone();f.noValidate=true;show();
})();