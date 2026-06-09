// === Map: init, POI markers, selection, routes ===

function initMap() {
  const el = $("explore-map");
  if (!el || exploreMap) return;
  try {
    exploreMap = L.map(el, { zoomControl: true, attributionControl: false }).setView([35, 110], 4);
    L.tileLayer("https://webrd01.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8", { maxZoom: 18 }).addTo(exploreMap);
    setTimeout(() => exploreMap.invalidateSize(), 100);
  } catch(e) { setTimeout(initMap, 500); }
  window.addEventListener("resize", () => { if (exploreMap) setTimeout(() => exploreMap.invalidateSize(), 100); });
}

function renderPois(pois, city) {
  exploreMarkers.forEach(m => exploreMap.removeLayer(m));
  exploreMarkers = []; selectedPois = []; updateSelBar();
  if (!pois.length) { $("poi-info").textContent = "无结果"; return; }
  const first = pois[0];
  if (first && first.location) {
    const [lng, lat] = first.location.split(",").map(Number);
    exploreMap.setView([lat, lng], 13);
  }
  setTimeout(() => exploreMap.invalidateSize(), 200);
  $("poi-info").textContent = "找到 " + pois.length + " 个地点";
  goBtn.disabled = false;
  var iconMap = { "110200": "🏛️", "100000": "🏨", "050000": "🍽️" };
  var poiColors = { "110200": "#6366f1", "100000": "#10b981", "050000": "#ef4444" };
  pois.forEach(p => {
    if (!p.location) return;
    const [lng, lat] = p.location.split(",").map(Number);
    if (!lng || !lat) return;
    const color = poiColors[p.poiType] || "#6366f1";
    const ico = iconMap[p.poiType] || "📍";
    const marker = L.marker([lat, lng], {
      icon: L.divIcon({ html: '<div style="width:28px;height:28px;background:' + color + ';color:#fff;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,.3);border:2px solid rgba(255,255,255,.2);transition:all .15s">' + ico + '</div>', className: "", iconSize: [28,28], iconAnchor: [14,14] })
    }).addTo(exploreMap);
    marker._poiData = p; marker._selected = false;
    marker.on("click", function() {
      this._selected = !this._selected;
      const div = this.getElement() && this.getElement().querySelector("div");
      if (div) div.style.borderColor = this._selected ? "#fff" : "rgba(255,255,255,.2)";
      toggleSelect(p, this._selected);
    });
    exploreMarkers.push(marker);
  });
}

function toggleSelect(p, add) {
  if (add) {
    if (!selectedPois.find(sp => sp.name === p.name && sp.location === p.location))
      selectedPois.push({ id: p.id, name: p.name, location: p.location, address: p.address, type: p.poiType || "attraction" });
  } else {
    selectedPois = selectedPois.filter(sp => !(sp.name === p.name && sp.location === p.location));
  }
  updateSelBar();
}

function updateSelBar() {
  const bar = $("sel-bar"), tags = $("sel-tags"), c = $("sel-c");
  if (selectedPois.length) {
    bar.classList.remove("hidden");
    tags.innerHTML = selectedPois.map(p => '<span class="sel-tag" data-n="' + escAttr(p.name) + '">' + esc(p.name) + ' ✕</span>').join("");
    c.textContent = selectedPois.length;
    $("poi-info").textContent = "已选 " + selectedPois.length + " 个";
    tags.querySelectorAll(".sel-tag").forEach(t => {
      t.addEventListener("click", function() {
        const name = this.dataset.n;
        exploreMarkers.forEach(m => {
          if (m._poiData && m._poiData.name === name) { m._selected = false; const d = m.getElement() && m.getElement().querySelector("div"); if (d) d.style.borderColor = "rgba(255,255,255,.2)"; }
        });
        selectedPois = selectedPois.filter(p => p.name !== name);
        updateSelBar();
      });
    });
  } else {
    bar.classList.add("hidden");
    $("poi-info").textContent = exploreMarkers.length ? exploreMarkers.length + " 个地点" : "输入目的地";
  }
}

function renderRoutes(data) {
  if (!exploreMap || !data || !data.markers) return;
  exploreMarkers.forEach(function(m) { try{exploreMap.removeLayer(m);}catch(_){} });
  var bounds = [];
  var rIcon = { attraction: "🏛️", hotel: "🏨", restaurant: "🍽️" };
  var rCol = { attraction: "#6366f1", hotel: "#10b981", restaurant: "#ef4444" };
  for (var i = 0; i < data.markers.length; i++) {
    var m = data.markers[i]; var loc = m.location; if (!loc) continue;
    var ll = loc.split(","); var lat = parseFloat(ll[1]), lng = parseFloat(ll[0]);
    if (!lat || !lng) continue;
    bounds.push([lat, lng]);
    var col = rCol[m.type] || "#6366f1";
    var ico = rIcon[m.type] || "📍";
    var txt = m.day ? String(m.day) : ico;
    L.marker([lat, lng], {
      icon: L.divIcon({ html: '<div style="width:26px;height:26px;background:' + col + ';color:#fff;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:11px;box-shadow:0 2px 8px rgba(0,0,0,.3);border:2px solid rgba(255,255,255,.3)">' + txt + '</div>', className: "", iconSize: [26,26], iconAnchor: [13,13] })
    }).addTo(exploreMap).bindPopup("<b>" + esc(m.name) + "</b>" + (m.day ? " Day " + m.day : ""));
  }
  if (data.routes) {
    var ms = { driving: { color:"#00b894", dash:"8,4", icon:"🚗", label:"驾车" }, walking: { color:"#6c5ce7", dash:"4,4", icon:"🚶", label:"步行" } };
    for (var i = 0; i < data.routes.length; i++) {
      var r = data.routes[i]; if (!r.from_loc || !r.to_loc) continue;
      var f = r.from_loc.split(","), t = r.to_loc.split(",");
      var s = ms[r.mode] || ms.driving;
      L.polyline([[parseFloat(f[1]), parseFloat(f[0])], [parseFloat(t[1]), parseFloat(t[0])]], { color: s.color, weight: 3, opacity: .8, dashArray: s.dash })
        .addTo(exploreMap)
        .bindPopup("<b>" + esc(r.from) + " → " + esc(r.to) + "</b><br>" + s.icon + " " + s.label + ": " + r.distance_km + "km " + (r.duration_min || "?") + "分钟");
    }
  }
  if (bounds.length) exploreMap.fitBounds(bounds, { padding: [50,50] });
  setTimeout(() => exploreMap.invalidateSize(), 200);
}
