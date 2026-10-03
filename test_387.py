import urllib.request
import json
import urllib.error
import sys

BASE_URL = 'http://127.0.0.1:8000'

def request(method, path, data=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if data is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(data).encode('utf-8')
    if token:
        headers['Authorization'] = f"Bearer {token}"
    
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            body = res.read()
            if not body: return None
            return json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read()
        print(f"HTTPError {e.code} on {method} {path}: {body.decode('utf-8')}")
        raise

print("--- 3.8.7 Save / Update Workflow Test Suite ---")

# Setup auth
try:
    request('POST', '/auth/register', {
        'email': 'demo@smeconnect.io',
        'password': 'DemoPassword123!',
        'name': 'Test User',
        'organization_name': 'Test Org'
    })
except urllib.error.HTTPError as e:
    pass # probably already exists

token_res = request('POST', '/auth/login', {
    'email': 'demo@smeconnect.io',
    'password': 'DemoPassword123!'
})
token = token_res['access_token']
print("1. Auth initialized.")

# Get capabilities
caps = request('GET', '/workflows/capabilities', token=token)

# Step 1: Create a new workflow (POST /workflows)
draft_def = {
    "trigger": {
        "connector": "google_sheets",
        "event": "new_row",
        "config": {}
    },
    "steps": [
        {
            "id": "step-1",
            "type": "action",
            "connector": "crm",
            "action": "create_lead",
            "config": {},
            "mapping": {
                "name": "trigger.values.Name",
                "email": "trigger.values.Email",
                "phone": "trigger.values.Phone"
            }
        }
    ]
}

print("\nStep 1 & 2: Create and Verify Draft")
wf = request('POST', '/workflows', {
    "name": "3.8.7 Test Workflow",
    "description": "Testing save behavior",
    "definition": draft_def
}, token=token)

wf_id = wf['id']
print(f"Created workflow ID: {wf_id}")
assert wf['status'] == 'draft'
assert wf['version_number'] == 1
assert wf['definition']['steps'][0]['mapping']['phone'] == 'trigger.values.Phone'

print("\nStep 3: Edit existing draft (PUT)")
draft_def['steps'][0]['mapping']['phone'] = 'trigger.values.Mobile'
wf_updated = request('PUT', f'/workflows/{wf_id}', {
    "definition": draft_def
}, token=token)
assert wf_updated['id'] == wf_id
assert wf_updated['status'] == 'draft'
assert wf_updated['version_number'] == 1
assert wf_updated['definition']['steps'][0]['mapping']['phone'] == 'trigger.values.Mobile'
print("Draft updated successfully. Version remained 1.")

print("\nStep 4: GET workflow")
wf_fetched = request('GET', f'/workflows/{wf_id}', token=token)
assert wf_fetched['definition']['steps'][0]['mapping']['phone'] == 'trigger.values.Mobile'
print("Fetched successfully. Definition verified.")

print("\nStep 5: Add another action")
draft_def['steps'].append({
    "id": "step-2",
    "type": "action",
    "connector": "stripe",
    "action": "create_customer",
    "config": {},
    "mapping": {}
})
wf_updated2 = request('PUT', f'/workflows/{wf_id}', {
    "definition": draft_def
}, token=token)
assert len(wf_updated2['definition']['steps']) == 2
print("Second action added.")

print("\nStep 6: Test publish")
# Mock connections so publish passes
request('POST', '/connectors', {
    "connector_slug": "google_sheets",
    "name": "Sheets",
    "auth_data": {"token": "x"}
}, token=token)
request('POST', '/connectors', {
    "connector_slug": "crm",
    "name": "CRM",
    "auth_data": {"token": "x"}
}, token=token)
request('POST', '/connectors', {
    "connector_slug": "stripe",
    "name": "Stripe",
    "auth_data": {"token": "x"}
}, token=token)

wf_published = request('POST', f'/workflows/{wf_id}/publish', token=token)
assert wf_published['status'] == 'published'
assert wf_published['version_number'] == 1
print("Published successfully. Status is published, version 1.")

print("\nStep 7: Edit published workflow")
draft_def['steps'][0]['mapping']['phone'] = 'trigger.values.Home'
wf_v2 = request('PUT', f'/workflows/{wf_id}', {
    "definition": draft_def
}, token=token)
assert wf_v2['status'] == 'draft'
assert wf_v2['version_number'] == 2
print("Editing published workflow created V2 draft automatically.")

print("\nStep 8: Verify V1 was not modified")
wf_v1 = request('GET', f'/workflows/{wf_id}?version=1', token=token)
assert wf_v1['version_number'] == 1
assert wf_v1['definition']['steps'][0]['mapping']['phone'] == 'trigger.values.Mobile'
wf_v2_fetch = request('GET', f'/workflows/{wf_id}?version=2', token=token)
assert wf_v2_fetch['version_number'] == 2
assert wf_v2_fetch['definition']['steps'][0]['mapping']['phone'] == 'trigger.values.Home'
print("V1 is intact. V2 contains new edits.")

print("\nStep 9: Publish V2")
wf_v2_pub = request('POST', f'/workflows/{wf_id}/publish', token=token)
assert wf_v2_pub['status'] == 'published'
assert wf_v2_pub['version_number'] == 2
# Verify active version logic works
wf_summary = request('GET', '/workflows', token=token)
target_wf = next(w for w in wf_summary if w['id'] == wf_id)
assert target_wf['version_number'] == 2
assert target_wf['status'] == 'published'
print("V2 published. V1 is now inactive, V2 is active.")

print("\nStep 10: Pause and Resume")
wf_paused = request('POST', f'/workflows/{wf_id}/pause', token=token)
assert wf_paused['status'] == 'paused'
assert wf_paused['version_number'] == 2
print("Workflow paused.")

wf_resumed = request('POST', f'/workflows/{wf_id}/publish', token=token)
assert wf_resumed['status'] == 'published'
assert wf_resumed['version_number'] == 2
print("Workflow resumed safely.")

print("\nÃƒÂ¢Ã…â€œÃ¢â‚¬Â¦ All 3.8.7 tests passed!")
