'use strict';
let data, state, selectedGroup=null;
const $=id=>document.getElementById(id);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const pct=n=>n==null?'—':(100*n).toFixed(1)+'%';
const number=n=>n==null?'—':Number(n).toLocaleString('zh-CN',{maximumFractionDigits:1});
const signed=n=>n==null?'—':(n>0?'+':'')+number(n);
const resultName={win:'胜',loss:'负',draw:'平',unknown:'未知'};
const dimension=k=>data.dimensions.find(d=>d.key===k);
const RETIRED_RANK_DIMENSIONS=new Set(['self_rank','ally_ranks','enemy_ranks','allies_high','enemies_high']);
const RETIRED_LOBBY_VALUES=new Set(['白银局','未分类']);
const retiredFilter=f=>RETIRED_RANK_DIMENSIONS.has(f.key)||(f.key==='lobby_type'&&f.values.some(v=>RETIRED_LOBBY_VALUES.has(v)));
const RESULTS={rating:{label:'积分变化',mean:'场均积分变化',format:signed},prestige:{label:'声望',mean:'平均声望',format:number},win:{label:'胜率',mean:'已知胜率',format:pct}};
function defaultState(){return {metric:'rating',dims:['map'],filters:[],from:data.metadata.window_start.slice(0,10),to:data.metadata.cutoff.slice(0,10),min:0,sort:'result_asc',bounds:true};}
// Replay calendar dates follow the server's UTC+08 convention.
function datePresetRange(preset,now=new Date()){
  const offsets={today:[0,0],yesterday:[1,1],beforeYesterday:[2,2],threeDays:[2,0],sevenDays:[6,0]}[preset];
  if(!offsets)throw Error('未知日期快捷选项');
  const today=new Date(now.getTime()+8*60*60*1000);
  const day=offset=>{const date=new Date(today);date.setUTCDate(date.getUTCDate()-offset);return date.toISOString().slice(0,10);};
  return {from:day(offsets[0]),to:day(offsets[1])};
}
function renderDateControls(){
  $('date-from').value=state.from;$('date-to').value=state.to;
  const now=new Date();
  document.querySelectorAll('[data-date-preset]').forEach(button=>{
    const range=datePresetRange(button.dataset.datePreset,now);
    button.setAttribute('aria-pressed',String(state.from===range.from&&state.to===range.to));
  });
}
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
  renderResultControls();
  renderDateControls();$('min-count').value=state.min;$('sort').value=state.sort;$('bounds').checked=state.bounds;
}
function filtered(){return data.records.filter(r=>(!state.from||r.tags.day>=state.from)&&(!state.to||r.tags.day<=state.to)&&state.filters.every(f=>!f.values.length||f.values.includes(r.tags[f.key])));}
function metricStats(rows,key){
  const values=rows.map(r=>r[key]).filter(v=>typeof v==='number'&&Number.isFinite(v)).sort((a,b)=>a-b);
  const count=values.length,total=count?values.reduce((a,b)=>a+b,0):null;
  const quantile=p=>{if(!count)return null;const index=(count-1)*p,low=Math.floor(index);return values[low]+(values[Math.ceil(index)]-values[low])*(index-low);};
  const outcome=result=>{const subset=rows.filter(r=>r.result===result&&typeof r[key]==='number'&&Number.isFinite(r[key]));return {count:subset.length,mean:subset.length?subset.reduce((sum,r)=>sum+r[key],0)/subset.length:null};};
  return {count,total,mean:count?total/count:null,median:quantile(.5),q1:quantile(.25),q3:quantile(.75),win:outcome('win'),loss:outcome('loss')};
}
function stats(rows){
  const wins=rows.filter(r=>r.result==='win').length,losses=rows.filter(r=>r.result==='loss').length,draws=rows.filter(r=>r.result==='draw').length;
  const known=wins+losses+draws,total=rows.length,unknown=total-known,p=known?wins/known:null,z=1.959963984540054;
  let low=null,high=null;
  if(known){const denom=1+z*z/known,center=(p+z*z/(2*known))/denom,radius=z*Math.sqrt(p*(1-p)/known+z*z/(4*known*known))/denom;low=Math.max(0,center-radius);high=Math.min(1,center+radius);}
  // User scenario: every replay without a final report is assumed to be an early departure.
  const eligible=rows.filter(r=>r.result==='unknown'&&r.result_status==='no_result_block').length;
  const unassigned=unknown-eligible,expectedWins=wins+.3*eligible;
  const estimate=total&&unassigned===0?expectedWins/total:null;
  return {wins,losses,draws,known,total,unknown,p,low,high,eligible,unassigned,expectedWins,estimate,prestige:metricStats(rows,'comp7PrestigePoints'),damage:metricStats(rows,'damageDealt'),rating:metricStats(rows,'rating_delta'),boundLow:total?wins/total:null,boundHigh:total?(wins+unknown)/total:null};
}
function resultSummary(s,metric){
  return metric==='win'?{count:s.known,mean:s.p,total:s.wins}:s[metric];
}
function resultDifference(group,all,metric){
  const g=resultSummary(group,metric),a=resultSummary(all,metric),restCount=a.count-g.count;
  return g.mean==null||restCount<=0?null:g.mean-(a.total-g.total)/restCount;
}
function compareResults(a,b,metric,sort){
  const am=resultSummary(a,metric),bm=resultSummary(b,metric);
  if(sort==='total')return b.total-a.total;
  if(sort==='unknown')return (b.total-bm.count)/b.total-(a.total-am.count)/a.total;
  if(sort==='name')return a.key.localeCompare(b.key,'zh-CN');
  const av=sort==='estimated'?a.estimate:am.mean,bv=sort==='estimated'?b.estimate:bm.mean;
  // Missing groups always follow observed groups, in either sort direction.
  if(av==null||bv==null)return av==null?(bv==null?0:1):-1;
  return (sort==='result_desc'?bv-av:av-bv)||bm.count-am.count;
}
function restoreState(saved){
  if(!saved||!Array.isArray(saved.dims)||!saved.dims.length||!Array.isArray(saved.filters)||saved.filters.some(f=>!Array.isArray(f.values)))throw Error('Invalid view');
  const dims=[...new Set(saved.dims.map(k=>RETIRED_RANK_DIMENSIONS.has(k)?'lobby_type':k))];
  const filters=saved.filters.filter(f=>!retiredFilter(f));
  if(dims.some(k=>!dimension(k))||filters.some(f=>!dimension(f.key)))throw Error('Invalid view');
  const metric=saved.metric??'win'; // Old saved views were explicitly about win rate.
  if(!Object.hasOwn(RESULTS,metric))throw Error('Invalid result');
  const sort=saved.sort==='win_rate'?'result_asc':saved.sort??'result_asc';
  if(!['result_asc','result_desc','total','unknown','name','estimated'].includes(sort)||(sort==='estimated'&&metric!=='win'))throw Error('Invalid sort');
  return {...defaultState(),...saved,dims,filters,metric,sort};
}
function renderResultControls(){
  const config=RESULTS[state.metric],isWin=state.metric==='win';
  document.querySelectorAll('[data-result]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.result===state.metric)));
  $('min-label').textContent=isWin?'分组至少有多少场已知胜负':'分组至少有多少场'+config.label+'数据';
  $('bounds-control').hidden=!isWin;
  const options=[['result_asc',config.mean+'：低 → 高'],['result_desc',config.mean+'：高 → 低'],
    ...(isWin?[['estimated','估计胜率（30% 情景）：低 → 高']]:[]),['total','总场数：多 → 少'],['unknown',config.label+'缺失占比：高 → 低'],['name','标签名称']];
  $('sort').innerHTML=options.map(([key,label])=>`<option value="${key}">${label}</option>`).join('');
  $('sort').value=state.sort;
}
function renderOverview(all){
  const metric=state.metric,config=RESULTS[metric],m=resultSummary(all,metric),isWin=metric==='win',fmt=config.format;
  const coverage=`有值 ${m.count} / ${all.total} 场 · 缺失 ${all.total-m.count} 场`;
  const cards=isWin?[
    ['已知胜率',pct(all.p),`${all.wins} 胜 · ${all.losses} 负`],
    ['估计胜率 · 30% 情景',pct(all.estimate),all.unassigned?'含结果异常场，未纳入估计':`${all.wins} + ${all.eligible} × 30% 预计胜场`],
    ['当前对局',number(all.total),coverage],
    ['已知胜率 · 95% 区间',`${pct(all.low)}–${pct(all.high)}`,'Wilson 区间，仅基于已知胜负'],
    ['含未知的胜率范围',`${pct(all.boundLow)}–${pct(all.boundHigh)}`,'未知全负 → 未知全胜'],
    ['结果未知',number(all.unknown),`${pct(all.total?all.unknown/all.total:null)} 的当前样本`]
  ]:[
    [config.mean,fmt(m.mean),coverage],
    metric==='rating'?['已记录积分净变化',signed(m.total),'有值场次合计；未补估缺失场']:['声望中位数',number(m.median),'一半有值场次不高于此值'],
    ['当前对局',number(all.total),coverage],
    ['中间 50% 对局',`${fmt(m.q1)} ～ ${fmt(m.q3)}`,'第 25–75 百分位；描述分布，不是置信区间'],
    [metric==='rating'?'胜局平均加分':'胜局平均声望',fmt(m.win.mean),`有值 ${m.win.count} / ${all.wins} 胜场`],
    [metric==='rating'?'负局平均扣分':'负局平均声望',fmt(m.loss.mean),`有值 ${m.loss.count} / ${all.losses} 负场`]
  ];
  $('kpis').innerHTML=cards.map(([label,value,hint],i)=>`<div class="kpi ${i===0?'primary-kpi':''}"><small>${label}</small><strong>${value}</strong><span>${hint}</span></div>`).join('');
  $('scenario-note').hidden=!isWin;
  $('scenario-note').textContent='按你的规定：所有没有最终战报的对局，一律假设为提前离场，胜率取 30%，包括新增及未调查的录像。估计胜率 =（已知胜场 + 无最终战报场数 × 30%）÷ 总场数。筛选后的各组也统一按此规则计算。此情景仅用于胜率，不改写逐场实际结果，也不补估声望或积分；已有战报但结果异常的对局不按无战报处理。';
  $('result-note').textContent=isWin?'比较胜负结果，保留未知比例、置信区间和 30% 情景。':metric==='rating'?'比较本人每场实际加减分。场均反映有值对局的得分效率，净变化是这些对局的合计。胜局和负局分别统计；缺失场不补估。':'比较本人声望表现。显示均值、中位数和分布，并分别比较胜局、负局。声望保留原值，可超过 200。';
}
function renderGroupTable(list,all){
  const metric=state.metric,isWin=metric==='win',fmt=RESULTS[metric].format;
  const headers=isWin?['标签组合','场数 / 已知','胜 / 负','估计胜率 · 30% 情景','已知胜率 · 95% 区间','相对其余胜率差','未知','含未知的上下界']:
    ['标签组合','总场 / 有值',RESULTS[metric].mean,'中位数 · 中间 50%',metric==='rating'?'已记录积分合计':'胜局 / 负局平均声望',metric==='rating'?'胜局加分 / 负局扣分':'胜 / 负','平均声望','平均输出'];
  $('group-head').innerHTML=headers.map((label,i)=>`<th ${isWin&&i===7?'class="bounds-col"':''}>${label}</th>`).join('');
  $('groups-table').classList.toggle('bounds-hidden',isWin&&!state.bounds);
  $('groups').innerHTML=list.length?list.map((g,i)=>{
    const m=resultSummary(g,metric),diff=resultDifference(g,all,metric),missing=g.total-m.count;
    const restTotal=all.total-g.total,robust=isWin&&restTotal>0&&g.boundHigh<(all.wins-g.wins)/restTotal;
    const title=`<td class="group-name"><button data-group="${i}">${JSON.parse(g.key).map(esc).join(' / ')}</button>${m.count<10?'<span class="small">小样本 · 先看对局</span>':''}${robust?'<span class="robust" title="当前样本中，本组未知全胜、其余未知全负，本组仍较低。">本组上界仍低于其余下界</span>':''}</td>`;
    const difference=`<td class="${diff==null?'':diff<0?'negative':'positive'}">${diff==null?'—':signed(isWin?diff*100:diff)+(isWin?' pp':'')}</td>`;
    const missingCell=`<td class="unknown">${missing}<span class="small">${pct(g.total?missing/g.total:null)}</span></td>`;
    const outcomes=`${g.wins} / ${g.losses}`;
    const content=isWin?
      `<td>${g.total} / ${g.known}</td><td>${outcomes}</td><td class="estimate-cell">${pct(g.estimate)}<span class="small">${g.unassigned?'结果异常未估计':g.eligible?'无战报按 30%':'无须补估'}</span></td><td class="rate-cell"><div class="rate-main"><b>${pct(g.p)}</b><span class="ci">${pct(g.low)}–${pct(g.high)}</span></div>${g.p!=null?`<div class="track"><i class="interval" style="left:${g.low*100}%;width:${(g.high-g.low)*100}%"></i><i class="point" style="left:${g.p*100}%"></i></div>`:''}</td>${difference}${missingCell}<td class="bounds-col">${pct(g.boundLow)}–${pct(g.boundHigh)}</td>`:
      `<td>${g.total} / ${m.count}</td><td class="metric-primary ${metric==='rating'&&m.mean!=null?(m.mean<0?'negative':'positive'):''}">${fmt(m.mean)}</td><td>${fmt(m.median)}<span class="small">${fmt(m.q1)} ～ ${fmt(m.q3)}</span></td><td>${metric==='rating'?signed(m.total):fmt(m.win.mean)+' / '+fmt(m.loss.mean)}${metric==='prestige'?`<span class="small">有值 ${m.win.count} 胜 / ${m.loss.count} 负</span>`:''}</td><td>${metric==='rating'?fmt(m.win.mean)+' / '+fmt(m.loss.mean)+`<span class="small">有值 ${m.win.count} 胜 / ${m.loss.count} 负</span>`:outcomes}</td><td title="本人声望；有值 ${g.prestige.count} / ${g.total} 场">${number(g.prestige.mean)}</td><td title="本人造成的伤害；有值 ${g.damage.count} / ${g.total} 场">${number(g.damage.mean)}</td>`;
    return `<tr ${g.key===selectedGroup?'class="selected"':''}>${title}${content}</tr>`;
  }).join(''):'<tr><td colspan="8" class="empty">没有符合条件的分组。试着放宽筛选或降低最小有值场数。</td></tr>';
}
function render(){
  renderDateControls();
  const rows=filtered(),all=stats(rows),groups=new Map();
  for(const r of rows){const key=JSON.stringify(state.dims.map(d=>r.tags[d]));if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}
  const list=[...groups.entries()].map(([key,rows])=>({key,rows,...stats(rows)})).filter(g=>resultSummary(g,state.metric).count>=state.min);
  list.sort((a,b)=>compareResults(a,b,state.metric,state.sort));
  renderOverview(all);
  $('quality').innerHTML=`<strong>数据覆盖：</strong>当前 ${all.unknown} 场结果未知，其中 ${all.eligible} 场无最终战报，统一假设提前离场并按 30% 估计。${all.unassigned?`另有 ${all.unassigned} 场结果异常，未纳入估计。`:''}${all.unknown?'<button id="inspect-unknown">查看未知场</button>':''}`;
  if($('inspect-unknown'))$('inspect-unknown').onclick=()=>{state.filters=state.filters.filter(f=>f.key!=='result').concat([{key:'result',values:['未知']}]);selectedGroup=null;renderControls();render();};
  const config=RESULTS[state.metric];
  $('groups-title').textContent=config.label+' · 分组比较';
  $('group-caption').textContent=state.dims.map(k=>dimension(k).label).join(' × ')+` · 当前${config.mean} ${config.format(resultSummary(all,state.metric).mean)} · ${list.length} / ${groups.size} 组`+(state.metric==='win'?' · 差值与其余对局比较':'');
  $('post-label-note').hidden=!state.dims.concat(state.filters.map(f=>f.key)).some(k=>dimension(k)?.kind==='战后');
  renderGroupTable(list,all);
  document.querySelectorAll('[data-group]').forEach(el=>el.onclick=()=>{selectedGroup=list[+el.dataset.group].key;render();$('battles-section').scrollIntoView({behavior:'smooth',block:'start'});});
  const selected=list.find(g=>g.key===selectedGroup);
  $('battles-section').hidden=!selected;
  if(selected){
    $('battles-title').textContent=JSON.parse(selected.key).join(' / ')+' · '+selected.total+' 场';
    const sorted=[...selected.rows].sort((a,b)=>b.started_at.localeCompare(a.started_at));
    $('battles').innerHTML=sorted.map((r,i)=>`<tr><td><button class="quiet" data-battle="${i}">${esc(r.started_at.slice(5,19).replace('T',' '))}</button></td><td>${esc(r.tags.map)}<span class="small">${esc(r.tags.vehicle)}</span></td><td>${esc(r.tags.side)}</td><td class="${r.result==='win'?'positive':r.result==='unknown'?'unknown':'negative'}">${resultName[r.result]}</td><td>${number(r.damageDealt)}</td><td>${number(r.comp7PrestigePoints)}</td><td>${signed(r.rating_delta)}</td><td>${esc(r.tags.recording_end)}</td></tr>`).join('');
    document.querySelectorAll('[data-battle]').forEach(el=>el.onclick=()=>showDetail(sorted[+el.dataset.battle]));
  }
}

function participantsTable(r,side){
  const list=r.players.filter(p=>p.is_ally===side).sort((a,b)=>(b.comp7PrestigePoints??-Infinity)-(a.comp7PrestigePoints??-Infinity));
  if(!list.length)return '<p class="hint">没有有效最终战报，双方表现与声望保持缺失。</p>';
  const table=fields=>`<div class="table-wrap roster-wrap" tabindex="0" aria-label="${side?'我方':'对方'}战报，可横向滚动"><table class="roster"><thead><tr><th>车辆 / 分段</th>${fields.map(f=>`<th title="${esc(f.key)}">${esc(f.label)}</th>`).join('')}</tr></thead><tbody>${list.map(p=>`<tr ${p.is_self?'class="self-row"':''}><td>${p.is_self?'<b>本人 · </b>':''}${esc((p.vehicle||'未知').split(':').pop())}<span class="small">${esc(p.rank_display)}</span></td>${fields.map(f=>`<td>${number(p[f.key])}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
  return table(data.performance_fields.slice(0,7))+`<details class="extra-metrics"><summary>更多战报：协助、血量、射击与占点</summary>${table(data.performance_fields.slice(7))}</details>`;
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
  const metrics=[['声望',r.comp7PrestigePoints],['伤害',r.damageDealt],['侦查协助',r.damageAssistedRadio],['断带协助',r.damageAssistedTrack],['格挡',r.damageBlockedByArmor],['击杀',r.kills],['生存秒数',r.lifeTime],['战前积分',r.rating_before],['积分变化',r.rating_delta],['战后积分',r.rating_after]];
  const participants=side=>{
    return participantsTable(r,side);
  };
  $('detail-body').innerHTML=`<h2>${esc(r.tags.map)} · ${esc(r.tags.vehicle)}</h2><p class="hint">${esc(r.started_at.replace('T',' '))} · ${esc(r.tags.side)} · ${resultName[r.result]}${!r.vehicle?' · 车辆来自文件头，未用战报复核':''}</p><div class="tag-list">${['vehicle_class','lobby_type','completeness','recording_end'].map(k=>`<span>${esc(dimension(k).label)}：${esc(r.tags[k])}</span>`).join('')}</div>${r.result==='unknown'?`<div class="note">最终结果未知。${r.result_status==='no_result_block'?'按规定假设提前离场，本场以 30% 胜率参与情景估计。':''}缺失的伤害、积分或分段仍保持未知。</div>`:''}<div class="detail-grid"><div class="detail-card"><h3>个人表现与积分</h3><dl class="stat-list">${metrics.map(([k,v])=>`<div><dt>${k}</dt><dd>${k==='积分变化'?signed(v):number(v)}</dd></div>`).join('')}</dl></div><div class="detail-card"><h3>录制时间线</h3><p class="hint">以下均为录像内秒数；事件来自实际数据包。</p><div class="timeline">${timeline.length?timeline.sort((a,b)=>a[0]-b[0]).map(([t,s])=>`<p><b>${t.toFixed(1)}s</b>${s}</p>`).join(''):'<p class="hint">此场未做二进制调查。</p>'}</div>${event?.seconds_from_death_to_end!=null?`<p class="hint">阵亡后继续记录 ${event.seconds_from_death_to_end.toFixed(1)} 秒。</p>`:''}${event?.seconds_end_to_next_start!=null?`<p class="hint">下一场录像约在结束后 ${event.seconds_end_to_next_start.toFixed(0)} 秒开始。</p>`:''}</div></div><h3>全场赛后战报 · ${r.players.length?r.players.length+' 人':'未记录'}</h3><p class="hint">双方按声望从高到低排列，本人高亮。全员 19 项汇总来自最终战报；不代表全员完整位置或事件轨迹。精确积分变化仅本人可见。声望保留原值，可超过 200。</p><section class="team-report"><h3>我方 · 含本人</h3>${participants(true)}</section><section class="team-report"><h3>对方</h3>${participants(false)}</section><h3>原始录像与追溯</h3><p class="path">${esc(r.replay_path)}</p><p class="hint">SHA-256：${esc(r.sha256)}<br>出生点配置坐标：${esc(JSON.stringify(r.spawn_points))}；这是队伍配置点，不是实测轨迹。</p><div class="detail-actions"><button id="copy-path">复制录像路径</button><a class="download" href="/replay/${encodeURIComponent(r.id)}" download>下载原始录像</a></div>`;
  $('copy-path').onclick=async()=>{try{await navigator.clipboard.writeText(r.replay_path);$('copy-path').textContent='路径已复制';}catch{$('copy-path').textContent='请在上方选中路径复制';}};
  $('detail').showModal();
  $('detail-body').scrollTop=0;
}
function wire(){
  document.querySelectorAll('[data-date-preset]').forEach(button=>button.onclick=()=>{
    Object.assign(state,datePresetRange(button.dataset.datePreset));selectedGroup=null;render();
  });
  document.querySelectorAll('[data-result]').forEach(button=>button.onclick=()=>{state.metric=button.dataset.result;state.sort='result_asc';renderResultControls();render();});
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
  $('load-view').onclick=()=>{try{const saved=JSON.parse(localStorage.getItem('onslaught-view-v1'));state=restoreState(saved);selectedGroup=null;renderControls();render();$('view-status').textContent=saved.dims.some(k=>RETIRED_RANK_DIMENSIONS.has(k))||saved.filters.some(retiredFilter)?'已恢复；分段标签已更新，过时筛选已移除，请重新选择局型筛选。':'已恢复保存的视图';}catch{$('view-status').textContent='没有可恢复的视图';}};
}
async function init(){try{const response=await fetch('/api/data');if(!response.ok)throw Error('数据读取失败');data=await response.json();state=defaultState();$('snapshot').textContent=`本地快照 · ${data.metadata.window_start.slice(0,10)} 至 ${data.metadata.cutoff.slice(0,10)} · ${data.metadata.recent_count} 场`;$('startup-message').textContent=data.metadata.startup_message||'';$('startup-message').hidden=!data.metadata.startup_message;wire();renderControls();render();}catch(error){$('error').hidden=false;$('error').textContent='加载失败：'+error.message;}}
init();
