// === App entry: init, event binding, reset ===

initMap();

// POI search on destination input
let searchTimer = null;
dest.addEventListener("input", function() {
  clearTimeout(searchTimer);
  const val = dest.value.trim();
  if (val.length < 2) return;
  searchTimer = setTimeout(() => { $("poi-info").textContent = "搜索中…"; goBtn.disabled = true; fetchPois(val); }, 500);
});

// Clear selected
$("clear-all-btn").addEventListener("click", function() {
  exploreMarkers.forEach(m => { m._selected = false; const d = m.getElement() && m.getElement().querySelector("div"); if (d) d.style.borderColor = "rgba(255,255,255,.2)"; });
  selectedPois = []; updateSelBar();
  $("poi-info").textContent = exploreMarkers.length + " 个地点";
});

// Form submit
$("plan-form").addEventListener("submit", async e => {
  e.preventDefault();
  if (goBtn.disabled) return;
  if (!dest.value.trim()) { dest.focus(); return; }
  const payload = {
    destination: dest.value.trim(), origin: origin.value.trim() || undefined,
    start_date: startDate.value || undefined, end_date: endDate.value || undefined,
    travelers: parseInt(travelers.value) || 1, budget: parseFloat(budget.value) || undefined,
    interests: interestsCustom && interestsCustom.value ? interestsCustom.value.split(",").map(s=>s.trim()).filter(Boolean) : ["观光"],
    special_requirements: special.value.trim() || undefined,
    selected_pois: selectedPois.length ? selectedPois.map(p => ({ id: p.id, name: p.name, location: p.location, address: p.address, type: p.type })) : [],
  };
  goBtn.disabled = true; goBtn.classList.add("loading");
  resetProg(); setMode("progress");
  try {
    const res = await fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
    const { session_id } = await res.json();
    listenSSE(session_id);
  } catch (err) { showErr(err.message); }
});

function resetAll() {
  $("plan-form").reset();
  if (interestsCustom) interestsCustom.value = "";
  selectedPois = []; travelers.value = 1;
  exploreMarkers.forEach(function(m) { try { exploreMap.removeLayer(m); } catch(_) {} }); exploreMarkers = [];
  $("sel-bar").classList.add("hidden"); $("poi-info").textContent = "输入目的地";
  if (mapInstance) { mapInstance.remove(); mapInstance = null; }
  savedTripPlan = null; goBtn.disabled = false; goBtn.classList.remove("loading");
  setMode("form");
  setTimeout(function() { if (exploreMap) exploreMap.setView([35, 110], 4); exploreMap.invalidateSize(); }, 100);
}
