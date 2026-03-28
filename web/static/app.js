function normaliseText(value) {
  return String(value || "").trim().toLowerCase();
}

var MONTH_ABBREVIATIONS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];

function copyPlainText(value, successMessage) {
  var text = String(value || "");
  if (!text) {
    return;
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () {
      window.alert(successMessage || "Copied.");
    }).catch(function () {
      window.prompt("Copy this:", text);
    });
  } else {
    window.prompt("Copy this:", text);
  }
}

function updatePBSScheduleBanner(data) {
  var latestNode = document.getElementById("pbs-schedule-latest");
  var metaNode = document.getElementById("pbs-schedule-meta");
  if (!latestNode || !metaNode || !data) {
    return;
  }

  latestNode.textContent = data.latest_api_schedule || "Unknown";
  latestNode.textContent = data.latest_api_schedule_label || data.latest_api_schedule || "Unknown";

  if (data.last_checked_at) {
    metaNode.textContent = "Last checked " + data.last_checked_at + " | Current database schedule " + (data.current_db_schedule_label || data.current_db_schedule || "Unknown");
  } else {
    metaNode.textContent = "Current database schedule " + (data.current_db_schedule_label || data.current_db_schedule || "Unknown");
  }
}

function runIncrementalSyncFromPrompt() {
  fetch("/api/v1/admin/sync/incremental", { method: "POST" })
    .then(function (response) { return response.json().then(function (data) { return { ok: response.ok, data: data }; }); })
    .then(function (result) {
      if (!result.ok) {
        window.alert(result.data.detail || "Incremental sync could not be started.");
        return;
      }
      window.alert(result.data.message || "Incremental sync started.");
    })
    .catch(function (error) {
      window.alert("Incremental sync failed to start: " + error.message);
    });
}

function loadPBSScheduleStatus() {
  var latestNode = document.getElementById("pbs-schedule-latest");
  var metaNode = document.getElementById("pbs-schedule-meta");
  if (!latestNode || !metaNode) {
    return;
  }

  fetch("/web/pbs-schedule-status")
    .then(function (response) { return response.json(); })
    .then(function (data) {
      updatePBSScheduleBanner(data);
    })
    .catch(function (error) {
      latestNode.textContent = "Unavailable";
      metaNode.textContent = "Could not load PBS schedule status: " + error.message;
    });
}

function checkLatestPBSSchedule() {
  var latestNode = document.getElementById("pbs-schedule-latest");
  var metaNode = document.getElementById("pbs-schedule-meta");
  if (latestNode) {
    latestNode.textContent = "Checking...";
  }
  if (metaNode) {
    metaNode.textContent = "Checking latest PBS schedule availability...";
  }

  fetch("/web/pbs-schedule-check", { method: "POST" })
    .then(function (response) { return response.json(); })
    .then(function (data) {
      updatePBSScheduleBanner(data);
      if (metaNode) {
        metaNode.textContent = (data.last_checked_at ? "Last checked " + data.last_checked_at + " | " : "") + (data.message || "");
      }

      if (data.new_schedule_available) {
        if (window.confirm((data.message || "A new PBS schedule is available.") + " Run incremental sync now?")) {
          runIncrementalSyncFromPrompt();
        }
      }
    })
    .catch(function (error) {
      if (latestNode) {
        latestNode.textContent = "Unavailable";
      }
      if (metaNode) {
        metaNode.textContent = "Could not check the latest PBS schedule: " + error.message;
      }
    });
}

function dataAttributeName(key) {
  return "data-" + String(key || "").replace(/_/g, "-");
}

function getRowValue(row, key) {
  return row.getAttribute(dataAttributeName(key)) || "";
}

function parseComparable(value, type) {
  var raw = String(value || "").trim();
  if (!raw) {
    return type === "number" || type === "date" ? Number.POSITIVE_INFINITY : "";
  }

  if (raw === "Multiple") {
    return Number.POSITIVE_INFINITY;
  }

  if (type === "date") {
    var time = Date.parse(raw);
    return isNaN(time) ? Number.POSITIVE_INFINITY : time;
  }

  if (type === "number") {
    var numeric = parseFloat(raw.replace(/[^0-9.-]/g, ""));
    return isNaN(numeric) ? Number.POSITIVE_INFINITY : numeric;
  }

  return raw.toLowerCase();
}

function formatMedicareMonthDisplay(yyyymm) {
  var raw = String(yyyymm || "").trim();
  var year;
  var monthIndex;

  if (!/^\d{6}$/.test(raw)) {
    return "";
  }

  year = raw.slice(0, 4);
  monthIndex = parseInt(raw.slice(4, 6), 10) - 1;
  if (monthIndex < 0 || monthIndex > 11) {
    return "";
  }

  return MONTH_ABBREVIATIONS[monthIndex] + "-" + year;
}

function parseMedicareMonthValue(value) {
  var raw = String(value || "").trim();
  var upper;
  var compact;
  var match;
  var monthIndex;

  if (!raw) {
    return "";
  }

  upper = raw.toUpperCase();
  compact = upper.replace(/\s+/g, "");

  if (/^\d{6}$/.test(compact)) {
    monthIndex = parseInt(compact.slice(4, 6), 10);
    return monthIndex >= 1 && monthIndex <= 12 ? compact : "";
  }

  match = compact.match(/^(\d{4})-(\d{2})$/);
  if (match) {
    monthIndex = parseInt(match[2], 10);
    return monthIndex >= 1 && monthIndex <= 12 ? match[1] + match[2] : "";
  }

  match = upper.match(/^([A-Z]{3})-(\d{4})$/);
  if (match) {
    monthIndex = MONTH_ABBREVIATIONS.indexOf(match[1]);
    return monthIndex >= 0 ? match[2] + String(monthIndex + 1).padStart(2, "0") : "";
  }

  return "";
}

function getMedicareMonthPickerValue(id) {
  var picker = document.getElementById(id);
  return picker ? parseMedicareMonthValue(picker.value) : "";
}

function normaliseMedicareMonthPicker(id) {
  var picker = document.getElementById(id);
  var parsedValue;

  if (!picker) {
    return "";
  }

  parsedValue = parseMedicareMonthValue(picker.value);
  if (parsedValue) {
    picker.value = formatMedicareMonthDisplay(parsedValue);
  }
  return parsedValue;
}

function collectRowPairs(table) {
  var rows = table.tBodies && table.tBodies[0] ? Array.prototype.slice.call(table.tBodies[0].children) : [];
  var pairs = [];
  var index;

  for (index = 0; index < rows.length; index += 1) {
    if (!rows[index].classList.contains("result-row")) {
      continue;
    }

    pairs.push({
      row: rows[index],
      historyRow: rows[index + 1] && rows[index + 1].classList.contains("history-row") ? rows[index + 1] : null,
    });

    if (rows[index + 1] && rows[index + 1].classList.contains("history-row")) {
      index += 1;
    }
  }

  return pairs;
}

function updateSortIndicators(table) {
  var buttons = table.querySelectorAll(".sort-button");
  var index;

  for (index = 0; index < buttons.length; index += 1) {
    buttons[index].setAttribute("data-direction", "none");
    buttons[index].setAttribute("data-active", "false");
  }

  if (!table.dataset.sortKey) {
    return;
  }

  var active = table.querySelector('.sort-button[data-sort-key="' + table.dataset.sortKey + '"]');
  if (active) {
    active.setAttribute("data-direction", table.dataset.sortDirection || "asc");
    active.setAttribute("data-active", "true");
  }
}

function applyTableState(table) {
  var tbody = table.tBodies && table.tBodies[0];
  if (!tbody) {
    return;
  }

  var pairs = collectRowPairs(table);
  var filters = {};
  var filterEls = table.querySelectorAll(".column-filter");
  var i;

  for (i = 0; i < filterEls.length; i += 1) {
    if (filterEls[i].value) {
      filters[filterEls[i].getAttribute("data-filter-key")] = {
        value: normaliseText(filterEls[i].value),
        exact: filterEls[i].tagName === "SELECT" && filterEls[i].getAttribute("data-filter-match") !== "contains",
      };
    }
  }

  var visiblePairs = pairs.filter(function (pair) {
    return Object.keys(filters).every(function (key) {
      var rowValue = normaliseText(getRowValue(pair.row, key));
      if (filters[key].exact) {
        return rowValue === filters[key].value;
      }
      return rowValue.indexOf(filters[key].value) !== -1;
    });
  });

  var sortKey = table.dataset.sortKey;
  var sortType = table.dataset.sortType || "text";
  var direction = table.dataset.sortDirection === "desc" ? -1 : 1;

  if (sortKey) {
    visiblePairs.sort(function (left, right) {
      var leftValue = parseComparable(getRowValue(left.row, sortKey), sortType);
      var rightValue = parseComparable(getRowValue(right.row, sortKey), sortType);

      if (leftValue < rightValue) {
        return -1 * direction;
      }
      if (leftValue > rightValue) {
        return 1 * direction;
      }

      return normaliseText(getRowValue(left.row, "pbs_code")).localeCompare(
        normaliseText(getRowValue(right.row, "pbs_code"))
      ) * direction;
    });
  }

  for (i = 0; i < pairs.length; i += 1) {
    pairs[i].row.style.display = "none";
    if (pairs[i].historyRow) {
      pairs[i].historyRow.style.display = "none";
    }
  }

  for (i = 0; i < visiblePairs.length; i += 1) {
    tbody.appendChild(visiblePairs[i].row);
    visiblePairs[i].row.style.display = "";
    if (visiblePairs[i].historyRow) {
      tbody.appendChild(visiblePairs[i].historyRow);
      visiblePairs[i].historyRow.style.display = visiblePairs[i].historyRow.classList.contains("is-hidden") ? "none" : "";
    }
  }

  var counter = table.closest(".results-shell");
  if (counter) {
    var countNode = counter.querySelector(".results-count");
    if (countNode) {
      countNode.textContent = visiblePairs.length + " grouped result" + (visiblePairs.length === 1 ? "" : "s");
    }
  }

  updateSortIndicators(table);
  updateSelectAllState(table);
  refreshReportSection();
}

function initSearchResultsTable(table) {
  if (!table || table.dataset.initialised === "true") {
    return;
  }

  table.dataset.initialised = "true";
  table.dataset.sortKey = "drug_name";
  table.dataset.sortType = "text";
  table.dataset.sortDirection = "asc";
  updateSortIndicators(table);
}

function toggleHistory(button) {
  var row = button.closest(".result-row");
  if (!row) {
    return;
  }

  var historyRow = row.nextElementSibling;
  if (!historyRow || !historyRow.classList.contains("history-row")) {
    return;
  }

  var shouldOpen = historyRow.classList.contains("is-hidden");
  historyRow.classList.toggle("is-hidden", !shouldOpen);
  historyRow.style.display = shouldOpen ? "" : "none";
  button.textContent = shouldOpen ? "−" : "+";
  button.setAttribute("aria-expanded", shouldOpen ? "true" : "false");

  if (shouldOpen && row.getAttribute("data-history-loaded") !== "true") {
    var url = button.getAttribute("data-url");
    var targetId = button.getAttribute("data-target");
    if (window.htmx && url && targetId) {
      window.htmx.ajax("GET", url, "#" + targetId);
      row.setAttribute("data-history-loaded", "true");
    }
  }
}

function getResultRows() {
  return Array.prototype.slice.call(document.querySelectorAll("#results tbody tr.result-row")).filter(function (row) {
    return row.style.display !== "none";
  });
}

function getEarliestFirstListedMonthValue() {
  var earliest = null;

  getResultRows().forEach(function (row) {
    var listedText = getRowValue(row, "first_listed_date");
    var parts;
    var comparable;
    var monthValue;

    if (!listedText) {
      return;
    }

    parts = String(listedText).split("-");
    if (parts.length < 2 || !parts[0] || !parts[1]) {
      return;
    }

    comparable = parts[0] + parts[1];
    monthValue = comparable;
    if (!earliest || comparable < earliest.comparable) {
      earliest = {
        comparable: comparable,
        monthValue: monthValue,
      };
    }
  });

  return earliest ? earliest.monthValue : "";
}

function syncMedicareStartDatePicker() {
  var picker = document.getElementById("medicare-start-date");
  var earliestMonthValue;
  var previousAutoValue;

  if (!picker) {
    return;
  }

  earliestMonthValue = getEarliestFirstListedMonthValue();
  previousAutoValue = picker.dataset.autoValue || "";

  if (!earliestMonthValue) {
    if (picker.dataset.autoManaged === "true") {
      picker.value = "";
      picker.dataset.autoValue = "";
    }
    return;
  }

  if (!picker.value || picker.dataset.autoManaged === "true" || picker.value === previousAutoValue) {
    picker.value = formatMedicareMonthDisplay(earliestMonthValue);
    picker.dataset.autoValue = earliestMonthValue;
    picker.dataset.autoManaged = "true";
  }
}

function getSelectedResultRows() {
  return getResultRows().filter(function (row) {
    var checkbox = row.querySelector(".report-select-checkbox");
    return checkbox && checkbox.checked;
  });
}

function updateSelectAllState(table) {
  var selectAll = table.querySelector(".report-select-all");
  var visibleRows;
  var selectedCount;
  if (!selectAll) {
    return;
  }

  visibleRows = getResultRows();
  selectedCount = visibleRows.filter(function (row) {
    var checkbox = row.querySelector(".report-select-checkbox");
    return checkbox && checkbox.checked;
  }).length;

  selectAll.indeterminate = selectedCount > 0 && selectedCount < visibleRows.length;
  selectAll.checked = visibleRows.length > 0 && selectedCount === visibleRows.length;
}

function getPBSReportCodes() {
  var seen = {};
  return getSelectedResultRows()
    .map(function (row) {
      return getRowValue(row, "pbs_code");
    })
    .filter(function (code) {
      if (!code || seen[code]) {
        return false;
      }
      seen[code] = true;
      return true;
    });
}

function getMedicareEndDate() {
  return getMedicareMonthPickerValue("medicare-end-date");
}

function getMedicareStartDate() {
  var pickerValue = getMedicareMonthPickerValue("medicare-start-date");
  if (pickerValue) {
    return pickerValue;
  }

  var earliestMonthValue = getEarliestFirstListedMonthValue();
  if (earliestMonthValue) {
    return earliestMonthValue;
  }

  return "202501";
}

function getReportVar() {
  var sel = document.getElementById("report-var");
  return sel ? sel.value : "SERVICES";
}

function getReportFormat() {
  var sel = document.getElementById("report-format");
  return sel ? sel.value : "2";
}

function buildReportParams() {
  var uniqueCodes = getPBSReportCodes();
  var startDate;
  var endDate;
  if (!uniqueCodes.length) {
    return null;
  }
  if (uniqueCodes.length > 20) {
    return { error: "Medicare Statistics allows up to 20 item codes per report. Please deselect some rows first." };
  }

  startDate = getMedicareStartDate();
  endDate = getMedicareEndDate();
  if (!startDate) {
    return { error: "Enter a valid Stats start date in MMM-YYYY format." };
  }
  if (!endDate) {
    return { error: "Enter a valid Stats end date in MMM-YYYY format." };
  }

  var params = new URLSearchParams();
  params.set("pbs_codes", uniqueCodes.join(","));
  params.set("start_date", startDate);
  params.set("end_date", endDate);
  params.set("var", getReportVar());
  params.set("rpt_fmt", getReportFormat());
  return params;
}

function getDirectReportURL() {
  var params = buildReportParams();
  if (!params || params.error) {
    return null;
  }

  return "/web/pbs-report?" + params.toString();
}

function viewPBSReport() {
  var params = buildReportParams();
  var url;
  if (!params) {
    window.alert("Select at least one visible item code for the Medicare Statistics report.");
    return;
  }
  if (params.error) {
    window.alert(params.error);
    return;
  }
  url = "/web/pbs-report?" + params.toString();
  window.open(url, "_blank", "noopener,noreferrer");
}

function copyReportURL() {
  var params = buildReportParams();
  var url;
  if (!params) {
    window.alert("Select at least one visible item code for the Medicare Statistics report.");
    return;
  }
  if (params.error) {
    window.alert(params.error);
    return;
  }

  url = window.location.origin + "/web/pbs-report?" + params.toString();
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(function () {
      window.alert("URL copied.");
    }).catch(function () {
      window.prompt("Copy this URL:", url);
    });
  } else {
    window.prompt("Copy this URL:", url);
  }
}

function downloadExcel() {
  var params = buildReportParams();
  if (!params) {
    window.alert("Select at least one visible item code for the Medicare Statistics report.");
    return;
  }
  if (params.error) {
    window.alert(params.error);
    return;
  }
  window.open("/web/pbs-report-excel?" + params.toString(), "_blank", "noopener,noreferrer");
}

function refreshReportSection() {
  var reportSection = document.getElementById("report-section");
  var summary = document.getElementById("report-selection-summary");
  var visibleRows = getResultRows();
  var selectedRows = getSelectedResultRows();
  var selectedCodes = getPBSReportCodes();
  if (!reportSection) {
    return;
  }
  reportSection.style.display = visibleRows.length > 0 ? "block" : "none";
  syncMedicareStartDatePicker();
  if (!summary) {
    return;
  }

  if (!visibleRows.length) {
    summary.textContent = "";
    return;
  }

  if (!selectedRows.length) {
    summary.textContent = "No item codes selected for the Medicare Statistics report.";
    summary.setAttribute("data-state", "empty");
    return;
  }

  if (selectedCodes.length > 20) {
    summary.textContent = selectedCodes.length + " item codes selected. Medicare Statistics allows up to 20 per report, so please deselect at least " + (selectedCodes.length - 20) + ".";
    summary.setAttribute("data-state", "warning");
    return;
  }

  summary.textContent = selectedCodes.length + " item code" + (selectedCodes.length === 1 ? "" : "s") + " selected for the Medicare Statistics report.";
  summary.setAttribute("data-state", "ready");
}

function initPageEnhancements(root) {
  var scope = root || document;
  var tables = scope.querySelectorAll ? scope.querySelectorAll('table[data-enhanced="search-results"]') : [];
  var i;
  for (i = 0; i < tables.length; i += 1) {
    initSearchResultsTable(tables[i]);
    applyTableState(tables[i]);
  }
  refreshReportSection();
}

function updateSavedReportWindowFields() {
  var windowType = document.getElementById("saved-report-window-type");
  var fields;
  if (!windowType) {
    return;
  }

  fields = document.querySelectorAll("[data-window-field]");
  Array.prototype.forEach.call(fields, function (field) {
    var expected = field.getAttribute("data-window-field");
    var isActive = expected === windowType.value;
    var inputs = field.querySelectorAll("input, select, textarea");

    field.classList.toggle("is-disabled", !isActive);
    Array.prototype.forEach.call(inputs, function (input) {
      input.disabled = !isActive;
    });
  });
}

function updateSavedReportSourceFields() {
  var sourceType = document.getElementById("saved-report-source-type");
  var fields;
  if (!sourceType) {
    return;
  }

  fields = document.querySelectorAll("[data-source-field]");
  Array.prototype.forEach.call(fields, function (field) {
    var expected = field.getAttribute("data-source-field");
    var isActive = expected === sourceType.value;
    var inputs = field.querySelectorAll("input, select, textarea");

    field.classList.toggle("is-disabled", !isActive);
    Array.prototype.forEach.call(inputs, function (input) {
      input.disabled = !isActive;
    });
  });
}

function validateSavedReportForm(form) {
  var sourceType;
  var drugName;
  var brandName;
  if (!form) {
    return true;
  }

  sourceType = form.querySelector('[name="source_type"]');
  if (!sourceType || sourceType.value !== "search_based") {
    return true;
  }

  drugName = form.querySelector('[name="drug_name"]');
  brandName = form.querySelector('[name="brand_name"]');
  if ((drugName && drugName.value.trim()) || (brandName && brandName.value.trim())) {
    return true;
  }

  window.alert("Search-based saved reports must include at least one Drug or Brand value.");
  return false;
}

document.addEventListener("click", function (event) {
  var copyButton = event.target.closest("[data-copy-text]");
  if (copyButton) {
    copyPlainText(copyButton.getAttribute("data-copy-text"), "Hyperlink copied.");
    return;
  }

  var sortButton = event.target.closest(".sort-button");
  if (sortButton) {
    var table = sortButton.closest('table[data-enhanced="search-results"]');
    if (!table) {
      return;
    }

    var sortKey = sortButton.getAttribute("data-sort-key");
    var sortType = sortButton.getAttribute("data-sort-type") || "text";
    if (table.dataset.sortKey === sortKey) {
      table.dataset.sortDirection = table.dataset.sortDirection === "asc" ? "desc" : "asc";
    } else {
      table.dataset.sortKey = sortKey;
      table.dataset.sortType = sortType;
      table.dataset.sortDirection = "asc";
    }
    applyTableState(table);
    return;
  }

  var toggle = event.target.closest(".history-toggle");
  if (toggle) {
    toggleHistory(toggle);
  }
});

document.addEventListener("change", function (event) {
  if (event.target.id === "medicare-start-date") {
    var startParsedValue = normaliseMedicareMonthPicker("medicare-start-date");
    event.target.dataset.autoManaged = startParsedValue === (event.target.dataset.autoValue || "") ? "true" : "false";
    return;
  }

  if (event.target.id === "medicare-end-date") {
    normaliseMedicareMonthPicker("medicare-end-date");
    return;
  }

  if (event.target.id === "saved-report-window-type") {
    updateSavedReportWindowFields();
    return;
  }

  if (event.target.id === "saved-report-source-type") {
    updateSavedReportSourceFields();
    return;
  }

  var selectAll = event.target.closest(".report-select-all");
  if (selectAll) {
    getResultRows().forEach(function (row) {
      var checkbox = row.querySelector(".report-select-checkbox");
      if (checkbox) {
        checkbox.checked = selectAll.checked;
      }
    });
    refreshReportSection();
    return;
  }

  var reportCheckbox = event.target.closest(".report-select-checkbox");
  if (reportCheckbox) {
    var checkboxTable = reportCheckbox.closest('table[data-enhanced="search-results"]');
    if (checkboxTable) {
      updateSelectAllState(checkboxTable);
    }
    refreshReportSection();
    return;
  }

  var filter = event.target.closest(".column-filter");
  if (!filter) {
    return;
  }
  var table = filter.closest('table[data-enhanced="search-results"]');
  if (table) {
    applyTableState(table);
  }
});

document.addEventListener("DOMContentLoaded", function () {
  var endPicker = document.getElementById("medicare-end-date");
  var form = document.getElementById("item-search-form");
  if (endPicker) {
    endPicker.value = formatMedicareMonthDisplay(endPicker.dataset.initialMonth || "");
  }
  if (form) {
    form.addEventListener("reset", function () {
      window.setTimeout(function () {
        var results = document.getElementById("results");
        if (results) {
          results.innerHTML = "";
        }
        refreshReportSection();
      }, 0);
    });
  }
  var savedReportForm = document.getElementById("saved-report-form");
  if (savedReportForm) {
    savedReportForm.addEventListener("submit", function (event) {
      if (!validateSavedReportForm(savedReportForm)) {
        event.preventDefault();
      }
    });
  }
  initPageEnhancements(document);
  updateSavedReportWindowFields();
  updateSavedReportSourceFields();
  loadPBSScheduleStatus();
});

window.viewPBSReport = viewPBSReport;
window.copyReportURL = copyReportURL;
window.downloadExcel = downloadExcel;

document.addEventListener("htmx:afterSwap", function (event) {
  if (event.detail && event.detail.target) {
    initPageEnhancements(event.detail.target);
  }
});
