const {chromium}=require('C:/Users/willi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('node:fs');const path=require('node:path');
const OUT=__dirname;const KEY=process.env.AUDIT_DEEPSEEK_KEY;
const results={checks:[],pages:{},errors:[]};
function save(){fs.writeFileSync(path.join(OUT,'browser-recheck.json'),JSON.stringify(results,null,2));}
function check(name,value){results.checks.push({name,value});save();console.log(name+': '+JSON.stringify(value));}
(async()=>{
const browser=await chromium.launch({headless:true,channel:'msedge'});
try{
const ctx=await browser.newContext({viewport:{width:1440,height:1000}});const page=await ctx.newPage();
page.on('pageerror',e=>{results.errors.push(e.message);save();});
await page.route('**/api/**',route=>{const u=new URL(route.request().url());return route.continue({url:'http://127.0.0.1:8011'+u.pathname+u.search});});
await page.route('**/healthz',route=>route.continue({url:'http://127.0.0.1:8011/healthz'}));
await page.goto('http://127.0.0.1:3000');
await page.getByText('audit-ui-check',{exact:true}).first().click();
await page.getByTitle('Configuración de Motor LLM (Principio VI: Memoria Efímera)').click();
await page.locator('select').last().selectOption('deepseek');await page.locator('input[type=password]').fill(KEY);
const v=page.waitForResponse(r=>r.url().includes('/llm/verify'),{timeout:120000});
await page.getByRole('button',{name:'Guardar y Probar Conexión'}).click();check('real_deepseek_verify',(await(await v).json()).status);
await page.getByText(/CONECTADO \(/).waitFor();
await page.getByRole('button',{name:/DeepSeek V4 Pro/}).click();
check('old_verification_visible_after_model_change',await page.getByText(/CONECTADO \(/).isVisible());
await page.getByRole('button',{name:/DeepSeek Flash/}).click();await page.getByRole('button',{name:'Cerrar',exact:true}).click();
for(const name of ['Resumen','1. Requisitos','2. Arquitectura','3. Modelos & SQL','4. Código & Fix','5. Calidad SAST','6. DevOps & Demo','7. Entrega Git','Monitor Live','Blueprints']){
await page.getByRole('button',{name:name==='Monitor Live'?/^Monitor Live/:name,exact:name!=='Monitor Live'}).click();await page.waitForTimeout(500);
results.pages[name]=(await page.locator('body').innerText()).slice(0,16000);save();
}
await page.getByRole('button',{name:'1. Requisitos',exact:true}).click();await page.waitForTimeout(600);
check('library_entities_visible', (await page.locator('body').innerText()).includes('Book'));
await page.getByRole('button',{name:'Aprobar y Diseñar Arquitectura →'}).click();
await page.getByRole('button',{name:/Generar \/ Regenerar con IA/}).waitFor();
await page.getByText('audit-empty-second',{exact:true}).first().click();await page.waitForTimeout(1000);
const architectureRequests=[];page.on('request',r=>{if(r.url().includes('/architecture/design'))architectureRequests.push(r.postData());});
await page.getByRole('button',{name:/Generar \/ Regenerar con IA/}).first().click();await page.waitForTimeout(1000);
check('cross_session_architecture_request_count',architectureRequests.length);
check('empty_session_screen',(await page.locator('body').innerText()).slice(-10000));
await page.screenshot({path:path.join(OUT,'ui-empty-after-switch.png'),fullPage:true});
await page.getByTitle('Cerrar sesión corporativa').click();await page.reload();await page.waitForTimeout(700);
check('demo_user_after_logout_reload',(await page.locator('body').innerText()).includes('Rodrigo Mendoza'));
await page.screenshot({path:path.join(OUT,'ui-logout-reload.png'),fullPage:true});
check('credential_in_storage',await page.evaluate(k=>JSON.stringify({...localStorage,...sessionStorage}).includes(k),KEY));
await ctx.close();
}finally{await browser.close();save();}
})().catch(e=>{results.errors.push(e.message);save();console.error(e.message);process.exitCode=1;});
