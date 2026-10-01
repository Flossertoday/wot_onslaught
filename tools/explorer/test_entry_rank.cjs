const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const nodes=new Map();
const node=id=>{if(!nodes.has(id))nodes.set(id,{innerHTML:'',textContent:'',classList:{toggle(){}}});return nodes.get(id);};
const dimControl={dataset:{dim:'0'},value:'entry_rank'};
const filterControl={dataset:{filterValues:'0'},selectedOptions:[{value:'黄金B'}]};
const resultControls=['rating','prestige','win'].map(result=>({dataset:{result},setAttribute(){}}));
const context=vm.createContext({fetch:()=>new Promise(()=>{}),document:{getElementById:node,
  querySelectorAll:selector=>selector==='[data-dim]'?[dimControl]:selector==='[data-filter-values]'?[filterControl]:selector==='[data-result]'?resultControls:[]}});
vm.runInContext(fs.readFileSync(__dirname+'/app.js','utf8'),context);
const order=['传说','勇士',...['黄金','白银','青铜','黑铁'].flatMap(r=>[...'ABCDE'].map(d=>r+d)),'定级赛','未知'];
context.fixture={metadata:{window_start:'2026-09-23',cutoff:'2026-10-01'},dimensions:[
  {key:'map',label:'地图',kind:'赛前'},{key:'lobby_type',label:'局型',kind:'赛前'},
  {key:'entry_rank',label:'本人进场分段',kind:'赛前',order}],
  records:order.slice().reverse().map((rank,i)=>({tags:{entry_rank:rank,day:'2026-09-30',map:'A',lobby_type:'其它'},
    result:rank==='未知'?'unknown':'win',result_status:rank==='未知'?'no_result_block':'valid',rating_delta:i,comp7PrestigePoints:i}))};
vm.runInContext('data=fixture;state=defaultState()',context);
context.wire();
context.renderControls();
assert.match(node('dimensions').innerHTML,/局型.*本人进场分段/);
dimControl.onchange(); // Actual dimension selection must switch to descending rank order.
assert.equal(vm.runInContext('state.sort',context),'rank_desc');
assert.match(node('sort').innerHTML,/本人进场分段：高 → 低/);
const visibleRanks=()=>[...node('groups').innerHTML.matchAll(/data-group="\d+">([^<]+)<\/button>/g)].map(m=>m[1]);
for(const button of resultControls){
  button.onclick();
  assert.equal(vm.runInContext('state.sort',context),'rank_desc');
  assert.deepEqual(visibleRanks(),order);
}
vm.runInContext("state.filters=[{key:'entry_rank',values:[]}]",context);
context.renderControls();
const filterValues=[...node('filters').innerHTML.matchAll(/<option value="([^"]+)"[^>]*>\1<\/option>/g)].map(m=>m[1]).filter(v=>order.includes(v));
assert.deepEqual(filterValues,order);
filterControl.onchange();
assert.equal(context.filtered().length,1);
assert.equal(context.filtered()[0].tags.entry_rank,'黄金B');
assert.deepEqual(visibleRanks(),['黄金B']);
const saved=vm.runInContext('JSON.parse(JSON.stringify(state))',context);
assert.equal(context.restoreState(saved).sort,'rank_desc');
assert.equal(context.restoreState(saved).filters[0].values[0],'黄金B');
assert.throws(()=>context.restoreState({...saved,dims:['map']}));

// In combined groups, rank is primary even when the other dimension appears first.
const groups=[['A','黄金E'],['B','黄金A'],['B','黄金E'],['A','黄金A'],['A','未知']].map(values=>({key:JSON.stringify(values)}));
assert.deepEqual(groups.sort((a,b)=>context.compareGroups(a,b,'rating','rank_desc',['map','entry_rank'])).map(g=>JSON.parse(g.key)),
  [['A','黄金A'],['B','黄金A'],['A','黄金E'],['B','黄金E'],['A','未知']]);
dimControl.value='map';
dimControl.onchange();
assert.equal(vm.runInContext('state.sort',context),'result_asc');
assert.doesNotMatch(node('sort').innerHTML,/rank_desc/);
console.log('Entry rank: all divisions, three result views, combined groups, filters, saved views and dimension switching passed.');
