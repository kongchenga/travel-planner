// === API: POI search, plan submission, SSE ===

function fetchPois(city) {
  const types = ["110200", "100000", "050000"];
  let all = [], done = 0;
  function fetchType(t, page) {
    fetch("/api/poi/search", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ keywords: city, city: city, types: t, offset: 25, page: page }) })
    .then(r => r.json())
    .then(data => {
      const items = (data.results || []).map(p => Object.assign(p, { poiType: t }));
      all = all.concat(items);
      if (items.length >= 25 && page < 2) fetchType(t, page + 1);
      else { done++; if (done === types.length) renderPois(all, city); }
    })
    .catch(() => { done++; if (done === types.length) renderPois(all, city); });
  }
  types.forEach(t => fetchType(t, 1));
}

function listenSSE(sid) {
  _sseClosed = false;
  const es = new EventSource("/api/plan/" + sid + "/stream");
  es.addEventListener("agent_start", e => { try { setA(JSON.parse(e.data).agent); } catch(_) {} });
  es.addEventListener("agent_complete", e => { try { setD(JSON.parse(e.data).agent); } catch(_) {} });
  es.addEventListener("complete", e => {
    _sseClosed = true; es.close();
    let tp = null;
    try {
      const d = JSON.parse(e.data);
      tp = d.trip_plan || {};
      savedTripPlan = tp;
      renderPlan(tp);
      setMode("result");
    } catch(_) { console.error("plan error", _); }
    try {
      const md = tp && tp.map_data || savedTripPlan && savedTripPlan.map_data || null;
      if (md && md.markers && md.markers.length) setTimeout(() => renderRoutes(md), 200);
    } catch(_) { console.error("map error", _); }
    goBtn.disabled = false; goBtn.classList.remove("loading");
  });
  es.addEventListener("error", e => { _sseClosed = true; es.close(); try { showErr(JSON.parse(e.data).message || "出错了"); } catch(_) {} });
  es.onerror = function() { if (!_sseClosed) { _sseClosed = true; es.close(); showErr("连接断开"); } };
}
