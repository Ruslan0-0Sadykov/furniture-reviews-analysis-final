import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.cwd();
const qaDir = path.join(root, "outputs", "qa");
await fs.mkdir(qaDir, { recursive: true });
const font = "Arial";

function polishSheet(sheet, titleRows = 1) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(titleRows);
  const used = sheet.getUsedRange();
  if (!used) return;
  used.format.font = { name: font, size: 10, color: "#1F2937" };
  used.format.verticalAlignment = "center";
  const header = used.getRow(0);
  header.format = { fill: "#1F4E78", font: { name: font, size: 10, bold: true, color: "#FFFFFF" }, verticalAlignment: "center", horizontalAlignment: "center", wrapText: true };
  header.format.rowHeight = 30;
  used.format.autofitColumns();
  used.format.autofitRows();
}

async function verifyAndSave(workbook, filePath, previewPrefix) {
  workbook.recalculate();
  const sheets = workbook.worksheets.items;
  for (const sheet of sheets) {
    const preview = await workbook.render({ sheetName: sheet.name, autoCrop: "all", scale: 1.2, format: "png" });
    await fs.writeFile(path.join(qaDir, `${previewPrefix}-${sheet.name.replace(/[^a-zA-Z0-9_-]/g,"_")}.png`), new Uint8Array(await preview.arrayBuffer()));
  }
  const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "final formula error scan" });
  console.log(errors.ndjson);
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(filePath);
}

async function buildAudit() {
  const audit = JSON.parse(await fs.readFile(path.join(root,"outputs","metrics","data_audit.json"),"utf8"));
  const wb = Workbook.create();
  const summary = wb.worksheets.add("Сводка");
  summary.getRange("A1:B8").values = [
    ["Показатель","Значение"],
    ["Исходных файлов",audit.raw.combined.files],
    ["Строк до очистки",audit.preprocessing.rows_loaded],
    ["Удалено технических строк",audit.preprocessing.blank_or_nonreview_rows_removed],
    ["Удалено точных дублей",audit.preprocessing.exact_duplicates_removed],
    ["Строк после очистки",audit.preprocessing.rows_processed],
    ["Отзывы с текстом",audit.preprocessing.text_nonempty],
    ["Отзывы с рейтингом",audit.preprocessing.rating_nonmissing],
  ];
  polishSheet(summary);
  summary.getRange("A:A").format.columnWidth = 34; summary.getRange("B:B").format.columnWidth = 18;
  const fields = wb.worksheets.add("Поля");
  const rows=[["Файл","Поле","Тип","Пропуски","Доля пропусков","Уникальные"]];
  for (const file of audit.raw.files) for (const f of file.fields) rows.push([file.file,f.column,f.dtype,f.missing,f.missing_share,f.unique]);
  fields.getRange("A1").write(rows); polishSheet(fields); fields.getRange(`E2:E${rows.length}`).format.numberFormat="0.0%"; fields.freezePanes.freezeRows(1);
  fields.getRange("A:A").format.columnWidth=24; fields.getRange("B:B").format.columnWidth=26;
  console.log((await wb.inspect({kind:"table",range:"Сводка!A1:B8",include:"values,formulas",tableMaxRows:10,tableMaxCols:4})).ndjson);
  await verifyAndSave(wb,path.join(root,"outputs","tables","data_audit.xlsx"),"data-audit");
}

async function buildCsvWorkbook(csvPath, sheetName, outputPath, prefix, widths={}) {
  const csv=await fs.readFile(csvPath,"utf8"); const wb=await Workbook.fromCSV(csv,{sheetName}); const sheet=wb.worksheets.getItem(sheetName); polishSheet(sheet);
  for (const [col,width] of Object.entries(widths)) sheet.getRange(`${col}:${col}`).format.columnWidth=width;
  console.log((await wb.inspect({kind:"table",range:`${sheetName}!A1:F6`,include:"values,formulas",tableMaxRows:6,tableMaxCols:6})).ndjson);
  await verifyAndSave(wb,outputPath,prefix);
}

await buildAudit();
await buildCsvWorkbook(path.join(root,"outputs","tables","classification_audit.csv"),"Аудит классификации",path.join(root,"outputs","tables","classification_audit.xlsx"),"classification-audit",{A:20,B:70,C:12,D:10,E:14,F:28});
await buildCsvWorkbook(path.join(root,"datalens","data_dictionary.csv"),"Словарь данных",path.join(root,"datalens","data_dictionary.xlsx"),"data-dictionary",{A:28,B:16,C:60,D:12});

