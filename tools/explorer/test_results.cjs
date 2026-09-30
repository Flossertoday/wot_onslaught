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
assert.throws(()=>context.restoreState({...saved,dims:['bad']}));
console.log('Result views: distributions, outcome means, excluded-group baselines, missing-last sorting and saved-view migration passed.');
