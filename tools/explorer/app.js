'use strict';
let data, state, selectedGroup=null;
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=n=>n==null?'—':(100*n).toFixed(1)+'%';
const number=n=>n==null?'—':Number(n).toLocaleString('zh-CN',{maximumFractionDigits:1});
const resultName={win:'胜',loss:'负',draw:'平',unknown:'未知'};
const dimension=k=>data.dimensions.find(d=>d.key===k);
function defaultState(){return {dims:['map'],filters:[],from:data.metadata.window_start.slice(0,10),to:data.metadata.cutoff.slice(0,10),min:0,sort:'win_rate',bounds:true};}
function options(selected){return data.dimensions.map(d=>`<option value="${d.key}" ${d.key===selected?'selected':''}>${esc(d.label)}${d.kind==='战后'?' · 战后':''}</option>`).join('');}
function renderControls(){
  $('dimensions').innerHTML=state.dims.map((d,i)=>`<div class="dim-row"><select aria-label="分组标签 ${i+1}" data-dim="${i}">${options(d)}</select><button aria-label="删除分组标签 ${i+1}" data-remove-dim="${i}" ${state.dims.length===1?'disabled':''}>×</button></div>`).join('');
  document.querySelectorAll('[data-dim]').forEach(el=>el.onchange=()=>{state.dims[+el.dataset.dim]=el.value;state.dims=[...new Set(state.dims)];selectedGroup=null;renderControls();render();});
  document.querySelectorAll('[data-remove-dim]').forEach(el=>el.onclick=()=>{state.dims.splice(+el.dataset.removeDim,1);selectedGroup=null;renderControls();render();});
  $('filters').innerHTML=state.filters.map((f,i)=>{
    const vals=[...new Set(data.records.map(r=>r.tags[f.key]))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
    return `<div class="filter"><div class="filter-head"><select aria-label="筛选标签 ${i+1}" data-filter-key="${i}">${options(f.key)}</select><button aria-label="删除筛选 ${i+1}" data-remove-filter="${i}">×</button></div><select multiple aria-label="筛选值 ${i+1}" data-filter-values="${i}">${vals.map(v=>`<option value="${esc(v)}" ${f.values.includes(v)?'selected':''}>${esc(v)}</option>`).join('')}</select><p class="hint">空选 = 全部；Ctrl / ⌘ 多选。组内或，组间且。</p></div>`;
  }).join('');
  document.querySelectorAll('[data-filter-key]').forEach(el=>el.onchange=()=>{state.filters[+el.dataset.filterKey]={key:el.value,values:[]};selectedGroup=null;renderControls();render();});
  document.querySelectorAll('[data-filter-values]').forEach(el=>el.onchange=()=>{state.filters[+el.dataset.filterValues].values=[...el.selectedOptions].map(o=>o.value);selectedGroup=null;render();});
  document.querySelectorAll('[data-remove-filter]').forEach(el=>el.onclick=()=>{state.filters.splice(+el.dataset.removeFilter,1);selectedGroup=null;renderControls();render();});
  $('date-from').value=state.from;$('date-to').value=state.to;$('min-count').value=state.min;$('sort').value=state.sort;$('bounds').checked=state.bounds;
}
function filtered(){return data.records.filter(r=>(!state.from||r.tags.day>=state.from)&&(!state.to||r.tags.day<=state.to)&&state.filters.every(f=>!f.values.length||f.values.includes(r.tags[f.key])));}
function stats(rows){
  const wins=rows.filter(r=>r.result==='win').length,losses=rows.filter(r=>r.result==='loss').length,draws=rows.filter(r=>r.result==='draw').length;
  const known=wins+losses+draws,total=rows.length,unknown=total-known,p=known?wins/known:null,z=1.959963984540054;
  let low=null,high=null;
  if(known){const denom=1+z*z/known,center=(p+z*z/(2*known))/denom,radius=z*Math.sqrt(p*(1-p)/known+z*z/(4*known*known))/denom;low=Math.max(0,center-radius);high=Math.min(1,center+radius);}
  return {wins,losses,draws,known,total,unknown,p,low,high,boundLow:total?wins/total:null,boundHigh:total?(wins+unknown)/total:null};
}
function render(){
  const rows=filtered(),all=stats(rows),groups=new Map();
  for(const r of rows){const key=JSON.stringify(state.dims.map(d=>r.tags[d]));if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}
  let list=[...groups.entries()].map(([key,rows])=>({key,rows,...stats(rows)})).filter(g=>g.known>=state.min);
  list.sort((a,b)=>state.sort==='total'?b.total-a.total:state.sort==='unknown'?(b.unknown/b.total)-(a.unknown/a.total):state.sort==='name'?a.key.localeCompare(b.key,'zh-CN'):(a.p??Infinity)-(b.p??Infinity)||b.known-a.known);
  $('kpis').innerHTML=[['当前对局',number(all.total),'按日期和标签筛选'],['已知胜率',pct(all.p),`${all.wins} 胜 · ${all.losses} 负 · ${all.draws} 平`],['结果未知',number(all.unknown),`${pct(all.total?all.unknown/all.total:null)} 的当前样本`],['含未知的范围',`${pct(all.boundLow)}–${pct(all.boundHigh)}`,'未知全负 → 未知全胜'],['分组数量',number(list.length),`共 ${groups.size} 组，按已知场数显示`]].map(([l,v,h])=>`<div class="kpi"><small>${l}</small><strong ${l==='含未知的范围'?'style="font-size:20px"':''}>${v}</strong><span>${h}</span></div>`).join('');
  const investigation=data.investigation_summary?.unknown;
  $('quality').innerHTML=investigation?`<strong>缺失机制已核实：</strong>快照中的 ${investigation.files} 场未知均在本人阵亡后、结算前结束录像；不能视为随机缺失，也不能直接算作负场。<button id="inspect-unknown">查看这 ${investigation.files} 场</button>`:'缺失结果保持未知。仅看完整战报可能存在样本选择偏差。';
  if($('inspect-unknown'))$('inspect-unknown').onclick=()=>{state=defaultState();state.filters=[{key:'completeness',values:['无战报']}];selectedGroup=null;renderControls();render();};
  $('group-caption').textContent=state.dims.map(k=>dimension(k).label).join(' × ')+' · 当前基线 '+pct(all.p)+' · 点击分组查看具体对局';
  $('post-label-note').hidden=!state.dims.concat(state.filters.map(f=>f.key)).some(k=>dimension(k)?.kind==='战后');
  $('groups-table').classList.toggle('bounds-hidden',!state.bounds);
  $('groups').innerHTML=list.length?list.map((g,i)=>{
    const otherKnown=all.known-g.known,otherWins=all.wins-g.wins,diff=g.p!=null&&otherKnown?g.p-otherWins/otherKnown:null;
    const restTotal=all.total-g.total,robust=restTotal>0&&g.boundHigh<otherWins/restTotal;
    return `<tr ${g.key===selectedGroup?'class="selected"':''}><td class="group-name"><button data-group="${i}">${JSON.parse(g.key).map(esc).join(' / ')}</button>${g.known<10?'<span class="small">小样本 · 先看对局</span>':''}${robust?'<span class="robust" title="当前样本：本组未知全胜、其余未知全负，本组仍较低。不是总体显著性。">本组上界仍低于其余下界</span>':''}</td><td>${g.total} / ${g.known}</td><td>${g.wins} / ${g.losses} / ${g.draws}</td><td class="rate-cell"><div class="rate-main"><b>${pct(g.p)}</b><span class="ci">${pct(g.low)}–${pct(g.high)}</span></div>${g.p!=null?`<div class="track"><i class="interval" style="left:${g.low*100}%;width:${(g.high-g.low)*100}%"></i><i class="point" style="left:${g.p*100}%"></i></div>`:''}</td><td class="${diff<0?'negative':'positive'}">${diff==null?'—':(diff>=0?'+':'')+(diff*100).toFixed(1)+' pp'}</td><td class="unknown">${g.unknown}<span class="small">${pct(g.unknown/g.total)}</span></td><td class="bounds-col">${pct(g.boundLow)}–${pct(g.boundHigh)}</td></tr>`;
  }).join(''):'<tr><td colspan="7" class="empty">没有符合条件的分组。试着放宽筛选或降低最小已知场数。</td></tr>';
  document.querySelectorAll('[data-group]').forEach(el=>el.onclick=()=>{selectedGroup=list[+el.dataset.group].key;render();$('battles-section').scrollIntoView({behavior:'smooth',block:'start'});});
  const selected=list.find(g=>g.key===selectedGroup);
  $('battles-section').hidden=!selected;
  if(selected){
    $('battles-title').textContent=JSON.parse(selected.key).join(' / ')+' · '+selected.total+' 场';
    const sorted=[...selected.rows].sort((a,b)=>b.started_at.localeCompare(a.started_at));
    $('battles').innerHTML=sorted.map((r,i)=>`<tr><td><button class="quiet" data-battle="${i}">${esc(r.started_at.slice(5,19).replace('T',' '))}</button></td><td>${esc(r.tags.map)}<span class="small">${esc(r.tags.vehicle)}</span></td><td>${esc(r.tags.side)}</td><td class="${r.result==='win'?'positive':r.result==='unknown'?'unknown':'negative'}">${resultName[r.result]}</td><td>${number(r.damageDealt)}</td><td>${esc(r.tags.recording_end)}</td></tr>`).join('');
    document.querySelectorAll('[data-battle]').forEach(el=>el.onclick=()=>showDetail(sorted[+el.dataset.battle]));
  }
}
function showDetail(r){
  const event=r.investigation,prettyMode={lookAtKiller:'查看击杀者',postmortem:'阵亡后观战',arcade:'第三人称',sniper:'瞄准镜'};
  const timeline=[];
  if(event){
    if(event.battle_start_clock!=null)timeline.push([event.battle_start_clock,'战斗计时开始']);
    if(event.death_clock!=null)timeline.push([event.death_clock,'本人生命值降至 0，确认阵亡']);
    for(const v of event.view_modes.filter(v=>['lookAtKiller','postmortem'].includes(v.mode)))timeline.push([v.clock,prettyMode[v.mode]]);
    const after=event.phases.find(p=>p.value===4);if(after)timeline.push([after.clock,'进入赛后阶段']);
    timeline.push([event.end_clock,'录像正常收尾'+(event.has_afterbattle?'':'，未记录最终结算')]);
  }
  const metrics=[['伤害',r.damageDealt],['侦查协助',r.damageAssistedRadio],['断带协助',r.damageAssistedTrack],['格挡',r.damageBlockedByArmor],['击杀',r.kills],['生存秒数',r.lifeTime],['战前积分',r.rating_before],['积分变化',r.rating_delta]];
  const participants=side=>{
    const list=r.players.filter(p=>p.is_ally===side).sort((a,b)=>Number(b.is_self)-Number(a.is_self));
    if(!list.length)return '<p class="hint">这场没有战报，无法取得完整阵容与分段。</p>';
    return `<table><thead><tr><th>车辆</th><th>分段</th><th>伤害</th></tr></thead><tbody>${list.map(p=>`<tr><td>${p.is_self?'本人 · ':''}${esc((p.vehicle||'未知').split(':').pop())}</td><td>${esc(p.rank_display)}</td><td>${number(p.damageDealt)}</td></tr>`).join('')}</tbody></table>`;
  };
  $('detail-body').innerHTML=`<h2>${esc(r.tags.map)} · ${esc(r.tags.vehicle)}</h2><p class="hint">${esc(r.started_at.replace('T',' '))} · ${esc(r.tags.side)} · ${resultName[r.result]}${!r.vehicle?' · 车辆来自文件头，未用战报复核':''}</p><div class="tag-list">${['vehicle_class','self_rank','completeness','recording_end'].map(k=>`<span>${esc(dimension(k).label)}：${esc(r.tags[k])}</span>`).join('')}</div>${r.result==='unknown'?'<div class="note">最终结果未知。阵亡与提前结束录制均不等于整场失败；缺失的伤害、积分或分段也不是 0。</div>':''}<div class="detail-grid"><div class="detail-card"><h3>个人表现与积分</h3><dl class="stat-list">${metrics.map(([k,v])=>`<div><dt>${k}</dt><dd>${number(v)}</dd></div>`).join('')}</dl></div><div class="detail-card"><h3>录制时间线</h3><p class="hint">以下均为录像内秒数；事件来自实际数据包。</p><div class="timeline">${timeline.length?timeline.sort((a,b)=>a[0]-b[0]).map(([t,s])=>`<p><b>${t.toFixed(1)}s</b>${s}</p>`).join(''):'<p class="hint">此场未做二进制调查。</p>'}</div>${event?.seconds_from_death_to_end!=null?`<p class="hint">阵亡后继续记录 ${event.seconds_from_death_to_end.toFixed(1)} 秒。</p>`:''}${event?.seconds_end_to_next_start!=null?`<p class="hint">下一场录像约在结束后 ${event.seconds_end_to_next_start.toFixed(0)} 秒开始。</p>`:''}</div></div><div class="detail-grid"><div class="detail-card"><h3>我方 · 含本人</h3>${participants(true)}</div><div class="detail-card"><h3>对方</h3>${participants(false)}</div></div><h3>原始录像与追溯</h3><p class="path">${esc(r.replay_path)}</p><p class="hint">SHA-256：${esc(r.sha256)}<br>出生点配置坐标：${esc(JSON.stringify(r.spawn_points))}；这是队伍配置点，不是实测轨迹。</p><div class="detail-actions"><button id="copy-path">复制录像路径</button><a class="download" href="/replay/${encodeURIComponent(r.id)}" download>下载原始录像</a></div>`;
  $('copy-path').onclick=async()=>{try{await navigator.clipboard.writeText(r.replay_path);$('copy-path').textContent='路径已复制';}catch{$('copy-path').textContent='请在上方选中路径复制';}};
  $('detail').showModal();
}
function wire(){
  $('controls-toggle').onclick=()=>{const open=$('controls').classList.toggle('expanded');$('controls-toggle').setAttribute('aria-expanded',String(open));$('controls-toggle').textContent=open?'收起标签与筛选':'展开标签与筛选';};
  $('add-dimension').onclick=()=>{const next=data.dimensions.find(d=>!state.dims.includes(d.key));if(next){state.dims.push(next.key);selectedGroup=null;renderControls();render();}};
  $('add-filter').onclick=()=>{state.filters.push({key:'map',values:[]});renderControls();};
  $('reset').onclick=()=>{state=defaultState();selectedGroup=null;renderControls();render();};
  for(const [id,key] of [['date-from','from'],['date-to','to'],['sort','sort']])$(id).onchange=()=>{state[key]=$(id).value;selectedGroup=null;render();};
  $('min-count').oninput=()=>{state.min=Math.max(0,Number($('min-count').value)||0);selectedGroup=null;render();};
  $('bounds').onchange=()=>{state.bounds=$('bounds').checked;render();};
  $('methods-toggle').onclick=()=>{$('methods').hidden=!$('methods').hidden;};
  $('clear-group').onclick=()=>{selectedGroup=null;render();};
  $('close-detail').onclick=()=>$('detail').close();
  $('save-view').onclick=()=>{try{localStorage.setItem('onslaught-view-v1',JSON.stringify(state));$('view-status').textContent='已保存到此浏览器';}catch{$('view-status').textContent='此浏览器无法保存视图';}};
  $('load-view').onclick=()=>{try{const saved=JSON.parse(localStorage.getItem('onslaught-view-v1'));if(!saved)throw Error();if(!Array.isArray(saved.dims)||!saved.dims.length||saved.dims.some(k=>!dimension(k))||!Array.isArray(saved.filters)||saved.filters.some(f=>!dimension(f.key)||!Array.isArray(f.values)))throw Error();state={...defaultState(),...saved};selectedGroup=null;renderControls();render();$('view-status').textContent='已恢复保存的视图';}catch{$('view-status').textContent='没有可恢复的视图';}};
}
async function init(){try{const response=await fetch('/api/data');if(!response.ok)throw Error('数据读取失败');data=await response.json();state=defaultState();$('snapshot').textContent=`本地快照 · ${data.metadata.window_start.slice(0,10)} 至 ${data.metadata.cutoff.slice(0,10)} · ${data.metadata.recent_count} 场`;wire();renderControls();render();}catch(error){$('error').hidden=false;$('error').textContent='加载失败：'+error.message;}}
init();
