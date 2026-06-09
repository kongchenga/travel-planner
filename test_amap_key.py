import sys, requests, json

key = sys.argv[1] if len(sys.argv) > 1 else input("输入高德 Web 服务 Key: ").strip()

print("=== 1. POI 搜索 ===")
r = requests.get("https://restapi.amap.com/v3/place/text", params={
    "key": key, "keywords": "北京酒店", "city": "北京",
    "output": "JSON", "offset": 3
})
d = r.json()
if d.get("status") == "1":
    for p in d.get("pois", [])[:2]:
        print(f"  OK: {p['name']} - {p.get('address','')}")
else:
    print(f"  FAIL: {d.get('info')}")

print("=== 2. 天气查询 ===")
r = requests.get("https://restapi.amap.com/v3/weather/weatherInfo", params={
    "key": key, "city": "110000", "output": "JSON"
})
d = r.json()
if d.get("status") == "1" and d.get("lives"):
    w = d["lives"][0]
    print(f"  OK: {w['city']} {w['weather']} {w['temperature']}C")
else:
    print(f"  FAIL: {d.get('info')}")

print("\n两个都 OK 说明 Key 有效，然后执行:")
print(f"  Add to .env: AMAP_KEY={key}")
print("  Restart server")
