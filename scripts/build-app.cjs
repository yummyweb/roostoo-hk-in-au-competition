// Packages the local research engine with a native macOS Electron window.
const path = require('node:path');
(async () => {
 const { packager } = await import('@electron/packager');
 const apps = await packager({dir:'.',name:'Flight Deck',platform:'darwin',arch:'arm64',out:'dist',overwrite:true,asar:false,
  electronVersion:require('electron/package.json').version,
  icon:'desktop/icon.icns',
  ignore:[/^\/(?:data|runs|tests|artifacts|dist|\.venv-lstm|\.git|\.env|\.agents|\.codex)(?:\/|$)/,/\.pdf$/,/^\/\.env/],
  appBundleId:'com.roostoo.flightdeck',appCategoryType:'public.app-category.finance',
 });
 console.log(apps.join('\n'));
})().catch(e=>{console.error(e);process.exit(1)});
