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

// "?v=" + timestamp stops browsers from showing yesterday's cached data
fetch("data/bills.json?v=" + Date.now())
  .then(response => response.json())
  .then(data => {
    allBills = data.bills;
    buildTopicFilter(allBills);
    render();
    renderStatus(data);
  })
  .catch(() => {
    // fetch() fails if you open index.html by double-clicking it.
    // Serve the folder instead:  python3 -m http.server 8000
    tbody.innerHTML =
      '<tr class="empty-row"><td colspan="6">Could not load data/bills.json. ' +
      "If you opened this file directly, run a local server instead " +
      "(see README) — or view the live site.</td></tr>";
  });

// The banner above the table: a warning while the data is sample,
// a quiet status line once the daily Congress.gov feed is live.
function renderStatus(data) {
  const status = document.getElementById("data-status");
  if (!status) return;
  status.hidden = false;
  if ((data.source || "").toLowerCase().includes("sample")) {
    status.innerHTML =
      "<strong>Sample data.</strong> Placeholder entries to test the layout — " +
      "the live Congress.gov feed replaces this shortly.";
  } else {
    status.classList.add("notice-live");
    status.innerHTML =
      "<strong>Live data</strong> from the Congress.gov API · " +
      allBills.length + " bills tracked · updated " +
      formatDate(data.generated) + " · refreshes daily.";
  }
}

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

/* ------------------ 4. DOCKET SUB-TABS (Bills / Rules) ------------------ */

const subtabButtons = document.querySelectorAll("#docket .subtab-btn");
subtabButtons.forEach(btn => {
  btn.addEventListener("click", () => {
    subtabButtons.forEach(b => b.classList.toggle("active", b === btn));
    document.getElementById("view-bills").hidden = btn.dataset.view !== "bills";
    document.getElementById("view-rules").hidden = btn.dataset.view !== "rules";
  });
});

/* ------------------ 5. AGENCY RULEMAKING TABLE ------------------ */

let allRules = [];
const rulesBody = document.querySelector("#rules-table tbody");
const rulesSearch = document.getElementById("rules-search");
const typeFilter = document.getElementById("type-filter");
const rulesCount = document.getElementById("rules-count");

fetch("data/rules.json?v=" + Date.now())
  .then(response => response.json())
  .then(data => {
    allRules = data.rules;
    renderRules();
  })
  .catch(() => {
    // The rules file doesn't exist until the daily automation runs with it.
    rulesBody.innerHTML =
      '<tr class="empty-row"><td colspan="6">Rule data hasn\'t been generated ' +
      "yet — it arrives with the next daily refresh.</td></tr>";
  });

function renderRules() {
  const query = rulesSearch.value.trim().toLowerCase();
  const type = typeFilter.value;

  const rules = allRules.filter(r => {
    const haystack = (
      r.document + " " + r.title + " " + r.agency + " " +
      r.type + " " + r.topics.join(" ")
    ).toLowerCase();
    const matchesQuery = !query || haystack.includes(query);
    const matchesType = !type || r.type === type;
    return matchesQuery && matchesType;
  });

  rulesCount.textContent = rules.length + " of " + allRules.length + " documents";

  if (rules.length === 0) {
    rulesBody.innerHTML =
      '<tr class="empty-row"><td colspan="6">No documents match your search.</td></tr>';
    return;
  }

  rulesBody.innerHTML = rules.map(r => `
    <tr>
      <td class="bill-cell">
        <a href="${r.url}" target="_blank" rel="noopener">${r.document}</a>
      </td>
      <td class="title-cell">${r.title}</td>
      <td>${r.agency}</td>
      <td><span class="badge ${r.type === "Final Rule" ? "badge-final" : "badge-proposed"}">${r.type}</span></td>
      <td class="date-cell">${formatDate(r.published)}</td>
      <td class="date-cell">${r.comments_close_on
        ? '<span class="deadline">' + formatDate(r.comments_close_on) + "</span>"
        : "—"}</td>
    </tr>
  `).join("");
}

rulesSearch.addEventListener("input", renderRules);
typeFilter.addEventListener("change", renderRules);

/* ------------------ 6. "THIS WEEK" DIGEST ------------------ */

fetch("data/digest.json?v=" + Date.now())
  .then(response => response.json())
  .then(renderDigest)
  .catch(() => { /* no digest yet — leave the card hidden */ });

function digestSection(title, items) {
  return "<h4>" + title + "</h4><ul>" + items.join("") + "</ul>";
}

function renderDigest(d) {
  document.getElementById("digest-summary").innerHTML =
    "<strong>This Week in Space Policy</strong> — " + d.summary +
    ' <span class="digest-dates">(' + formatDate(d.window_start) +
    " – " + formatDate(d.window_end) + ")</span>";

  let html = "";
  if (d.bills && d.bills.length) {
    html += digestSection("On the Hill", d.bills.map(b =>
      `<li><a href="${b.url}" target="_blank" rel="noopener">${b.bill}</a> ` +
      `${b.title} — <em>${b.latest_action}</em> (${formatDate(b.action_date)})</li>`));
  }
  if (d.rules && d.rules.length) {
    html += digestSection("In the agencies", d.rules.map(r =>
      `<li>${r.type}: ${r.agency} — ` +
      `<a href="${r.url}" target="_blank" rel="noopener">${r.title}</a> ` +
      `(${formatDate(r.published)})</li>`));
  }
  if (d.deadlines && d.deadlines.length) {
    html += digestSection("Comment deadlines ahead", d.deadlines.map(x =>
      `<li><a href="${x.url}" target="_blank" rel="noopener">${x.title}</a> ` +
      `(${x.agency}) — closes <strong>${formatDate(x.closes)}</strong></li>`));
  }
  if (!html) html = '<p class="digest-quiet">A quiet week in space policy.</p>';

  document.getElementById("digest-body").innerHTML = html;
  document.getElementById("digest-card").hidden = false;
}

/* ------------------ 7. MONEY MAP ------------------ */

// "$22.4B" / "$830M" / "$140K" — compact money for tiles and bar tips.
function fmtMoney(n) {
  if (n >= 1e9) return "$" + (n / 1e9).toFixed(1).replace(/\.0$/, "") + "B";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(0) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(0) + "K";
  return "$" + n;
}

fetch("data/money.json?v=" + Date.now())
  .then(response => response.json())
  .then(initMoney)
  .catch(() => {
    document.getElementById("money-empty").hidden = false;
  });

function initMoney(data) {
  const status = document.getElementById("money-status");
  status.hidden = false;
  if ((data.source || "").toLowerCase().includes("sample")) {
    status.innerHTML = "<strong>Sample data.</strong> Placeholder figures to test " +
      "the layout — the live USAspending.gov feed replaces this shortly.";
  } else {
    status.classList.add("notice-live");
    status.innerHTML = "<strong>Live data</strong> from the USAspending.gov API · " +
      data.fiscal_year + " · updated " + formatDate(data.generated) + " · refreshes daily.";
  }

  document.getElementById("money-note").textContent =
    (data.note || "") + " Figures are " + data.fiscal_year + " prime-award obligations.";

  // One pill per program (only shown if there's more than one, e.g. NASA + Space Force).
  const pills = document.getElementById("program-pills");
  if (data.programs.length > 1) {
    pills.hidden = false;
    pills.innerHTML = data.programs.map((p, i) =>
      `<button class="subtab-btn ${i === 0 ? "active" : ""}" data-program="${p.key}">${p.label}</button>`
    ).join("");
    pills.querySelectorAll("button").forEach(btn => {
      btn.addEventListener("click", () => {
        pills.querySelectorAll("button").forEach(b =>
          b.classList.toggle("active", b === btn));
        renderProgram(data, data.programs.find(p => p.key === btn.dataset.program));
      });
    });
  }

  document.getElementById("money-content").hidden = false;
  renderProgram(data, data.programs[0]);
}

function renderProgram(data, program) {
  // Stat tiles.
  document.getElementById("stat-total-label").textContent =
    program.label + " obligations · " + data.fiscal_year;
  document.getElementById("stat-total").textContent = fmtMoney(program.total);
  const topR = program.recipients[0], topD = program.districts[0];
  document.getElementById("stat-recipient").textContent = topR ? topR.name : "—";
  document.getElementById("stat-recipient-amt").textContent = topR ? fmtMoney(topR.amount) : "";
  document.getElementById("stat-district").textContent = topD ? topD.name : "—";
  document.getElementById("stat-district-amt").textContent = topD ? fmtMoney(topD.amount) : "";

  // Bar charts (top 10 each) + full tables.
  barlist("bars-recipients", program.recipients.slice(0, 10));
  barlist("bars-districts", program.districts.slice(0, 10));
  miniTable("table-recipients", program.recipients, "Recipient");
  miniTable("table-districts", program.districts, "District");
}

// A horizontal bar per row: label | bar | value. All bars share one scale.
function barlist(id, rows) {
  const max = Math.max(...rows.map(r => r.amount), 1);
  document.getElementById(id).innerHTML = rows.map(r => `
    <div class="bar-row" title="${r.name} — $${r.amount.toLocaleString()}">
      <span class="bar-label">${r.name}</span>
      <div class="bar-track">
        <div class="bar-fill" style="width:${(r.amount / max * 100).toFixed(1)}%"></div>
      </div>
      <span class="bar-value">${fmtMoney(r.amount)}</span>
    </div>
  `).join("");
}

function miniTable(id, rows, header) {
  document.getElementById(id).innerHTML =
    `<thead><tr><th>#</th><th>${header}</th><th class="num">Amount</th></tr></thead><tbody>` +
    rows.map((r, i) =>
      `<tr><td>${i + 1}</td><td>${r.name}</td><td class="num">$${r.amount.toLocaleString()}</td></tr>`
    ).join("") + "</tbody>";
}
