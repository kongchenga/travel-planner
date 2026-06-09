// === State & DOM refs ===
let selectedPois = [], exploreMarkers = [], exploreMap = null, mapInstance = null;
let _sseClosed = false, savedTripPlan = null;

const $ = id => document.getElementById(id);
const dest = $("destination"), origin = $("origin");
const startDate = $("start-date"), endDate = $("end-date");
const travelers = $("travelers"), budget = $("budget");
const special = $("special"), interestsCustom = $("interests-custom"), goBtn = $("go-btn");

function esc(s) { return (s || "").replace(/[<>&"']/g," "); }
function escAttr(s) { return (s || "").replace(/"/g,"&quot;"); }
function adj(d) { const v = parseInt(travelers.value) || 1; travelers.value = Math.max(1, Math.min(99, v + d)); }
