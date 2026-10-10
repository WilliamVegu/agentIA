import os
import sys
import glob
import json
import re
import sqlite3
import subprocess

# ==============================================================================
# 🔑 CONFIGURACIÓN: COLOCA AQUÍ TU API KEY DE TCS GENAI LAB
# ==============================================================================
GATEWAY_URL = os.getenv(
    "TCS_GATEWAY_URL",
    "https://genailab.tcs.in/v1/chat/completions",
).strip()
MODEL_ID = os.getenv("TCS_MODEL_ID", "genailab-maas-gpt-5.3-codex").strip()
# ==============================================================================

if not GATEWAY_URL or not MODEL_ID:
    print("\n❌ TCS_GATEWAY_URL and TCS_MODEL_ID must not be empty.\n")
    sys.exit(1)

# 1. Localizar extensión github.copilot-chat activa
candidate_patterns = [
    os.path.expandvars(r"%USERPROFILE%\.vscode\extensions\github.copilot-chat-*"),
    os.path.expanduser("~/.vscode/extensions/github.copilot-chat-*"),
    os.path.expanduser("~/.vscode-server/extensions/github.copilot-chat-*"),
]

ext_dirs = []
for pat in candidate_patterns:
    found = sorted(glob.glob(pat))
    if found:
        ext_dirs.extend(found)

if not ext_dirs:
    # Si no se encuentra en las carpetas de usuario, verificar la versión del sistema
    system_copilot = "/usr/share/code/resources/app/extensions/copilot"
    user_target = os.path.expanduser("~/.vscode/extensions/github.copilot-chat-0.69.0")
    if os.path.exists(system_copilot):
        print(f"ℹ Copiando extensión incorporada de {system_copilot} a {user_target}...")
        os.makedirs(os.path.dirname(user_target), exist_ok=True)
        import shutil
        shutil.copytree(system_copilot, user_target, dirs_exist_ok=True)
        ext_dirs = [user_target]

if not ext_dirs:
    print("❌ No se encontró la carpeta de la extensión github.copilot-chat.")
    print("Asegúrate de tener instalada la extensión en VS Code.")
    sys.exit(1)

target_ext_dir = ext_dirs[-1]
ext_file = os.path.join(target_ext_dir, "dist", "extension.js")
print(f"\n📂 Extensión localizada: {ext_file}")

# 2. Respaldo previo
backup_file = ext_file + ".bak"
if not os.path.exists(backup_file):
    with open(ext_file, "r", encoding="utf-8") as f_in, open(backup_file, "w", encoding="utf-8") as f_out:
        f_out.write(f_in.read())
    print("✓ Respaldo creado en extension.js.bak")

with open(ext_file, "r", encoding="utf-8") as f:
    text = f.read()

# 3. Parche BYOK (Habilitar modo BYOK incondicionalmente)
# Versión A (0.24+): function Nee(r,e){...}
t_nee = 'function Nee(r,e){let t=e.dotComAPIURL!=="https://api.github.com";return(r.isInternal||r.isIndividual)&&!t}'
r_nee = 'function Nee(r,e){return true}'
# Versión B (0.69+): function qwe(t,e){return t?e?e.isInternal||e.isIndividual||e.isClientBYOKEnabled():!1:!0}
t_qwe = re.search(r'function \w+\(t,e\)\{return t\?e\?e\.isInternal\|\|e\.isIndividual\|\|e\.isClientBYOKEnabled\(\):!1:!0\}', text)

if t_nee in text:
    text = text.replace(t_nee, r_nee, 1)
    print("✓ [1/5] Parche BYOK aplicado (función Nee)")
elif t_qwe:
    fn_name = t_qwe.group(0).split('(')[0]
    r_qwe = f'{fn_name}(t,e){{return true}}'
    text = text.replace(t_qwe.group(0), r_qwe, 1)
    print(f"✓ [1/5] Parche BYOK aplicado ({fn_name})")
else:
    print("ℹ [1/5] BYOK ya habilitado o firma no encontrada")

# 4. Parche Endpoint Azure / Custom URLs
t_uze = 'function UZe(r){let e=/^https:\\/\\/([^.]+)\\..*\\.models\\.ai\\.azure\\.com\\//,t=r.match(e);if(t&&t[1])return t[1];let n=/\\/openai\\/deployments\\/([^\\/]+)\\//,o=r.match(n);if(o&&o[1])return o[1]}'
r_uze = 'function UZe(r){let e=/^https:\\/\\/([^.]+)\\..*\\.models\\.ai\\.azure\\.com\\//,t=r.match(e);if(t&&t[1])return t[1];let n=/\\/openai\\/deployments\\/([^\\/]+)\\//,o=r.match(n);if(o&&o[1])return o[1];return "custom-model"}'
t_azure_err = re.search(r'throw new Error\([`"\']Unrecognized Azure deployment URL:[^`"\']*[`"\']\)', text)

if t_uze in text:
    text = text.replace(t_uze, r_uze, 1)
    print("✓ [2/5] Parche URL aplicado (función UZe)")
elif t_azure_err:
    r_azure = 'return e'
    text = text.replace(t_azure_err.group(0), r_azure, 1)
    print("✓ [2/5] Parche URL aplicado (permite URLs de TCS GenAI Lab)")
else:
    print("ℹ [2/5] Validación de URL ya parchada o no requerida")

# 5. Parche is_chat_default (Activar selector de modelos)
t_kee = 'function kee(r){let e=r.capabilities.limits?.max_output_tokens??4096,t=r.capabilities.limits?.max_prompt_tokens??(r.capabilities.limits?.max_context_window_tokens||64e3)-e;return{family:r.capabilities.family,vendor:"copilot-byok",version:"1.0.0",maxOutputTokens:e,maxInputTokens:t,name:r.name,isUserSelectable:!0,capabilities:{agentMode:r.capabilities.supports.tool_calls,toolCalling:r.capabilities.supports.tool_calls,vision:r.capabilities.supports.vision}}}'
r_kee = 'function kee(r){let e=r.capabilities.limits?.max_output_tokens??4096,t=r.capabilities.limits?.max_prompt_tokens??(r.capabilities.limits?.max_context_window_tokens||64e3)-e;return{family:r.capabilities.family,vendor:"copilot-byok",version:"1.0.0",maxOutputTokens:e,maxInputTokens:t,name:r.name,isDefault:!!r.is_chat_default,isUserSelectable:!0,capabilities:{agentMode:r.capabilities.supports.tool_calls,toolCalling:r.capabilities.supports.tool_calls,vision:r.capabilities.supports.vision}}}'
if t_kee in text:
    text = text.replace(t_kee, r_kee, 1)
    print("✓ [3/5a] Parche kee aplicado")

t_dee = 'is_chat_default:!1,is_chat_fallback:!1,model_picker_enabled:!0}}function Nee('
r_dee = 'is_chat_default:!!(o?.isDefault||r.includes("5.3")),is_chat_fallback:!1,model_picker_enabled:!0}}function Nee('
if t_dee in text:
    text = text.replace(t_dee, r_dee, 1)
    print("✓ [3/5b] Parche Dee aplicado")

# Versión 0.69+
t_def_069 = 'is_chat_default:!1,is_chat_fallback:!1,model_picker_enabled:!0'
r_def_069 = 'is_chat_default:!0,is_chat_fallback:!1,model_picker_enabled:!0'
if t_def_069 in text:
    text = text.replace(t_def_069, r_def_069, 1)
    print("✓ [3/5] Parche is_chat_default activado para modelos BYOK")

# 6. Parche Almacenamiento de Modelos y API Key
t_yne = re.search(r'var (\w+)=class\{constructor\(e\)\{this\._extensionContext=e\}async getAPIKey\(e,t\)\{.*?\}\}\;', text)
t_mje = re.search(r'var (\w+)=class\{constructor\(e\)\{this\._extensionContext=e\}async getAPIKey\(e,n\)\{.*?\}\}\;', text)

match_storage = t_yne or t_mje
if match_storage:
    class_name = match_storage.group(1)
    r_storage = f'''var _TCS_DEFAULTS={{
"genailab-maas-gpt-5.3-codex":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-5.3 Codex",maxInputTokens:128e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!0}}}},
"genailab-maas-gpt-4o":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-4o",maxInputTokens:128e3,maxOutputTokens:4096,toolCalling:!0,vision:!0,isDefault:!1}}}},
"genailab-maas-gpt-5.4":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-5.4",maxInputTokens:128e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!1}}}},
"genailab-maas-gpt-5.2-codex":{{isCustomModel:!0,deploymentUrl:"{GATEWAY_URL}",isRegistered:!0,modelCapabilities:{{name:"TCS: GPT-5.2 Codex",maxInputTokens:128e3,maxOutputTokens:8192,toolCalling:!0,vision:!0,isDefault:!1}}}}
}};
var {class_name}=class{{constructor(e){{this._extensionContext=e}}async getAPIKey(e,n){{if(n){{let o=await this._extensionContext.secrets.get(`copilot-byok-${{e}}-${{n}}-api-key`);if(o&&o.trim())return o.trim()}}let k=await this._extensionContext.secrets.get(`copilot-byok-${{e}}-api-key`);if(k&&k.trim())return k.trim();return void 0}}async storeAPIKey(e,n,r,o){{r!==2&&(r===0?await this._extensionContext.secrets.store(`copilot-byok-${{e}}-api-key`,n):r===1&&o&&await this._extensionContext.secrets.store(`copilot-byok-${{e}}-${{o}}-api-key`,n))}}async deleteAPIKey(e,n,r){{n!==2&&(n===0?await this._extensionContext.secrets.delete(`copilot-byok-${{e}}-api-key`):n===1&&r&&await this._extensionContext.secrets.delete(`copilot-byok-${{e}}-${{r}}-api-key`))}}async getStoredModelConfigs(e){{let g=this._extensionContext.globalState.get(`copilot-byok-${{e}}-models-config`,{{}});if(e==="Azure")return{{..._TCS_DEFAULTS,...g}};return g}}async saveModelConfig(e,n,r,o){{let a={{isCustomModel:r.isCustomModel,deploymentUrl:r.deploymentUrl,isRegistered:!0,modelCapabilities:r.modelCapabilities}},s=await this.getStoredModelConfigs(n);s[e]=a,await this._extensionContext.globalState.update(`copilot-byok-${{n}}-models-config`,s),await this.storeAPIKey(n,r.apiKey,o,e)}}async removeModelConfig(e,n,r){{let o=await this.getStoredModelConfigs(n),a=o[e],s=a?.isCustomModel||!1;a&&(r||!s)?(delete o[e],await this._extensionContext.globalState.update(`copilot-byok-${{n}}-models-config`,o),await this._extensionContext.secrets.delete(`copilot-byok-${{n}}-${{e}}-api-key`)):(s.isRegistered=!1,await this._extensionContext.globalState.update(`copilot-byok-${{n}}-models-config`,o))}}}};\n'''
    text = text.replace(match_storage.group(0), r_storage, 1)
    print(f"✓ [4/5] Parche de almacenamiento aplicado ({class_name})")
else:
    print("ℹ [4/5] Clase de almacenamiento ya actualizada o no encontrada")

# 7. Parche interceptBody (Eliminar top_p, n y temperature)
t_body_old = 'interceptBody(t){super.interceptBody(t),t?.tools?.length===0&&delete t.tools,t&&(t.stream_options={include_usage:!0})}'
r_body_old = 'interceptBody(t){super.interceptBody(t),t?.tools?.length===0&&delete t.tools,t&&(t.stream_options={include_usage:!0},delete t.top_p,delete t.n,(t.model?.includes("gpt-5")||t.model?.startsWith("o"))&&delete t.temperature)}'

t_body_new = 'interceptBody(n){super.interceptBody(n),n?.tools?.length===0&&delete n.tools,'
r_body_new = 'interceptBody(n){super.interceptBody(n),n?.tools?.length===0&&delete n.tools,n&&(delete n.top_p,delete n.n,(n.model?.includes("gpt-5")||n.model?.startsWith("o"))&&delete n.temperature),'

if t_body_old in text:
    text = text.replace(t_body_old, r_body_old, 1)
    print("✓ [5/5] Parche interceptBody aplicado (v1)")
elif t_body_new in text:
    text = text.replace(t_body_new, r_body_new, 1)
    print("✓ [5/5] Parche interceptBody aplicado (v2)")

# Parche forzar visualización en Model Picker
t_picker_override = re.search(r'_getShowInModelPickerOverride\(n\)\{.*?\}\}\;', text)
if t_picker_override:
    text = text.replace(t_picker_override.group(0), '_getShowInModelPickerOverride(n){return true}};', 1)
    print("✓ [6/6] Parche _getShowInModelPickerOverride aplicado (fuerza visualización de modelos)")

with open(ext_file, "w", encoding="utf-8") as f:
    f.write(text)

# Validar sintaxis con node si está disponible
try:
    res = subprocess.run(["node", "--check", ext_file], capture_output=True, text=True)
    if res.returncode == 0:
        print("✓ Sintaxis de JavaScript verificada exitosamente.")
    else:
        print("✗ Aviso de sintaxis en extension.js:", res.stderr)
except FileNotFoundError:
    pass

# 8. Actualizar chatLanguageModels.json (Configuración nativa de modelos para VS Code moderno)
lm_candidates = [
    os.path.expandvars(r"%APPDATA%\Code\User\chatLanguageModels.json"),
    os.path.expanduser("~/.config/Code/User/chatLanguageModels.json"),
]

lm_config = [{
    "name": "TCS GenAI Lab",
    "vendor": "customendpoint",
    "apiKey": "${input:tcsGatewayApiKey}",
    "apiType": "chat",
    "models": [{
        "id": MODEL_ID,
        "name": f"TCS: {MODEL_ID}",
        "url": GATEWAY_URL,
        "toolCalling": True,
        "vision": True,
        "maxInputTokens": 128000,
        "maxOutputTokens": 8192
    }]
}]

for lm_path in lm_candidates:
    try:
        os.makedirs(os.path.dirname(lm_path), exist_ok=True)
        with open(lm_path, "w", encoding="utf-8") as f:
            json.dump(lm_config, f, indent=2)
        print(f"✓ {os.path.basename(lm_path)} actualizado con modelos TCS GenAI Lab.")
    except Exception as e:
        print(f"⚠ Aviso al actualizar {lm_path}: {e}")

# 9. Actualizar settings.json (http.proxyStrictSSL y soporte BYOK)
settings_candidates = [
    os.path.expandvars(r"%APPDATA%\Code\User\settings.json"),
    os.path.expanduser("~/.config/Code/User/settings.json"),
]

for s_path in settings_candidates:
    if os.path.exists(s_path):
        try:
            with open(s_path, "r", encoding="utf-8") as f:
                s_data = json.load(f)
            s_data["http.proxyStrictSSL"] = False
            s_data["chat.agentHost.byokModels.enabled"] = True
            with open(s_path, "w", encoding="utf-8") as f:
                json.dump(s_data, f, indent=4)
            print(f"✓ {os.path.basename(s_path)} actualizado (http.proxyStrictSSL=False).")
        except Exception as e:
            print(f"⚠ Aviso al actualizar settings.json: {e}")

# 10. Actualizar base de datos de VS Code (state.vscdb para compatibilidad previa)
db_candidates = [
    os.path.expandvars(r"%APPDATA%\Code\User\globalStorage\state.vscdb"),
    os.path.expanduser("~/.config/Code/User/globalStorage/state.vscdb"),
]

for db_path in db_candidates:
    if os.path.exists(db_path):
        try:
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute("SELECT value FROM ItemTable WHERE key = 'GitHub.copilot-chat'")
            row = cur.fetchone()
            state = json.loads(row[0]) if row else {}
            state["copilot-byok-Azure-models-config"] = {
                "genailab-maas-gpt-5.3-codex": {
                    "isCustomModel": True,
                    "deploymentUrl": GATEWAY_URL,
                    "isRegistered": True,
                    "modelCapabilities": {
                        "name": "TCS: GPT-5.3 Codex",
                        "maxInputTokens": 128000,
                        "maxOutputTokens": 8192,
                        "toolCalling": True,
                        "vision": True,
                        "isDefault": True
                    }
                },
                "genailab-maas-gpt-4o": {
                    "isCustomModel": True,
                    "deploymentUrl": GATEWAY_URL,
                    "isRegistered": True,
                    "modelCapabilities": {
                        "name": "TCS: GPT-4o",
                        "maxInputTokens": 128000,
                        "maxOutputTokens": 4096,
                        "toolCalling": True,
                        "vision": True,
                        "isDefault": False
                    }
                },
                "genailab-maas-gpt-5.4": {
                    "isCustomModel": True,
                    "deploymentUrl": GATEWAY_URL,
                    "isRegistered": True,
                    "modelCapabilities": {
                        "name": "TCS: GPT-5.4",
                        "maxInputTokens": 128000,
                        "maxOutputTokens": 8192,
                        "toolCalling": True,
                        "vision": True,
                        "isDefault": False
                    }
                },
                "genailab-maas-gpt-5.2-codex": {
                    "isCustomModel": True,
                    "deploymentUrl": GATEWAY_URL,
                    "isRegistered": True,
                    "modelCapabilities": {
                        "name": "TCS: GPT-5.2 Codex",
                        "maxInputTokens": 128000,
                        "maxOutputTokens": 8192,
                        "toolCalling": True,
                        "vision": True,
                        "isDefault": False
                    }
                }
            }
            cur.execute("INSERT OR REPLACE INTO ItemTable (key, value) VALUES ('GitHub.copilot-chat', ?)", (json.dumps(state),))
            conn.commit()
            conn.close()
            print(f"✓ Base de datos {os.path.basename(db_path)} actualizada correctamente.")
        except Exception as e:
            print(f"⚠ Aviso al actualizar state.vscdb: {e}")

print("\n🎉 ¡Parchado de GitHub Copilot Chat completado con éxito!")
print("👉 Ahora abre VS Code y presiona Ctrl + Shift + P -> 'Developer: Reload Window'.\n")
