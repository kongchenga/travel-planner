// === API: POI search, plan submission, SSE ===

var _poiAbortController = null;

function fetchPois(city) {
  // Cancel any in-flight POI request
  if (_poiAbortController) {
    _poiAbortController.abort();
  }
  _poiAbortController = new AbortController();
  var signal = _poiAbortController.signal;

  var types = ["110200", "100000", "050000"];
  var all = [], done = 0, errored = 0;
  var totalTypes = types.length;

  function fetchType(t, page) {
    fetch("/api/poi/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ keywords: city, city: city, types: t, offset: 25, page: page }),
      signal: signal,
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (signal.aborted) return;
      var items = (data.results || []).map(function(p) { return Object.assign({}, p, { poiType: t }); });
      all = all.concat(items);
      if (items.length >= 25 && page < 2) { fetchType(t, page + 1); return; }
      done++;
      if (done + errored >= totalTypes) renderPois(all, city);
    })
    .catch(function() {
      if (signal.aborted) return;
      errored++;
      if (done + errored >= totalTypes) renderPois(all, city);
    });
  }
  types.forEach(function(t){ fetchType(t, 1); });
}

function listenSSE(sid) {
  _sseClosed = false;
  var es = new EventSource("/api/plan/" + sid + "/stream");
  es.addEventListener("agent_start", function(e) { try { setA(JSON.parse(e.data).agent); } catch(_1) {} });
  es.addEventListener("agent_complete", function(e) {
    try {
      var d = JSON.parse(e.data);
      var agent = d.agent;
      var cont = (d.content || "").slice(0, 40);
      var labelMap = {
        destination: "目的地研究", flight: "航班搜索",
        hotel: "住宿推荐", dining: "美食推荐",
        route_planner: "路线规划",
      };
      setD(agent, (labelMap[agent] || agent) + (cont ? ": " + cont : ""));
    } catch(_2) {}
  });
  es.addEventListener("complete", function(e) {
    _sseClosed = true; es.close();
    var tp = null;
    try {
      var d = JSON.parse(e.data);
      tp = d.trip_plan || {};
      savedTripPlan = tp;
      try { renderPlan(tp); } catch(err1) { console.error("plan render error", err1); }
      setMode("result");
    } catch(err0) { console.error("complete parse error", err0); }
    try {
      // Store ALL route map_data for switching
      window._routeMapData = (tp && tp.routes || []).map(function(r) { return r.map_data || {}; });
      var md = window._routeMapData.length > 0 ? window._routeMapData[0] : null;
      if (md && md.markers && md.markers.length) {
        setTimeout(function() { try { renderRoutes(md, 0); } catch(err2) { console.error("map render error", err2); } }, 300);
      }
    } catch(err3) { console.error("map data error", err3); }
    goBtn.disabled = false; goBtn.classList.remove("loading");
  });
  es.addEventListener("error", function(e) { _sseClosed = true; es.close(); try { showErr(JSON.parse(e.data).message || "出错了"); } catch(_3) {} });
  es.onerror = function() { if (!_sseClosed) { _sseClosed = true; es.close(); showErr("连接断开"); } };
}
