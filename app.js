/* ============================================================
   Space Policy Docket — app.js
   Plain vanilla JavaScript, three jobs:
     1. Tab switching (with URL hash support, e.g. #regulators)
     2. Load bill data from data/bills.json
     3. Search, topic filter, and column sorting for the table
   ============================================================ */

/* ------------------ 1. TABS ------------------ */

const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = document.querySelectorAll(".tab-panel");

function activateTab(tabId) {
  // Show the matching panel, highlight the matching button, hide the rest.
  tabButtons.forEach(btn =>
    btn.classList.toggle("active", btn.dataset.tab === tabId)
  );
  tabPanels.forEach(panel =>
    panel.classList.toggle("active", panel.id === tabId)
  );
}

tabButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    activateTab(btn.dataset.tab);
    // Put the tab in the URL so links can point to a specific tab.
    history.replaceState(null, "", "#" + btn.dataset.tab);
  });
});

// If the page loads with a hash like #regulators, open that tab.
const initialTab = location.hash.replace("#", "");
if (initialTab && document.getElementById(initialTab)) {
  activateTab(initialTab);
}

/* ------------------ 2. LOAD DATA ------------------ */

let allBills = [];                       // full dataset, never mutated
let sortKey = "action_date";             // current sort column
let sortDir = "desc";                    // "asc" or "desc"

const tbody = document.querySelector("#bills-table tbody");
const searchInput = document.getElementById("search-input");
const topicFilter = document.getElementById("topic-filter");
const resultCount = document.getElementById("result-count");

fetch("data/bills.json")
  .then(response => response.json())
  .then(data => {
    allBills = data.bills;
    buildTopicFilter(allBills);
    render();
  })
  .catch(() => {
    // fetch() fails if you open index.html by double-clicking it.
    // Serve the folder instead:  python3 -m http.server 8000
    tbody.innerHTML =
      '<tr class="empty-row"><td colspan="6">Could not load data/bills.json. ' +
      "If you opened this file directly, run a local server instead " +
      "(see README) — or view the live site.</td></tr>";
  });

// Collect every unique topic and add it to the dropdown.
function buildTopicFilter(bills) {
  const topics = new Set();
  bills.forEach(b => b.topics.forEach(t => topics.add(t)));
  [...topics].sort().forEach(t => {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    topicFilter.appendChild(opt);
  });
}

/* ------------------ 3. FILTER + SORT + RENDER ------------------ */

function getVisibleBills() {
  const query = searchInput.value.trim().toLowerCase();
  const topic = topicFilter.value;

  let bills = allBills.filter(b => {
    const haystack = (
      b.bill + " " + b.title + " " + b.sponsor + " " +
      b.latest_action + " " + b.topics.join(" ")
    ).toLowerCase();
    const matchesQuery = !query || haystack.includes(query);
    const matchesTopic = !topic || b.topics.includes(topic);
    return matchesQuery && matchesTopic;
  });

  // Sort a copy so the original order is preserved.
  bills = [...bills].sort((a, b) => {
    const av = a[sortKey] || "";
    const bv = b[sortKey] || "";
    const cmp = av.localeCompare(bv, undefined, { numeric: true });
    return sortDir === "asc" ? cmp : -cmp;
  });

  return bills;
}

function render() {
  const bills = getVisibleBills();

  resultCount.textContent =
    bills.length + " of " + allBills.length + " bills";

  if (bills.length === 0) {
    tbody.innerHTML =
      '<tr class="empty-row"><td colspan="6">No bills match your search.</td></tr>';
    return;
  }

  tbody.innerHTML = bills.map(b => `
    <tr>
      <td class="bill-cell">
        <a href="${b.url}" target="_blank" rel="noopener">${b.bill}</a>
        <span class="congress">${b.congress} Congress</span>
      </td>
      <td class="title-cell">${b.title}</td>
      <td>${b.sponsor}</td>
      <td class="action-cell">${b.latest_action}</td>
      <td class="date-cell">${formatDate(b.action_date)}</td>
      <td>${b.topics.map(t => `<span class="tag">${t}</span>`).join("")}</td>
    </tr>
  `).join("");
}

// "2026-03-12" → "Mar 12, 2026"
function formatDate(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  const months = ["Jan","Feb","Mar","Apr","May","Jun",
                  "Jul","Aug","Sep","Oct","Nov","Dec"];
  return months[m - 1] + " " + d + ", " + y;
}

// Re-render whenever the user types or changes the topic.
searchInput.addEventListener("input", render);
topicFilter.addEventListener("change", render);

// Clicking a sortable column header sorts by it; clicking again flips direction.
document.querySelectorAll("th.sortable").forEach(th => {
  th.addEventListener("click", () => {
    const key = th.dataset.sort;
    if (sortKey === key) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortKey = key;
      sortDir = key === "action_date" ? "desc" : "asc";
    }
    // Update the little arrows in the headers.
    document.querySelectorAll("th.sortable").forEach(h =>
      h.classList.remove("sorted-asc", "sorted-desc")
    );
    th.classList.add(sortDir === "asc" ? "sorted-asc" : "sorted-desc");
    render();
  });
});
