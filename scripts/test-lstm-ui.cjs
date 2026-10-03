const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
(async()=>{
 const profile=await fs.mkdtemp('/private/tmp/flight-lstm-ui-');
 const app=await electron.launch({...(process.env.FLIGHT_PACKAGED?{executablePath:process.env.FLIGHT_PACKAGED,args:[]}:{args:[path.resolve('.')]}),env:{...process.env,FLIGHT_USER_DATA:profile},timeout:60000});
 try{
  const page=await app.firstWindow(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.waitForFunction(()=>document.querySelector('#tradeRows tr'));
  await page.locator('#newRun').click();
  await page.locator('select[name="strategy"]').selectOption('lstm_prediction');
  assert.ok(await page.locator('#lstmNote').isVisible());
  await page.locator('#submitRun').click();
  assert.match(await page.locator('#runError').innerText(),/historical hourly CSV/);
  await page.locator('#runDialog .close-dialog').click();
  const file=path.resolve(process.env.LSTM_RUN||'runs/lstm-prediction-20/run.json');
  await app.evaluate(({dialog},target)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[target]});},file);
  await page.locator('#openRun').click();
  await page.waitForFunction(()=>document.querySelector('#runName').textContent==='LSTM Prediction');
  const run=JSON.parse(await fs.readFile(file,'utf8'));
  if(run.trades.length){
   await page.locator('#tradeRows tr').first().click();
   assert.ok(await page.locator('#forecastDetail').isVisible());
   assert.match(await page.locator('#forecastMove').innerText(),/12 hours/);
   assert.match(await page.locator('#entryReason').innerText(),/LSTM Prediction/);
  }
  await page.locator('#assumptions').click();
  assert.match(await page.locator('#infoContent').innerText(),/Return MAE/);
  await page.locator('#infoDialog .close-dialog').click();
  await fs.mkdir('artifacts',{recursive:true});await page.screenshot({path:'artifacts/lstm-prediction.png',fullPage:true});
  // Train via the real desktop Python bridge on a small slice of actual Binance candles.
  const dataset=path.resolve('data/lstm-ui-market.csv');
  await app.evaluate(({dialog},target)=>{dialog.showOpenDialog=async()=>({canceled:false,filePaths:[target]});},dataset);
  await page.locator('#newRun').click();await page.locator('#chooseData').click();await page.locator('#submitRun').click();
  await page.waitForFunction(()=>!document.querySelector('#runDialog').open,{timeout:120000});
  assert.equal(await page.locator('#runName').innerText(),'LSTM Prediction');
  assert.equal(await page.locator('#sourceBadge').innerText(),'HISTORICAL REPLAY');
  assert.deepEqual(errors,[]);
  console.log('LSTM desktop tests passed: market-data requirement, forecasts, model diagnostics, and real training through the Python bridge.');
 }finally{await app.close();}
})().catch(e=>{console.error(e);process.exit(1)});
