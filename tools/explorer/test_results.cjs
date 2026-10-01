// Hand-calculated groups distinguish rating, prestige and win-rate populations.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const context = vm.createContext({fetch:()=>new Promise(()=>{})});
vm.runInContext(fs.readFileSync(__dirname+'/app.js','utf8'),context);
const group=(key,rows)=>({key,rows,...context.stats(rows)});
const a=group('A',[
  {result:'win',rating_delta:5,comp7PrestigePoints:100},
  {result:'loss',rating_delta:-5,comp7PrestigePoints:200}
]);
const b=group('B',[
  {result:'win',rating_delta:30,comp7PrestigePoints:300},
  {result:'win',rating_delta:10,comp7PrestigePoints:null},
  {result:'loss',rating_delta:-20,comp7PrestigePoints:50},
  {result:'unknown',rating_delta:null,comp7PrestigePoints:null}
]);
const empty=group('Empty',[{result:'unknown'}]);
const all=context.stats([...a.rows,...b.rows]);
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-10,`${a} != ${b}`);
assert.equal(all.rating.total,20);
assert.equal(all.rating.count,5);
assert.equal(all.prestige.count,4);
assert.equal(all.rating.median,5);
assert.equal(all.rating.q1,-5);
assert.equal(all.rating.q3,10);
assert.equal(all.prestige.median,150);
assert.equal(all.prestige.q1,87.5);
assert.equal(all.prestige.q3,225);
near(all.rating.win.mean,15);
near(all.rating.loss.mean,-12.5);
assert.equal(all.rating.win.count,3);
assert.equal(all.prestige.win.count,2);
near(context.resultDifference(a,all,'rating'),-20/3);
near(context.resultDifference(a,all,'prestige'),-25);
near(context.resultDifference(a,all,'win'),-1/6);
assert.equal(context.resultDifference(all,all,'rating'),null);
assert.equal(context.resultDifference(empty,all,'prestige'),null);
assert.equal(empty.rating.median,null);
assert.equal(context.stats([{rating_delta:0}]).rating.q1,0);
assert.equal(context.stats([{rating_delta:0}]).rating.loss.mean,null);
assert.equal(context.resultSummary(b,'prestige').count,2);
assert.equal(context.resultSummary(b,'win').count,3);
for(const metric of ['rating','prestige','win']){
  assert.deepEqual([empty,b,a].sort((a,b)=>context.compareResults(a,b,metric,'result_asc')).map(g=>g.key),['A','B','Empty']);
  assert.deepEqual([empty,a,b].sort((a,b)=>context.compareResults(a,b,metric,'result_desc')).map(g=>g.key),['B','A','Empty']);
}
vm.runInContext("data={metadata:{window_start:'2026-09-23',cutoff:'2026-09-30'},dimensions:[{key:'map'}]}",context);
assert.equal(context.defaultState().metric,'rating');
const old=context.restoreState({dims:['map'],filters:[],sort:'win_rate'});
assert.equal(old.metric,'win');
assert.equal(old.sort,'result_asc');
const saved={dims:['map'],filters:[{key:'map',values:['A']}],metric:'prestige',sort:'result_desc'};
assert.equal(context.restoreState(saved).metric,'prestige');
assert.equal(context.restoreState(saved).sort,'result_desc');
assert.deepEqual(context.restoreState(saved).filters,saved.filters);
assert.throws(()=>context.restoreState({...saved,metric:'bad'}));
assert.throws(()=>context.restoreState({...saved,sort:'estimated'}));
vm.runInContext("data.dimensions.push({key:'lobby_type'})",context);
const legacy=context.restoreState({...saved,dims:['map','self_rank','enemy_ranks'],filters:[{key:'allies_high',values:['6人']},{key:'map',values:['A']}]});
assert.deepEqual(Array.from(legacy.dims),['map','lobby_type']);
assert.deepEqual(Array.from(legacy.filters),[{key:'map',values:['A']}]);
assert.equal(legacy.metric,'prestige');
const lobby=context.restoreState({...saved,dims:['lobby_type'],filters:[{key:'lobby_type',values:['高压局','黄金局']}]});
assert.deepEqual(Array.from(lobby.filters),[{key:'lobby_type',values:['高压局','黄金局']}]);
for(const retired of ['白银局','未分类']){
  const migrated=context.restoreState({...saved,filters:[{key:'map',values:['A']},{key:'lobby_type',values:['黄金局',retired]}]});
  assert.deepEqual(Array.from(migrated.filters),[{key:'map',values:['A']}]);
}
const lowPressure=context.restoreState({...saved,filters:[{key:'lobby_type',values:['低压局']}]});
assert.deepEqual(Array.from(lowPressure.filters),[{key:'lobby_type',values:['低压局']}]);
const other=context.restoreState({...saved,filters:[{key:'lobby_type',values:['其它']}]});
assert.deepEqual(Array.from(other.filters),[{key:'lobby_type',values:['其它']}]);
vm.runInContext("data.records=[{tags:{day:'2026-09-29',lobby_type:'其它'}},{tags:{day:'2026-09-29',lobby_type:'高压局'}}];state=restoreState({dims:['lobby_type'],filters:[{key:'lobby_type',values:['其它']}]})",context);
assert.equal(context.filtered().length,1);
assert.equal(context.filtered()[0].tags.lobby_type,'其它');
assert.throws(()=>context.restoreState({...saved,dims:['bad']}));

// Split damage bands must not restore obsolete filters as empty populations.
vm.runInContext("data.dimensions.push({key:'damage_band'})",context);
for(const retired of ['2000–3999','3000–4000','>4000']){
  const migrated=context.restoreState({...saved,dims:['damage_band'],filters:[{key:'map',values:['A']},{key:'damage_band',values:['<2000',retired]}]});
  assert.deepEqual(Array.from(migrated.dims),['damage_band']);
  assert.deepEqual(Array.from(migrated.filters),[{key:'map',values:['A']}]);
  assert.equal(migrated.metric,'prestige');
}
for(const value of ['<2000','2000–2999','3000–3999','≥4000','未知']){
  const filters=[{key:'damage_band',values:[value]}];
  assert.deepEqual(Array.from(context.restoreState({...saved,filters}).filters),filters);
}
vm.runInContext("data.records=['<2000','2000–2999','3000–3999','≥4000','未知'].map(value=>({tags:{day:'2026-09-29',damage_band:value}}));state=restoreState({metric:'rating',dims:['damage_band'],filters:[{key:'damage_band',values:['2000–2999','3000–3999']}]})",context);
assert.equal(context.filtered().length,2);
assert.deepEqual(Array.from(context.filtered(),r=>r.tags.damage_band),['2000–2999','3000–3999']);
const damageOrder=['<2000','2000–2999','3000–3999','≥4000','未知'];
const damageGroups=[...damageOrder].reverse().map((label,i)=>group(JSON.stringify([label]),[{result:'win',rating_delta:i,comp7PrestigePoints:i}]));
for(const metric of ['rating','prestige','win']){
  assert.deepEqual(damageGroups.slice().sort((a,b)=>context.compareResults(a,b,metric,'name',['damage_band'])).map(g=>JSON.parse(g.key)[0]),damageOrder);
}
assert.deepEqual([...damageOrder].reverse().sort((a,b)=>context.compareLabels('damage_band',a,b)),damageOrder);
assert.equal(context.defaultDimensionSort(['damage_band']),'name');
assert.equal(context.defaultDimensionSort(['map','damage_band']),'name');
assert.equal(context.defaultDimensionSort(['map']),'result_asc');
const combinations=['≥4000','<2000','未知','3000–3999','2000–2999'].map(label=>group(JSON.stringify(['地图 A',label]),[]));
assert.deepEqual(combinations.sort((a,b)=>context.compareResults(a,b,'rating','name',['map','damage_band'])).map(g=>JSON.parse(g.key)[1]),damageOrder);
assert.deepEqual(combinations.slice().reverse().sort((a,b)=>context.compareGroups(a,b,'rating','name',['map','damage_band'])).map(g=>JSON.parse(g.key)[1]),damageOrder);
vm.runInContext("state.dims=['entry_rank','damage_band'];state.sort='rank_desc';updateDimensionSort('damage_band')",context);
assert.equal(vm.runInContext('state.sort',context),'name');
vm.runInContext("updateDimensionSort('entry_rank')",context);
assert.equal(vm.runInContext('state.sort',context),'rank_desc');
vm.runInContext("state.dims=['damage_band'];updateDimensionSort()",context);
assert.equal(vm.runInContext('state.sort',context),'name');

// Performance averages use their own observed battles, even without rating data.
const performance=group('["表现组"]',[
  {result:'win',rating_delta:10,comp7PrestigePoints:100,damageDealt:3000},
  {result:'loss',rating_delta:-10,comp7PrestigePoints:200,damageDealt:0},
  {result:'unknown',rating_delta:null,comp7PrestigePoints:300,damageDealt:1500},
  {result:'unknown',comp7PrestigePoints:null,damageDealt:null},
  {result:'unknown',comp7PrestigePoints:NaN,damageDealt:Infinity}
]);
assert.equal(performance.prestige.mean,200);
assert.equal(performance.damage.mean,1500);
assert.equal(performance.damage.count,3);
assert.equal(empty.damage.mean,null);
const nodes=new Map();
context.document={getElementById:id=>{
  if(!nodes.has(id))nodes.set(id,{innerHTML:'',classList:{toggle(){}}});
  return nodes.get(id);
}};
for(const metric of ['rating','prestige','win']){
  vm.runInContext(`state.metric='${metric}'`,context);
  context.renderGroupTable([performance,{...empty,key:'["未知"]'}],performance);
  const headers=nodes.get('group-head').innerHTML;
  assert.ok(headers.includes('<th >平均声望</th>'));
  assert.ok(!headers.includes('平均输出'));
  assert.ok(!headers.includes('相对其余')&&!headers.includes('缺失')&&!headers.includes('>未知<'));
  const html=nodes.get('groups').innerHTML;
  assert.ok(html.includes('本人声望；有值 3 / 5 场">200</td>'));
  assert.ok(html.includes('本人声望；有值 0 / 1 场">—</td>'));
  assert.ok(!html.includes('本人造成的伤害'));
  const columns=metric==='rating'?8:7;
  assert.equal((headers.match(/<th /g)||[]).length,columns);
  assert.equal((html.match(/<td[ >]/g)||[]).length,columns*2);
  if(metric==='rating')assert.ok(headers.includes('<th >场均积分变化</th><th >胜率</th>'));
  if(metric==='win')assert.ok(headers.includes('class="bounds-col">含未知的上下界'));
  context.renderGroupTable([],performance);
  assert.ok(nodes.get('groups').innerHTML.includes(`colspan="${columns}"`));
}
const scenario=group('["含无战报"]',[
  {result:'win',rating_delta:20}, {result:'loss',rating_delta:-10},
  {result:'unknown',result_status:'no_result_block'}
]);
const noReport=group('["仅无战报"]',[{result:'unknown',result_status:'no_result_block'}]);
vm.runInContext("state.metric='rating'",context);
context.renderGroupTable([scenario,noReport,{...empty,key:'["结果异常"]'}],scenario);
const ratingTable=nodes.get('groups').innerHTML;
assert.match(ratingTable,/metric-primary positive">\+5<\/td><td class="estimate-cell"[^>]*>43\.3%/);
assert.match(ratingTable,/30\.0%<span class="small">无战报按 30%/);
assert.match(ratingTable,/>—<span class="small">结果异常未估计/);
assert.equal(scenario.p,.5);
console.log('Result views: distributions, outcome means, excluded-group baselines, missing-last sorting and saved-view migration passed.');
