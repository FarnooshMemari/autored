import httpx, json, sys
B="http://127.0.0.1:3000"
def pj(label,r): print(label, r.status_code, (r.text[:160] if r.status_code>=300 else "ok"))
# 1) admin (first signup becomes admin)
r=httpx.post(f"{B}/api/v1/auths/signup", json={"name":"Admin","email":"admin@acme.test","password":"AdminPass123!"}, timeout=30)
if r.status_code>=300: print("signup admin (maybe exists):", r.status_code, r.text[:120]); 
tok=None
if r.status_code<300: tok=r.json()["token"]
else:
    r2=httpx.post(f"{B}/api/v1/auths/signin", json={"email":"admin@acme.test","password":"AdminPass123!"}, timeout=30)
    tok=r2.json().get("token"); print("signin admin:", r2.status_code)
H={"Authorization":f"Bearer {tok}"}
# 2) per-agent accounts (admins => bypass model/tool access control; audit attributes by email)
for e in ["injection","leakage","hierarchy","tools"]:
    r=httpx.post(f"{B}/api/v1/auths/add", headers=H, json={"name":e,"email":f"{e}@acme.test","password":"TestPass123!","role":"admin"}, timeout=30)
    pj(f"add {e}", r)
# 3) register the audited tool
content=open("support_tools_content.py").read()
r=httpx.post(f"{B}/api/v1/tools/create", headers=H, json={"id":"support_tools","name":"Acme Support Tools","content":content,"meta":{"description":"synthetic support tools with audit log"}}, timeout=60)
pj("tool create", r)
# 4) model overlay attaching the tool by default
r=httpx.post(f"{B}/api/v1/models/create", headers=H, json={"id":"acme-tools:latest","name":"AcmeHelp","base_model_id":None,"meta":{"description":"Acme support assistant","toolIds":["support_tools"]},"params":{},"is_active":True}, timeout=30)
pj("model overlay", r)
print("ADMIN_TOKEN", tok)
