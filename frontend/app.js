// === App entry: init, event binding, reset ===

initMap();

// Empty state visibility toggle
function toggleEmptyState(show) {
  var es = $("empty-state");
  if (es) es.classList.toggle("show", show);
}

// POI search on destination input
var searchTimer = null;
dest.addEventListener("input", function() {
  clearTimeout(searchTimer);
  var val = dest.value.trim();
  if (val.length < 2) {
    toggleEmptyState(true);
    return;
  }
  searchTimer = setTimeout(function() {
    toggleEmptyState(false);
    $("poi-info").textContent = "搜索中.."; goBtn.disabled = true; fetchPois(val);
  }, 500);
});

// Also enable go-btn when user manually enters a valid destination (no POI needed)
dest.addEventListener("change", function() {
  if (dest.value.trim().length >= 2 && goBtn.disabled) {
    goBtn.disabled = false;
  }
});

// Clear selected
var clearAll = $("clear-all-btn");
if (clearAll) {
  clearAll.addEventListener("click", function() {
    exploreMarkers.forEach(function(m) { m._selected = false; });
    selectedPois = []; updateSelBar();
  });
}

// Form submit — use click on button instead of form submit
var goBtn = $("go-btn");
goBtn.addEventListener("click", function(e) {
  e.preventDefault();
  if (goBtn.disabled) return;
  if (!dest.value.trim()) { dest.focus(); return; }
  var payload = {
    destination: dest.value.trim(), origin: originInp.value.trim() || undefined,
    start_date: startDateInp.value || undefined, end_date: endDateInp.value || undefined,
    travelers: parseInt(travelers.value) || 1, budget: parseFloat(budget.value) || undefined,
    interests: interestsCustom && interestsCustom.value ? interestsCustom.value.split(",").map(function(s){return s.trim();}).filter(Boolean) : ["观光"],
    special_requirements: special.value ? special.value.trim() : undefined,
    selected_pois: selectedPois.length ? selectedPois.map(function(p){return{id:p.id,name:p.name,location:p.location,address:p.address,type:p.type};}) : []
  };
  goBtn.disabled = true; goBtn.classList.add("loading");
  resetProg(); setMode("progress");
  fetch("/api/plan", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(payload)})
    .then(function(r){return r.json();})
    .then(function(d){listenSSE(d.session_id);})
    .catch(function(err){showErr(err.message);});
});

function resetAll() {
  var f = $("plan-form"); if (f) f.reset();
  if (interestsCustom) interestsCustom.value = "";
  selectedPois = []; travelers.value = 1;
  exploreMarkers.forEach(function(m) { try { exploreMap.removeLayer(m); } catch(_) {} }); exploreMarkers = [];
  $("sel-bar").classList.add("hidden"); $("poi-info").textContent = "输入目的地";
  if (mapInstance) { mapInstance.remove(); mapInstance = null; }
  savedTripPlan = null; goBtn.disabled = false; goBtn.classList.remove("loading");
  toggleEmptyState(true);
  setMode("form");
  if (exploreMap) {
    exploreMap.setView([35, 110], 4);
    setTimeout(function() { exploreMap.invalidateSize(); }, 100);
  }
}
