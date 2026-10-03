'use strict';
const $ = id => document.getElementById(id);
const money = n => n == null ? '—' : new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(n);
const number = (n,d=2) => n == null ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits:d, minimumFractionDigits:d });
const pct = n => n == null ? '—' : `${n >= 0 ? '+' : ''}${number(n*100)}%`;
const date = (n, time=false) => n == null ? '—' : new Date(n).toLocaleString('en-GB', { timeZone:'UTC', day:'2-digit', month:'short', ...(time ? {hour:'2-digit',minute:'2-digit'} : {year:'numeric'}) });
const escape = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = { run:null, selected:null, mode:'equity', pair:null, page:0, sort:'time', descending:true, start:null, end:null, dataPath:null, markers:[], drag:null };
let toastTimer;
function toast(text) { $('toast').textContent=text; $('toast').classList.remove('hidden'); clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),5500); }
function text(id,s) { $(id).textContent=s; }
function tone(el,n) { el.classList.toggle('positive',n>=0); el.classList.toggle('negative',n<0); }
function setRun(run) {
  state.run=run; state.selected=null; state.pair=run.pairs[0]; state.page=0;
  state.start=run.evaluation_start; state.end=run.evaluation_end;
  text('runName',run.name); text('runMeta',`${run.pairs.map(p=>p.split('/')[0]).join(' + ')}   /   ${run.interval_ms/60000}m candles   /   ${date(run.evaluation_start)} — ${date(run.evaluation_end)}`);
  text('sourceBadge',run.manifest.synthetic?'SYNTHETIC DEMO':'HISTORICAL REPLAY');
  const m=run.metrics;
  text('equity',money(m.final_equity)); text('return',`${pct(m.total_return)}  ·  ${money(m.net_pnl)} net P&L`); tone($('return'),m.total_return);
  text('sharpe',number(m.sharpe)); text('drawdown',`−${number(m.max_drawdown*100)}%`); text('winrate',m.win_rate==null?'—':number(m.win_rate*100)+'%');
  text('tradeCount',`${m.closed_trades} closed trades · ${m.open_trades} open`);
  text('dataLabel',run.manifest.synthetic?'Synthetic fixture · not performance evidence':'Historical OHLCV · modeled execution');
  text('frictionLabel',`${run.config.fee_bps} bps fees · ${run.config.slippage_bps} bps slippage`);
  text('footerNote',`${run.id} · ALL TIMES UTC`);
  $('pairFilter').innerHTML='<option value="all">All pairs</option>'+run.pairs.map(p=>`<option>${escape(p)}</option>`).join('');
  $('search').value=''; $('sideFilter').value='all'; $('outcomeFilter').value='all';
  $('inspectorEmpty').classList.remove('hidden'); $('tradeDetail').classList.add('hidden');
  text('tradeId','SELECT A TRADE'); text('markerCount',`/ ${run.orders.filter(o=>o.status==='FILLED').length} executions`);
  renderRows(); renderChart();
  if(run.trades.length) selectTrade(run.trades[run.trades.length-1].id);
}
function filtered() {
  if(!state.run) return [];
  const query=$('search').value.toLowerCase(), pair=$('pairFilter').value, side=$('sideFilter').value, outcome=$('outcomeFilter').value;
  return state.run.trades.filter(t=>(pair==='all'||t.pair===pair)&&(side==='all'||t.side===side)&&
    (outcome==='all'||(outcome==='open'?t.status==='OPEN':t.status==='CLOSED'&&(outcome==='win'?t.net_pnl>0:t.net_pnl<0)))&&
    `${t.id} ${t.pair} ${t.entry_reason} ${t.exit_reason||''}`.toLowerCase().includes(query)).sort((a,b)=>
    ((state.sort==='pnl'?a.net_pnl-b.net_pnl:a.entry_time-b.entry_time)||(a.id-b.id))*(state.descending?-1:1));
}
function renderRows() {
  const all=filtered(), pages=Math.max(1,Math.ceil(all.length/10)); state.page=Math.min(state.page,pages-1);
  const rows=all.slice(state.page*10,state.page*10+10);
  $('tradeRows').innerHTML=rows.map(t=>`<tr tabindex="0" role="button" aria-label="Inspect trade ${t.id}, ${escape(t.pair)}" data-id="${t.id}" class="${t.id===state.selected?'selected':''}"><td><div class="pair-cell"><div class="coin">${escape(t.pair[0])}</div><div><strong>${escape(t.pair)}</strong><small>#${String(t.id).padStart(3,'0')} · ${escape(t.regime)}</small></div></div></td><td><span class="side-tag ${t.side==='SHORT'?'short':''}">${t.side==='LONG'?'↗':'↘'} ${escape(t.side)}</span></td><td>${date(t.entry_time,true)}</td><td>${money(t.entry_price)} <span class="muted">→</span> ${money(t.exit_price??t.mark_price)}</td><td>${number(t.holding_hours,1)}h</td><td class="pnl-cell ${t.net_pnl>=0?'positive':'negative'}"><strong>${money(t.net_pnl)}</strong><small>${pct(t.return_pct)}</small></td><td><span class="status-tag ${t.status==='OPEN'?'open':''}">${t.status==='OPEN'?'◌ OPEN':'● CLOSED'}</span></td><td class="muted">↗</td></tr>`).join('');
  text('ledgerCount',all.length); text('pageLabel',all.length?`Showing ${state.page*10+1}–${Math.min((state.page+1)*10,all.length)} of ${all.length} trades`:'0 trades'); text('pageNumber',`${state.page+1} / ${pages}`);
  $('noTrades').classList.toggle('hidden',all.length>0); $('prevPage').disabled=state.page===0; $('nextPage').disabled=state.page>=pages-1;
  $('tradeRows').querySelectorAll('tr').forEach(row=>{ row.onclick=()=>selectTrade(Number(row.dataset.id)); row.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();selectTrade(Number(row.dataset.id));}}; });
}
function selectTrade(id) {
  const t=state.run.trades.find(t=>t.id===id); if(!t) return;
  state.selected=id; state.pair=t.pair;
  $('inspectorEmpty').classList.add('hidden'); $('tradeDetail').classList.remove('hidden');
  text('tradeId',`TRADE #${String(id).padStart(3,'0')}`); text('tradePair',t.pair); text('tradeCoin',t.pair[0]);
  text('tradeSide',t.side); text('tradeStatus',t.status); text('tradePnl',money(t.net_pnl)); text('tradeReturn',pct(t.return_pct)); tone($('tradePnl'),t.net_pnl); tone($('tradeReturn'),t.net_pnl);
  text('entryPrice',money(t.entry_price)); text('exitPrice',money(t.exit_price??t.mark_price)); text('entryTime',date(t.entry_time,true)); text('exitTime',t.exit_time?date(t.exit_time,true):'Marked · position open');
  text('positionSize',`${number(t.quantity,6)} ${t.pair.split('/')[0]}`); text('holdTime',`${number(t.holding_hours,1)} hours`); text('tradeFees',money(t.entry_fee+t.exit_fee)); text('initialStop',t.initial_stop==null?'Portfolio risk cap':money(t.initial_stop));
  const forecast=t.features?.predicted_price;
  $('forecastDetail').classList.toggle('hidden',forecast==null);
  if(forecast!=null){text('forecastPrice',money(forecast));text('forecastMove',`${pct(t.features.predicted_return)} over ${t.features.forecast_horizon} hours`);}
  $('rankingDetail').classList.toggle('hidden',t.features?.rank_score==null);
  if(t.features?.rank_score!=null){const trend=state.run.config.rank_model==='trend_budget';text('rankingScore',trend?`${number(t.features.trend_strength*4,0)} / 4 upward trends`:`Rank score ${number(t.features.rank_score,4)}`);text('rankingVotes',`Annualized trailing volatility ${pct(t.features.volatility*Math.sqrt(365*24))}`);text('rankingDescription',trend?'Signals over 3, 7, 14 and 30 days · unused risk budget stays in cash':'Relative asset score at entry · not a price forecast');}
  text('entryReason',t.entry_reason); text('exitReason',t.exit_reason||'Position is still open. P&L includes entry fees; exit fees have not been charged.');
  const at=state.run.trades.findIndex(x=>x.id===id); $('prevTrade').disabled=at===0; $('nextTrade').disabled=at===state.run.trades.length-1;
  renderRows(); drawTrade(t); renderChart();
}
function canvasContext(canvas) {
  const rect=canvas.getBoundingClientRect(), dpr=window.devicePixelRatio||1;
  canvas.width=Math.round(rect.width*dpr); canvas.height=Math.round(rect.height*dpr);
  const ctx=canvas.getContext('2d'); ctx.scale(dpr,dpr); return {ctx,w:rect.width,h:rect.height};
}
function line(ctx,points,color,width=1.6) {
  if(!points.length) return; ctx.beginPath(); ctx.moveTo(...points[0]); for(let i=1;i<points.length;i++)ctx.lineTo(...points[i]); ctx.strokeStyle=color; ctx.lineWidth=width; ctx.stroke();
}
function nearest(series,t) {
  let lo=0,hi=series.length-1;
  while(lo<hi){const mid=Math.floor((lo+hi)/2); if(series[mid].timestamp<t)lo=mid+1;else hi=mid;}
  return series[lo];
}
function renderChart() {
  if(!state.run)return;
  const {run,mode,start,end}=state, {ctx,w,h}=canvasContext($('mainChart'));
  if(w<1)return;
  let series=mode==='price'?run.bars.filter(b=>b.pair===state.pair).map(b=>({timestamp:b.timestamp+run.interval_ms,value:b.close})):run.equity_curve.map(p=>({timestamp:p.timestamp,value:mode==='drawdown'?-p.drawdown*100:p.equity,benchmark:p.benchmark}));
  const visible=series.filter(p=>p.timestamp>=start&&p.timestamp<=end);
  $('chartEmpty').classList.toggle('hidden',visible.length>0);
  text('chartLabel',mode==='price'?`${state.pair} · all executions`:mode==='drawdown'?'Peak-to-trough loss':'Portfolio equity');
  text('dateRange',`${date(start)} — ${date(end)}`);
  document.querySelectorAll('#chartModes button').forEach(b=>b.classList.toggle('selected',b.dataset.mode===mode));
  if(!visible.length)return;
  const benchmark=mode==='equity'&&$('benchmark').checked;
  const vals=visible.flatMap(p=>benchmark?[p.value,p.benchmark]:[p.value]).filter(Number.isFinite);
  let low=Math.min(...vals),high=Math.max(...vals),pad=(high-low)*.15||Math.max(1,high*.01); low-=pad;high+=pad;
  if(mode==='drawdown')high=.2;
  const left=10,right=w-76,top=14,bottom=h-28;
  const x=t=>left+(t-start)/(end-start)*(right-left),y=v=>bottom-(v-low)/(high-low)*(bottom-top);
  ctx.font='9px SFMono-Regular,Consolas,monospace';ctx.textBaseline='middle';
  for(let i=0;i<=4;i++){const yy=top+(bottom-top)*i/4,v=high-(high-low)*i/4;ctx.strokeStyle='#29362d';ctx.setLineDash([2,5]);ctx.beginPath();ctx.moveTo(left,yy);ctx.lineTo(right,yy);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#768e7e';ctx.fillText(mode==='drawdown'?`${number(v,1)}%`:money(v),right+12,yy);}
  for(let i=0;i<=4;i++){const t=start+(end-start)*i/4;ctx.fillStyle='#6f8677';ctx.fillText(new Date(t).toLocaleDateString('en-GB',{timeZone:'UTC',day:'2-digit',month:'short'}),Math.min(right-35,x(t)),h-10);}
  const points=visible.map(p=>[x(p.timestamp),y(p.value)]);
  const fill=ctx.createLinearGradient(0,top,0,bottom);fill.addColorStop(0,mode==='drawdown'?'#b867582a':'#9bc8a027');fill.addColorStop(1,'#7bc68900');
  ctx.beginPath();ctx.moveTo(points[0][0],bottom);points.forEach(p=>ctx.lineTo(...p));ctx.lineTo(points[points.length-1][0],bottom);ctx.closePath();ctx.fillStyle=fill;ctx.fill();
  if(benchmark)line(ctx,visible.map(p=>[x(p.timestamp),y(p.benchmark)]),'#a28560',1);
  line(ctx,points,mode==='drawdown'?'#e09481':'#b5e7bb',1.65);
  state.markers=[];
  for(const t of run.trades){
    if(mode==='price'&&t.pair!==state.pair)continue;
    for(const entry of [true,false]){
      const time=entry?t.entry_time:t.exit_time;if(time==null||time<start||time>end)continue;
      const p=nearest(series,time);if(!p)continue;
      const xx=x(time),yy=y(mode==='price'?(entry?t.entry_price:t.exit_price):p.value);
      const selected=t.id===state.selected,color=selected?'#f5ad79':(entry?'#b5e7bb':'#91a198');
      ctx.fillStyle=selected?'#f5ad79':'#17251d';ctx.strokeStyle=color;ctx.lineWidth=selected?2:1;
      ctx.beginPath();if(entry){ctx.moveTo(xx,yy-5);ctx.lineTo(xx-4,yy+3);ctx.lineTo(xx+4,yy+3);ctx.closePath();}else{ctx.arc(xx,yy,3.5,0,Math.PI*2);}ctx.fill();ctx.stroke();
      state.markers.push({x:xx,y:yy,id:t.id,time,entry});
    }
  }
  state.plot={x,y,left,right,top,bottom,series};
  drawTimeline();
}
function drawTimeline(){
  const {ctx,w,h}=canvasContext($('timeline')),r=state.run,s=r.equity_curve;
  const min=Math.min(...s.map(p=>p.equity)),max=Math.max(...s.map(p=>p.equity));
  const x=t=>(t-r.evaluation_start)/(r.evaluation_end-r.evaluation_start)*w;
  line(ctx,s.map(p=>[x(p.timestamp),h-7-(p.equity-min)/(max-min||1)*(h-16)]),'#557961',1);
  ctx.fillStyle='#c8eacf13';ctx.fillRect(x(state.start),0,x(state.end)-x(state.start),h);
  ctx.strokeStyle='#657e6d';ctx.strokeRect(x(state.start),1,x(state.end)-x(state.start),h-2);
  r.trades.forEach(t=>{ctx.fillStyle=t.id===state.selected?'#f5ad79':'#708c78';ctx.fillRect(x(t.entry_time),h-5,2,4);});
}
function drawTrade(t){
  const {ctx,w,h}=canvasContext($('tradeChart'));
  const end=t.exit_time||state.run.evaluation_end;
  const forecast=t.features?.predicted_price;
  const forecastTime=forecast==null?end:t.entry_signal_time+1+t.features.forecast_horizon*state.run.interval_ms;
  const plotEnd=Math.max(end,forecastTime),span=Math.max(plotEnd-t.entry_time,6*state.run.interval_ms);
  const bars=state.run.bars.filter(b=>b.pair===t.pair&&b.timestamp>=t.entry_time-span*.15&&b.timestamp<=plotEnd+span*.15);
  if(!bars.length)return;
  const vals=bars.map(b=>b.close).concat([t.entry_price,t.exit_price??t.mark_price]);
  if(forecast!=null)vals.push(forecast);
  const lo=Math.min(...vals),hi=Math.max(...vals);const x=t=>18+(t-bars[0].timestamp)/(Math.max(forecastTime,bars[bars.length-1].timestamp+state.run.interval_ms)-bars[0].timestamp||1)*(w-36),y=v=>h-12-(v-lo)/(hi-lo||1)*(h-24);
  const color=t.net_pnl>=0?'#b5e7bb':'#e09b91';
  ctx.fillStyle='#b5e7bb08';ctx.fillRect(x(t.entry_time),8,x(end)-x(t.entry_time),h-16);
  line(ctx,bars.map(b=>[x(b.timestamp+state.run.interval_ms),y(b.close)]),color,1.4);
  if(forecast!=null){ctx.setLineDash([4,3]);line(ctx,[[x(t.entry_signal_time+1),y(t.features.close)],[x(forecastTime),y(forecast)]],'#f5ad79',1.2);ctx.setLineDash([]);}
  for(const [time,value] of [[t.entry_time,t.entry_price],[end,t.exit_price??t.mark_price]]){ctx.beginPath();ctx.arc(x(time),y(value),3,0,Math.PI*2);ctx.fillStyle='#f5ad79';ctx.fill();}
}
function clampWindow(start,end){
  const r=state.run,full=r.evaluation_end-r.evaluation_start,span=Math.min(full,Math.max(r.interval_ms*12,end-start));
  start=Math.max(r.evaluation_start,Math.min(start,r.evaluation_end-span));state.start=start;state.end=start+span;renderChart();
}
$('mainChart').addEventListener('mousemove',e=>{
  if(!state.plot)return;
  const rect=e.currentTarget.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
  if(state.drag){const delta=(e.clientX-state.drag.x)/(state.plot.right-state.plot.left)*(state.drag.end-state.drag.start);clampWindow(state.drag.start-delta,state.drag.end-delta);return;}
  const marker=state.markers.find(m=>Math.hypot(m.x-x,m.y-y)<8);
  const t=state.start+(x-state.plot.left)/(state.plot.right-state.plot.left)*(state.end-state.start),p=nearest(state.plot.series,t);
  if(!p)return;
  const content=marker?`#${marker.id} · ${marker.entry?'Entry':'Exit'} · click to inspect`:`${date(p.timestamp,true)} UTC`;
  $('chartTooltip').textContent=`${content}  |  ${state.mode==='drawdown'?number(p.value)+'%':money(p.value)}`;
  $('chartTooltip').classList.remove('hidden');$('chartTooltip').style.left=`${Math.max(5,Math.min(x,rect.width-330))}px`;$('chartTooltip').style.top=`${Math.max(0,y-42)}px`;
  e.currentTarget.style.cursor=marker?'pointer':'crosshair';
});
$('mainChart').addEventListener('mouseleave',()=>{$('chartTooltip').classList.add('hidden');});
$('mainChart').addEventListener('mousedown',e=>{if(state.run)state.drag={x:e.clientX,start:state.start,end:state.end};});
window.addEventListener('mouseup',()=>state.drag=null);
$('mainChart').addEventListener('click',e=>{const rect=e.currentTarget.getBoundingClientRect();const m=state.markers.find(m=>Math.hypot(m.x-e.clientX+rect.left,m.y-e.clientY+rect.top)<10);if(m)selectTrade(m.id);});
$('mainChart').addEventListener('wheel',e=>{if(!state.run)return;e.preventDefault();const rect=e.currentTarget.getBoundingClientRect(),f=Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width)),span=state.end-state.start,newSpan=span*(e.deltaY>0?1.18:.84),anchor=state.start+span*f;clampWindow(anchor-newSpan*f,anchor+newSpan*(1-f));},{passive:false});
$('timeline').onclick=e=>{if(!state.run)return;const rect=e.currentTarget.getBoundingClientRect(),r=state.run,t=r.evaluation_start+(e.clientX-rect.left)/rect.width*(r.evaluation_end-r.evaluation_start),span=(state.end-state.start)*.5;clampWindow(t-span/2,t+span/2);};
$('chartModes').onclick=e=>{if(e.target.dataset.mode){state.mode=e.target.dataset.mode;renderChart();}};
$('benchmark').onchange=renderChart;
function resetChart(){if(!state.run)return;state.start=state.run.evaluation_start;state.end=state.run.evaluation_end;renderChart();}
$('resetChart').onclick=resetChart;
document.querySelectorAll('[data-range]').forEach(b=>b.onclick=()=>{if(!state.run)return;document.querySelectorAll('[data-range]').forEach(x=>x.classList.toggle('selected',x===b));const days=Number(b.dataset.range);clampWindow(days?state.run.evaluation_end-days*86400000:state.run.evaluation_start,state.run.evaluation_end);});
$('focusTrade').onclick=()=>{const t=state.run.trades.find(x=>x.id===state.selected);if(!t)return;state.mode='price';state.pair=t.pair;const end=t.exit_time||state.run.evaluation_end,span=Math.max(end-t.entry_time,12*state.run.interval_ms);clampWindow(t.entry_time-span*.2,end+span*.2);};
for(const [id,direction] of [['prevTrade',-1],['nextTrade',1]])$(id).onclick=()=>{const ts=state.run.trades,i=ts.findIndex(t=>t.id===state.selected);if(ts[i+direction])selectTrade(ts[i+direction].id);};
for(const id of ['search','pairFilter','sideFilter','outcomeFilter'])$(id).addEventListener(id==='search'?'input':'change',()=>{state.page=0;if(id==='pairFilter'&&$('pairFilter').value!=='all'){state.pair=$('pairFilter').value;renderChart();}renderRows();});
$('sortTime').onclick=()=>{state.descending=state.sort==='time'?!state.descending:true;state.sort='time';text('sortTime',`ENTRY TIME ${state.descending?'↓':'↑'}`);renderRows();};
$('sortPnl').onclick=()=>{state.descending=state.sort==='pnl'?!state.descending:true;state.sort='pnl';text('sortPnl',`NET P&L ${state.descending?'↓':'↑'}`);renderRows();};
$('prevPage').onclick=()=>{state.page--;renderRows();};$('nextPage').onclick=()=>{state.page++;renderRows();};
$('tradesNav').onclick=()=>$('ledger').scrollIntoView({behavior:'smooth'});$('overviewNav').onclick=()=>window.scrollTo({top:0,behavior:'smooth'});
$('newRun').onclick=()=>$('runDialog').showModal();document.querySelectorAll('.close-dialog').forEach(b=>b.onclick=()=>b.closest('dialog').close());
$('openRun').onclick=async()=>{try{const run=await window.flight.openRun();if(run){setRun(run);toast('Run loaded. Every trade is ready to inspect.');}}catch(e){toast(e.message);}};
$('chooseData').onclick=async()=>{try{const path=await window.flight.chooseData();if(path){state.dataPath=path;text('datasetName',path.split(/[\\/]/).pop());}}catch(e){toast(e.message);}};
document.querySelector('select[name="strategy"]').onchange=e=>{$('lstmNote').classList.toggle('hidden',e.target.value!=='lstm_prediction');$('rankingNote').classList.toggle('hidden',e.target.value!=='cross_asset');document.querySelector('input[name="risk"]').disabled=e.target.value==='cross_asset';if(e.target.value==='cross_asset')document.querySelector('select[name="direction"]').value='long';};
$('runForm').onsubmit=async e=>{e.preventDefault();const form=new FormData(e.target);if(['lstm_prediction','cross_asset'].includes(form.get('strategy'))&&!state.dataPath){text('runError','Choose a historical hourly CSV for this strategy. The synthetic demo cannot be used.');return;}$('submitRun').disabled=true;text('submitRun',form.get('strategy')==='lstm_prediction'?'Training LSTM, then replaying evaluation trades…':'Replaying market events…');text('runError','');try{const config={strategy:form.get('strategy'),allow_short:form.get('direction')==='both',initial_cash:Number(form.get('initial_cash')),risk_per_trade:Number(form.get('risk')??0.5)/100,fee_bps:Number(form.get('fee_bps')),slippage_bps:Number(form.get('slippage_bps'))};const run=await window.flight.run({config,data_path:state.dataPath});setRun(run);$('runDialog').close();toast(`Backtest complete · ${run.metrics.fills} executions`);}catch(e){text('runError',e.message);}finally{$('submitRun').disabled=false;text('submitRun','Run backtest ↗');}};
function showInfo(method=false){if(!state.run)return;const r=state.run;text('infoTitle',method?'The research method':'Behind this run');
  const notes=method?['Competition screening: rule compliance → top 20 by portfolio return in each region → 40% Sortino + 30% Sharpe + 30% Calmar → code review.','The causal regime filter uses EMA trend, trailing momentum, price-path efficiency, and ATR sizing. Hybrid mode adds range mean reversion. No future labels enter signals.','Close-observed trailing stops execute at the next open. A drawdown breach latches a halt and prioritizes exits. Gaps can exceed the risk target.','For evidence, use chronological training / validation / holdout, compare passive and cash baselines, and double execution costs. Synthetic demo results prove plumbing, not an edge.']:r.warnings;
  $('infoContent').innerHTML=`<div class="info-warning">${escape(r.manifest.synthetic?'Synthetic development fixture — not historical performance.':r.manifest.source)}</div>`+notes.map(n=>`<div class="info-item">${escape(n)}</div>`).join('')+`<div class="info-item">Sortino ${number(r.metrics.sortino)} · Calmar ${number(r.metrics.calmar)} · Local composite ${number(r.metrics.composite_score)}<br>Fees ${money(r.metrics.fees)} · Active days ${r.metrics.active_days}<br>${escape(r.metrics.metric_basis)}</div><pre>${escape(JSON.stringify(r.config,null,2))}</pre>`;if(r.model){$('infoContent').innerHTML+=`<div class="info-item"><strong>LSTM Prediction</strong><br>${escape(r.model.architecture)}<br>Lookback ${r.model.sequence_bars}h · forecast ${r.model.forecast_horizon_bars}h · selected epoch ${r.model.best_epoch}<br>Return MAE ${number(r.model.forecast_metrics.return_mae*100,3)}% vs no-change ${number(r.model.forecast_metrics.zero_return_mae*100,3)}%<br>Direction accuracy ${number(r.model.forecast_metrics.directional_accuracy*100,1)}%<br>${escape(r.model.split_method)}</div>`;}if(r.ranking_model){$('infoContent').innerHTML+=`<div class="info-item"><strong>${escape(r.ranking_model.architecture)}</strong><br>${escape(r.ranking_model.target)}<br>${escape(r.ranking_model.method)}<br>Higher-cost return ${pct(r.ranking_model.cost_stress_metrics.total_return)} · annual volatility budget ${pct(r.config.target_volatility)}<br>Research preset; historical selection does not prove a future edge.</div>`;}$('infoDialog').showModal();}
$('assumptions').onclick=()=>showInfo();$('methodNav').onclick=()=>showInfo(true);
$('saveRun').onclick=async()=>{try{if(await window.flight.save({type:'json',content:JSON.stringify(state.run)}))toast('Complete run saved.');}catch(e){toast(e.message);}};
$('exportTrades').onclick=async()=>{if(!state.run)return;const keys=['id','pair','side','status','entry_time','exit_time','entry_price','exit_price','quantity','net_pnl','return_pct','entry_fee','exit_fee','entry_reason','exit_reason'];const csvCell=v=>'"'+String(v??'').replace(/^[=+@-]/,"'").replace(/"/g,'""')+'"';const content=[keys.join(','),...filtered().map(t=>keys.map(k=>typeof t[k]==='number'?t[k]:csvCell(t[k])).join(','))].join('\n');try{if(await window.flight.save({type:'csv',content}))toast('Filtered trades exported.');}catch(e){toast(e.message);}};
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{renderChart();if(state.selected)drawTrade(state.run.trades.find(t=>t.id===state.selected));},80);});
window.flight.initial().then(setRun).catch(e=>{text('runName','Workspace could not load');text('runMeta',e.message);toast('Check that Python 3.10+ is installed, then open or run a backtest.');});
