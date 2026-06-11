// === Map: init, POI markers, selection, routes ===

var _initMapRetries = 0;
var _MAX_INIT_MAP_RETRIES = 5;

function initMap() {
  var el = $("explore-map");
  if (!el || exploreMap) return;
  try {
    exploreMap = L.map(el, { zoomControl: true, attributionControl: false }).setView([35, 110], 4);
    L.tileLayer("https://webrd01.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8", { maxZoom: 18 }).addTo(exploreMap);
    setTimeout(function(){ exploreMap.invalidateSize(); }, 100);
    _initMapRetries = 0;
  } catch(e) {
    _initMapRetries++;
    if (_initMapRetries <= _MAX_INIT_MAP_RETRIES) {
      setTimeout(initMap, _initMapRetries * 500);
    } else {
      console.error("Map init failed after " + _MAX_INIT_MAP_RETRIES + " retries:", e);
    }
  }
  window.addEventListener("resize", function(){ if (exploreMap) setTimeout(function(){ exploreMap.invalidateSize(); }, 100); });
}

function renderPois(pois, city) {
  exploreMarkers.forEach(function(m){ try { exploreMap.removeLayer(m); } catch(e) {} });
  exploreMarkers = []; selectedPois = []; updateSelBar();
  if (!pois.length) { $("poi-info").textContent = "无结果"; goBtn.disabled = false; return; }
  var first = pois[0];
  if (first && first.location) {
    var ll = first.location.split(",");
    exploreMap.setView([parseFloat(ll[1]), parseFloat(ll[0])], 13);
  }
  setTimeout(function(){ exploreMap.invalidateSize(); }, 200);
  $("poi-info").textContent = "找到 " + pois.length + " 个地点";
  goBtn.disabled = false;
  var iconMap = { "110200": "🏛️", "100000": "🏨", "050000": "🍽️" };
  var poiColors = { "110200": "#6366f1", "100000": "#10b981", "050000": "#ef4444" };
  pois.forEach(function(p) {
    if (!p.location) return;
    var ll = p.location.split(","), lng = parseFloat(ll[0]), lat = parseFloat(ll[1]);
    if (!lng || !lat) return;
    var color = poiColors[p.poiType] || "#6366f1";
    var ico = iconMap[p.poiType] || "📍";
    var labelText = (p.name || "").length > 8 ? p.name.slice(0,8)+".." : p.name;
    var iconHtml =
      '<div style="position:relative">' +
      '<div class="leaflet-marker-label">' + esc(labelText) + '</div>' +
      '<div style="width:28px;height:28px;background:' + color + ';color:#fff;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,.3);border:2px solid rgba(255,255,255,.2);transition:all .15s">' + ico + '</div>' +
      '</div>';
    var marker = L.marker([lat, lng], {
      icon: L.divIcon({ html: iconHtml, className: "", iconSize: [60,44], iconAnchor: [30,14] })
    }).addTo(exploreMap);
    marker._poiData = p; marker._selected = false;
    marker.on("click", function() {
      this._selected = !this._selected;
      toggleSelect(p, this._selected);
    });
    exploreMarkers.push(marker);
  });
}

function toggleSelect(p, add) {
  if (add) {
    if (!selectedPois.find(function(sp) { return sp.name === p.name && sp.location === p.location; }))
      selectedPois.push({ id: p.id, name: p.name, location: p.location, address: p.address, type: p.poiType || "attraction" });
  } else {
    selectedPois = selectedPois.filter(function(sp) { return !(sp.name === p.name && sp.location === p.location); });
  }
  updateSelBar();
}

function updateSelBar() {
  var bar = $("sel-bar"), tags = $("sel-tags"), c = $("sel-c");
  if (selectedPois.length) {
    bar.classList.remove("hidden");
    tags.innerHTML = selectedPois.map(function(p) { return '<span class="sel-tag" data-n="' + escAttr(p.name) + '">' + esc(p.name) + '</span>'; }).join("");
    c.textContent = selectedPois.length;
    $("poi-info").textContent = "已选 " + selectedPois.length + " 个";
    tags.querySelectorAll(".sel-tag").forEach(function(t) {
      t.addEventListener("click", function() {
        var name = this.dataset.n;
        exploreMarkers.forEach(function(m) {
          if (m._poiData && m._poiData.name === name) { m._selected = false; }
        });
        selectedPois = selectedPois.filter(function(p) { return p.name !== name; });
        updateSelBar();
      });
    });
  } else {
    bar.classList.add("hidden");
    $("poi-info").textContent = exploreMarkers.length ? exploreMarkers.length + " 个地点" : "输入目的地";
  }
}

// Track route layers for cleanup
var _routeMarkers = [];
var _routeLines = [];
var _activeRouteIdx = 0;
var _routeColorPalette = ["#059669", "#F59E0B", "#3B82F6", "#EF4444"];

function renderRoutes(data, routeIdx) {
  if (!exploreMap || !data || !data.markers) return;

  // Cleanup previous
  _routeMarkers.forEach(function(m) { try { exploreMap.removeLayer(m); } catch(_) {} });
  _routeMarkers = [];
  _routeLines.forEach(function(l) { try { exploreMap.removeLayer(l); } catch(_) {} });
  _routeLines = [];

  _activeRouteIdx = (typeof routeIdx !== 'undefined') ? routeIdx : 0;
  var routeColor = _routeColorPalette[_activeRouteIdx % _routeColorPalette.length];

  var bounds = [];
  var rIcon = {
    attraction: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" width="12" height="12"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18"/><path d="M9 21V9"/></svg>',
    hotel: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" width="12" height="12"><path d="M3 21h18"/><path d="M3 7v14"/><path d="M21 7v14"/><rect x="7" y="3" width="10" height="4" rx="1"/></svg>',
    restaurant: '<svg viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.5" width="12" height="12"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/></svg>'
  };
  var rCol = { attraction: "#059669", hotel: "#F59E0B", restaurant: "#3B82F6" };

  for (var i = 0; i < data.markers.length; i++) {
    var m = data.markers[i]; var loc = m.location; if (!loc) continue;
    var ll = loc.split(","); var lat = parseFloat(ll[1]), lng = parseFloat(ll[0]);
    if (!lat || !lng) continue;
    bounds.push([lat, lng]);
    var col = rCol[m.type] || "#059669";
    var ico = rIcon[m.type] || rIcon.attraction;
    var dayBadge = m.day ? '<span style="position:absolute;top:-6px;right:-6px;width:16px;height:16px;border-radius:50%;background:'+routeColor+';color:#fff;font-size:9px;font-weight:700;display:flex;align-items:center;justify-content:center;box-shadow:0 1px 3px rgba(0,0,0,.2)">'+m.day+'</span>' : '';
    var nameLabel = (m.name || "").length > 10 ? m.name.slice(0,10)+".." : (m.name || "");
    var mHtml = '<div style="position:relative">' +
      '<div class="leaflet-marker-label">' + esc(nameLabel) + '</div>' +
      '<div style="width:30px;height:30px;background:' + col + ';color:#fff;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px;box-shadow:0 2px 8px rgba(0,0,0,.2);border:2px solid rgba(255,255,255,.25);opacity:1">' + ico + '</div>' +
      dayBadge + '</div>';
    var mk = L.marker([lat, lng], {
      icon: L.divIcon({ html: mHtml, className: "", iconSize: [60,46], iconAnchor: [30,23] })
    }).addTo(exploreMap).bindPopup("<b>" + esc(m.name) + "</b>" + (m.day ? " Day " + m.day : ""));
    _routeMarkers.push(mk);
  }

  // Draw route lines — animate segment by segment
  if (data.routes) {
    var segDelay = 0;
    // Find the polyline segment (last one is the full route)
    var fullPoly = null;
    for (var i = data.routes.length - 1; i >= 0; i--) {
      if (data.routes[i].polyline && data.routes[i].polyline.length >= 2) {
        fullPoly = data.routes[i];
        break;
      }
    }
    // Animate the full route, then draw segment dots
    if (fullPoly) {
      _animateRouteSegment(fullPoly.polyline, routeColor, fullPoly);
    }
    // Draw segment distances as dots/lines
    for (var i = 0; i < data.routes.length; i++) {
      var r = data.routes[i];
      if (!r.from_loc || !r.to_loc) continue;
      if (r.polyline && r.polyline.length >= 2) continue; // already animated
      var f = r.from_loc.split(","), t = r.to_loc.split(",");
      var segColor = r.mode === "walking" ? "#34D399" : routeColor;
      var line = L.polyline([[parseFloat(f[1]), parseFloat(f[0])], [parseFloat(t[1]), parseFloat(t[0])]], {
        color: segColor, weight: r.mode === "walking" ? 2 : 3, opacity: 0.5,
        dashArray: r.mode === "walking" ? "4,4" : ""
      }).addTo(exploreMap);
      line.bindPopup("<b>" + esc(r.from) + " -> " + esc(r.to) + "</b><br>" + esc(r.mode||"driving") + ": " + r.distance_km + "km");
      _routeLines.push(line);
    }
  }

  if (bounds.length) exploreMap.fitBounds(bounds, { padding: [50,50] });
  setTimeout(function(){ exploreMap.invalidateSize(); }, 200);
}

// Animate a single route segment growing from start to end
function _animateRouteSegment(polyline, color, routeData) {
  var total = polyline.length;
  if (total < 2) return;
  var step = Math.max(Math.ceil(total / 80), 1); // ~80 frames = slower
  var idx = 0;
  var line = L.polyline([], { color: color, weight: 5, opacity: 0.85 }).addTo(exploreMap);
  line.bindPopup("<b>" + esc(routeData.from) + " -> " + esc(routeData.to) + "</b><br>" + esc(routeData.mode||"driving") + ": " + esc(routeData.distance_km || 0) + "km " + (routeData.duration_min || "?") + "min");
  _routeLines.push(line);

  function tick() {
    idx += step;
    if (idx >= total) {
      line.setLatLngs(polyline);
      return;
    }
    line.setLatLngs(polyline.slice(0, idx));
    setTimeout(tick, 30); // 30ms per frame = ~2.4s per segment
  }
  tick();
}

// Switch route view on map when user clicks a route card
function switchRouteMap(routeIdx) {
  var routes = window._routeMapData;
  if (!routes || routeIdx >= routes.length) return;
  var md = routes[routeIdx];
  if (!md || !md.markers || !md.markers.length) return;
  renderRoutes(md, routeIdx);
  // Dim explore markers that are not on this route
  dimMarkers(routeIdx);
}

// Dim markers from other routes, highlight current route markers
function dimMarkers(activeIdx) {
  var routes = window._routeMapData;
  exploreMarkers.forEach(function(m) {
    var el = m.getElement();
    if (!el) return;
    var d0 = el.querySelector("div > div");
    var d1 = el.querySelector("div > div > div");
    if (!d0) return;
    // Check if this marker is on the active route
    var onActive = false;
    if (routes && routes[activeIdx] && routes[activeIdx].markers) {
      onActive = routes[activeIdx].markers.some(function(rm) {
        return m._poiData && m._poiData.name === rm.name;
      });
    }
    var opacity = onActive ? "1" : "0.3";
    d0.style.opacity = opacity;
    if (d1) d1.style.opacity = opacity;
  });
}
