// Real Edge/React/FastAPI UI audit. Requests go to the isolated real backend.
const {chromium} = require('C:/Users/willi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const OUT = __dirname;
const KEY = process.env.AUDIT_DEEPSEEK_KEY;
const records = {checks:[], requests:[], errors:[], pages:{}};
function safe(x) { return JSON.parse(JSON.stringify(x).split(KEY).join('[REDACTED]')); }
function save() { fs.writeFileSync(path.join(OUT,'browser-results.json'),JSON.stringify(safe(records),null,2)); }
function check(name, details) { records.checks.push({name,details}); save(); console.log(name+': '+JSON.stringify(details)); }
(async()=>{
  const browser = await chromium.launch({headless:true,channel:'msedge'});
  const context = await browser.newContext({viewport:{width:1440,height:1000}});
  const page = await context.newPage();
  page.on('pageerror',e=>{records.errors.push(e.message);save();});
  page.on('request',r=>{
    if(r.url().includes('/api/') && r.method()==='POST') {
      records.requests.push(safe({url:r.url(),body:r.postData()})); save();
    }
  });
  await page.route('**/api/**',route=>{
    const url = new URL(route.request().url());
    return route.continue({url:'http://127.0.0.1:8011'+url.pathname+url.search});
  });
  await page.route('**/healthz',route=>route.continue({url:'http://127.0.0.1:8011/healthz'}));
  const secondResp = await context.request.post('http://127.0.0.1:8011/api/v1/sessions/quick-start',{
    data:{service_name:'audit-empty-second',prompt:'Un servicio gestiona reservas de salas de reuniones.',auto_run:false,llm_provider:'deepseek',api_key:KEY}
  });
  const second = await secondResp.json();
  await page.goto('http://127.0.0.1:3000');
  await page.getByText('audit-library',{exact:false}).first().waitFor();
  await page.getByText('audit-library',{exact:true}).first().click();
  check('default_provider', (await page.locator('header').innerText()).includes('MOCK'));
  await page.getByTitle('Configuración de Motor LLM (Principio VI: Memoria Efímera)').click();
  await page.locator('select').last().selectOption('deepseek');
  await page.locator('input[type=password]').fill(KEY);
  const verified = page.waitForResponse(r=>r.url().includes('/llm/verify') && r.status()===200,{timeout:120000});
  await page.getByRole('button',{name:'Guardar y Probar Conexión'}).click();
  check('deepseek_verified',(await (await verified).json()).status);
  await page.getByText(/CONECTADO \(/).waitFor();
  await page.getByRole('button',{name:/DeepSeek V4 Pro/}).click();
  check('changing_model_keeps_verified',await page.getByText(/CONECTADO \(/).isVisible());
  await page.getByRole('button',{name:/DeepSeek Flash/}).click();
  await page.getByRole('button',{name:'Cerrar',exact:true}).click();
  for(const name of ['Resumen','1. Requisitos','2. Arquitectura','3. Modelos & SQL','4. Código & Fix','5. Calidad SAST','6. DevOps & Demo','7. Entrega Git','Monitor Live','Blueprints']) {
    await page.getByRole('button',{name,exact:true}).click();
    await page.waitForTimeout(700);
    records.pages[name] = (await page.locator('body').innerText()).slice(0,18000); save();
    check('tab_'+name,{visible:true,errors:records.errors.length});
    if(name==='1. Requisitos'||name==='3. Modelos & SQL'||name==='Monitor Live') {
      await page.screenshot({path:path.join(OUT,'ui-'+name.replace(/[^a-zA-Z0-9]/g,'_')+'.png'),fullPage:true});
    }
  }
  await page.getByRole('button',{name:'1. Requisitos',exact:true}).click();
  await page.waitForTimeout(500);
  const transform = page.waitForResponse(r=>r.url().includes('/requirements/transform'),{timeout:180000});
  await page.getByRole('button',{name:'Descomponer con IA',exact:true}).first().click();
  const tr = await transform;
  const generated = await tr.json();
  check('ui_real_requirements',{status:tr.status(),entities:generated.entities?.length,stories:generated.userStories?.length});
  await page.getByRole('button',{name:'Aprobar y Diseñar Arquitectura →'}).click();
  await page.getByRole('button',{name:/Generar \/ Regenerar con IA/}).waitFor();
  await page.screenshot({path:path.join(OUT,'ui-approved-architecture.png'),fullPage:true});
  // Another empty session is created by the real API; switching via the sidebar must clear draft state.
  await page.getByText('audit-empty-second',{exact:true}).first().click();
  await page.waitForTimeout(700);
  const designResponse = page.waitForResponse(r=>r.url().includes('/architecture/design'),{timeout:180000});
  await page.getByRole('button',{name:/Generar \/ Regenerar con IA/}).first().click();
  const dr = await designResponse;
  const d = await dr.json();
  check('cross_session_architecture',{status:dr.status(),responseService:d.serviceName,selectedService:'audit-empty-second',secondId:second.sessionId});
  await page.screenshot({path:path.join(OUT,'ui-cross-session.png'),fullPage:true});
  // Logout is real UI state; a page reload should preserve it.
  await page.getByTitle('Cerrar sesión corporativa').click();
  check('logout_screen',(await page.locator('body').innerText()).slice(0,1000));
  await page.reload();
  await page.waitForTimeout(700);
  check('reload_after_logout',(await page.locator('body').innerText()).includes('Rodrigo Mendoza'));
  const storage = await page.evaluate(()=>({local:{...localStorage},session:{...sessionStorage}}));
  check('key_in_browser_storage',JSON.stringify(storage).includes(KEY));
  await context.close(); await browser.close(); save();
})().catch(e=>{records.errors.push(e.stack);save();console.error(e.message);process.exit(1);});
