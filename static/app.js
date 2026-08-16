const COLUMNS = ["aor_title_line_item","amount","need_by_date","gr_date","vendor","po_number","remarks","conduct_name","reporting_location","to_location"];
const LABELS = {aor_title_line_item:"AOR title / line item",amount:"Amount",need_by_date:"Need-By date",gr_date:"GR date",vendor:"Vendor",po_number:"PO number",remarks:"Remarks",conduct_name:"Conduct name",reporting_location:"Reporting location",to_location:"To location"};
let files = [], rows = [];
const $ = id => document.getElementById(id);
const dropzone = $("dropzone"), input = $("fileInput");

dropzone.addEventListener("click", () => input.click());
dropzone.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") input.click(); });
input.addEventListener("change", () => addFiles(input.files));
["dragenter","dragover"].forEach(name => dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.add("drag"); }));
["dragleave","drop"].forEach(name => dropzone.addEventListener(name, e => { e.preventDefault(); dropzone.classList.remove("drag"); }));
dropzone.addEventListener("drop", e => addFiles(e.dataTransfer.files));

function addFiles(selected) {
  for (const file of selected) if (file.name.toLowerCase().endsWith(".pdf") && !files.some(x => x.file.name === file.name)) files.push({file, po:""});
  input.value = ""; renderFiles();
}
function normalizeOa(value) {
  value = String(value ?? "").toUpperCase();
  const start = value.indexOf("2");
  if (start < 0) return "";
  const digits = value.slice(start).replace(/\D/g, "");
  return digits.length >= 6 ? `OA${digits}` : "";
}
function renderFiles() {
  $("fileList").replaceChildren(...files.map((entry, index) => {
    const item = document.createElement("div"); item.className = "file-item";
    const name = document.createElement("div"); name.className = "file-name"; name.textContent = entry.file.name;
    const size = document.createElement("small"); size.textContent = `${(entry.file.size / 1024).toFixed(0)} KB`; name.append(size);
    const label = document.createElement("label"); label.textContent = "OA / Quotation Number";
    const po = document.createElement("input"); po.placeholder = "e.g. QN26/07/0449"; po.value = entry.po; po.addEventListener("input", e => entry.po = e.target.value);
    po.addEventListener("blur", () => { entry.po = normalizeOa(entry.po); po.value = entry.po; }); label.append(po);
    const remove = document.createElement("button"); remove.className = "remove"; remove.type = "button"; remove.title = "Remove"; remove.textContent = "×"; remove.onclick = () => { files.splice(index,1); renderFiles(); };
    item.append(name,label,remove); return item;
  }));
  $("extractBtn").disabled = files.length === 0;
}

function resetApp() {
  files = [];
  rows = [];
  input.value = "";
  $("needBy").value = "";
  $("grDate").value = "";
  $("dataTable").replaceChildren();
  $("summary").textContent = "";
  $("results").hidden = true;
  renderFiles();
  showToast("Reset complete");
}

$("resetBtn").addEventListener("click", resetApp);

$("extractBtn").addEventListener("click", async () => {
  files.forEach(entry => entry.po = normalizeOa(entry.po));
  const button = $("extractBtn"); button.disabled = true; button.textContent = "Extracting…";
  const form = new FormData(); files.forEach(x => form.append("files", x.file));
  form.append("need_by_date", $("needBy").value); form.append("gr_date", $("grDate").value);
  form.append("file_contexts", JSON.stringify(Object.fromEntries(files.map(x => [x.file.name,{po_number:x.po}]))));
  try {
    const response = await fetch("/extract", {method:"POST", body:form});
    if (!response.ok) throw new Error(`Extraction failed (${response.status})`);
    const data = await response.json(); rows = data.rows; renderTable();
  } catch (error) { showToast(error.message); }
  finally { button.disabled = files.length === 0; button.textContent = "Extract rows"; }
});

function renderTable() {
  const table = $("dataTable"), head = document.createElement("thead"), body = document.createElement("tbody"), trh = document.createElement("tr");
  ["source_file",...COLUMNS,"notes"].forEach(key => { const th=document.createElement("th"); th.textContent=key === "source_file" ? "Source file" : key === "notes" ? "Review notes" : LABELS[key]; trh.append(th); });
  head.append(trh);
  rows.forEach((row,rowIndex) => {
    const tr=document.createElement("tr"); if(row.needs_review) tr.className="review-row"; tr.title=row.notes || "Review needed";
    const source=document.createElement("td"); source.textContent=row.source_file; tr.append(source);
    COLUMNS.forEach(key => { const td=document.createElement("td"); td.contentEditable="true"; td.textContent=row[key] ?? ""; td.dataset.column=key; td.dataset.row=rowIndex;
      if ((row.review_fields || []).includes(key)) td.classList.add("review-cell");
      td.addEventListener("input", () => rows[rowIndex][key]=td.innerText.replace(/\r?\n/g," ")); tr.append(td); });
    const notes=document.createElement("td"); notes.textContent=row.notes || ""; notes.className="notes-cell"; tr.append(notes);
    body.append(tr);
  });
  table.replaceChildren(head,body); $("summary").textContent=`${rows.length} row${rows.length===1?"":"s"} from ${files.length} file${files.length===1?"":"s"}`; $("results").hidden=false;
}
function tsv(withHeader) {
  const clean = value => String(value ?? "").replace(/[\t\r\n]+/g," ");
  const lines=rows.map(row => COLUMNS.map(key => clean(row[key])).join("\t"));
  if(withHeader) lines.unshift(COLUMNS.join("\t")); return lines.join("\n");
}
async function copy(withHeader) { try { await navigator.clipboard.writeText(tsv(withHeader)); showToast(withHeader?"Copied with header":"TSV copied"); } catch { showToast("Clipboard access was blocked"); } }
$("copyTsv").onclick=()=>copy(false); $("copyHeader").onclick=()=>copy(true);

// Native row selections include only the sheet columns, never source/review notes.
$("dataTable").addEventListener("copy", event => {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0) return;
  const range = selection.getRangeAt(0);
  const selectedCells = [...$("dataTable").querySelectorAll("th,td")].filter(cell => range.intersectsNode(cell));
  if (selectedCells.length < 2) return;
  const selectedRows = [...$("dataTable").tBodies[0].rows]
    .filter(tr => [...tr.cells].some(cell => range.intersectsNode(cell)))
    .map(tr => rows[tr.rowIndex - 1]);
  if (!selectedRows.length) return;
  const clean = value => String(value ?? "").replace(/[\t\r\n]+/g," ");
  const lines = selectedRows.map(row => COLUMNS.map(key => clean(row[key])).join("\t"));
  if (selectedCells.some(cell => cell.tagName === "TH")) lines.unshift(COLUMNS.join("\t"));
  event.clipboardData.setData("text/plain", lines.join("\n"));
  event.preventDefault();
});
function showToast(message) { const toast=$("toast"); toast.textContent=message; toast.classList.add("show"); setTimeout(()=>toast.classList.remove("show"),1800); }
