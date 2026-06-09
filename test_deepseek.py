import requests, json, os
from dotenv import load_dotenv; load_dotenv()
key = os.getenv("OPENAI_API_KEY")
r = requests.post("https://api.deepseek.com/chat/completions", json={
    "model": "deepseek-chat",
    "messages": [{"role":"user","content":"Say hi in JSON: {\"greeting\":\"...\"}"}],
}, headers={"Authorization": f"Bearer {key}"}, timeout=15)
print(r.status_code)
if r.status_code == 200:
    print(r.json()["choices"][0]["message"]["content"])
else:
    print(r.text[:300])
