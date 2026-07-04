import type { Cell, CellValue, Worksheet } from "exceljs";

export type SpreadsheetCell = {
  text: string;
  rgb?: string;
};

export type SpreadsheetData = {
  sheetName: string | null;
  sheetNames: string[];
  rows: string[][];
  cells: SpreadsheetCell[][];
};

type SheetSelector = (sheetNames: string[]) => string | undefined;

function readFileWithReader(file: File, mode: "text"): Promise<string>;
function readFileWithReader(file: File, mode: "arrayBuffer"): Promise<ArrayBuffer>;
function readFileWithReader(file: File, mode: "text" | "arrayBuffer") {
  return new Promise<string | ArrayBuffer>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      if (mode === "text") {
        resolve(String(reader.result ?? ""));
      } else if (reader.result instanceof ArrayBuffer) {
        resolve(reader.result);
      } else {
        reject(new Error("Fișierul nu a putut fi citit ca ArrayBuffer."));
      }
    };
    reader.onerror = () => reject(reader.error ?? new Error("Fișierul nu a putut fi citit."));
    if (mode === "text") {
      reader.readAsText(file);
    } else {
      reader.readAsArrayBuffer(file);
    }
  });
}

async function readFileText(file: File): Promise<string> {
  if ("text" in file && typeof file.text === "function") {
    return file.text();
  }
  return readFileWithReader(file, "text");
}

async function readFileArrayBuffer(file: File): Promise<ArrayBuffer> {
  if ("arrayBuffer" in file && typeof file.arrayBuffer === "function") {
    return file.arrayBuffer();
  }
  return readFileWithReader(file, "arrayBuffer");
}

function countDelimiterOutsideQuotes(line: string, delimiter: string): number {
  let count = 0;
  let inQuotes = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const nextChar = line[index + 1];
    if (char === '"' && inQuotes && nextChar === '"') {
      index += 1;
      continue;
    }
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === delimiter && !inQuotes) {
      count += 1;
    }
  }
  return count;
}

function detectCsvDelimiter(text: string): string {
  const sampleLine = text.split(/\r?\n/).find((line) => line.trim().length > 0) ?? "";
  const candidates = [",", ";", "\t"];
  return candidates
    .map((delimiter) => ({
      delimiter,
      count: countDelimiterOutsideQuotes(sampleLine, delimiter),
    }))
    .sort((first, second) => second.count - first.count)[0]?.delimiter ?? ",";
}

function parseCsv(text: string): string[][] {
  const delimiter = detectCsvDelimiter(text);
  const rows: string[][] = [];
  let row: string[] = [];
  let value = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const nextChar = text[index + 1];

    if (char === '"' && inQuotes && nextChar === '"') {
      value += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }
    if (char === delimiter && !inQuotes) {
      row.push(value.trim());
      value = "";
      continue;
    }
    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && nextChar === "\n") {
        index += 1;
      }
      row.push(value.trim());
      rows.push(row);
      row = [];
      value = "";
      continue;
    }
    value += char;
  }

  if (value || row.length > 0) {
    row.push(value.trim());
    rows.push(row);
  }

  return rows.filter((candidate) => candidate.some((cell) => cell.length > 0));
}

function cellValueToText(value: CellValue): string {
  if (value == null) return "";
  if (value instanceof Date) return value.toISOString();
  if (typeof value !== "object") return String(value);
  if ("richText" in value && Array.isArray(value.richText)) {
    return value.richText.map((part) => part.text).join("");
  }
  if ("text" in value && typeof value.text === "string") {
    return value.text;
  }
  if ("result" in value) {
    return cellValueToText(value.result as CellValue);
  }
  return String(value);
}

function cellFillRgb(cell: Cell): string | undefined {
  const fill = cell.fill;
  if (!fill || fill.type !== "pattern") return undefined;
  return fill.fgColor?.argb?.replace(/^FF/i, "").toUpperCase();
}

function worksheetToData(worksheet: Worksheet): Pick<SpreadsheetData, "rows" | "cells"> {
  const rows: string[][] = [];
  const cells: SpreadsheetCell[][] = [];
  const rowCount = worksheet.rowCount;
  const columnCount = worksheet.columnCount;

  for (let rowIndex = 1; rowIndex <= rowCount; rowIndex += 1) {
    const worksheetRow = worksheet.getRow(rowIndex);
    const row: string[] = [];
    const cellRow: SpreadsheetCell[] = [];
    for (let columnIndex = 1; columnIndex <= columnCount; columnIndex += 1) {
      const cell = worksheetRow.getCell(columnIndex);
      const text = cellValueToText(cell.value).trim();
      row.push(text);
      cellRow.push({ text, rgb: cellFillRgb(cell) });
    }
    rows.push(row);
    cells.push(cellRow);
  }

  return trimSpreadsheetData(rows, cells);
}

function isBlankCell(cell: SpreadsheetCell | undefined): boolean {
  return !cell || cell.text.trim().length === 0;
}

function trimSpreadsheetData(
  rows: string[][],
  cells: SpreadsheetCell[][],
): Pick<SpreadsheetData, "rows" | "cells"> {
  let firstRow = 0;
  let lastRow = rows.length - 1;
  while (firstRow <= lastRow && rows[firstRow].every((cell) => cell.trim().length === 0)) {
    firstRow += 1;
  }
  while (lastRow >= firstRow && rows[lastRow].every((cell) => cell.trim().length === 0)) {
    lastRow -= 1;
  }
  if (firstRow > lastRow) {
    return { rows: [], cells: [] };
  }

  let firstColumn = 0;
  let lastColumn = Math.max(...rows.map((row) => row.length)) - 1;
  while (
    firstColumn <= lastColumn
    && rows.slice(firstRow, lastRow + 1).every((row) => (row[firstColumn] ?? "").trim() === "")
  ) {
    firstColumn += 1;
  }
  while (
    lastColumn >= firstColumn
    && rows.slice(firstRow, lastRow + 1).every((row) => (row[lastColumn] ?? "").trim() === "")
  ) {
    lastColumn -= 1;
  }

  const trimmedRows = rows
    .slice(firstRow, lastRow + 1)
    .map((row) => row.slice(firstColumn, lastColumn + 1));
  const trimmedCells = cells
    .slice(firstRow, lastRow + 1)
    .map((row, rowIndex) =>
      row.slice(firstColumn, lastColumn + 1).map((cell, columnIndex) => {
        if (!isBlankCell(cell)) return cell;
        return { text: trimmedRows[rowIndex]?.[columnIndex] ?? "" };
      }),
    );

  return { rows: trimmedRows, cells: trimmedCells };
}

export async function readSpreadsheetFile(
  file: File,
  selectSheet?: SheetSelector,
): Promise<SpreadsheetData> {
  const lowerName = file.name.toLowerCase();
  if (lowerName.endsWith(".csv")) {
    const rows = parseCsv(await readFileText(file));
    const data = trimSpreadsheetData(
      rows,
      rows.map((row) => row.map((text) => ({ text }))),
    );
    return {
      sheetName: "CSV",
      sheetNames: ["CSV"],
      rows: data.rows,
      cells: data.cells,
    };
  }
  if (!lowerName.endsWith(".xlsx")) {
    throw new Error("Format acceptat: CSV sau Excel .xlsx.");
  }

  const ExcelJS = await import("exceljs");
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(await readFileArrayBuffer(file));
  const sheetNames = workbook.worksheets.map((sheet) => sheet.name);
  const selectedName = selectSheet?.(sheetNames) ?? sheetNames[0];
  const worksheet = selectedName ? workbook.getWorksheet(selectedName) : workbook.worksheets[0];
  if (!worksheet) {
    return { sheetName: null, sheetNames, rows: [], cells: [] };
  }

  return {
    sheetName: worksheet.name,
    sheetNames,
    ...worksheetToData(worksheet),
  };
}

export function spreadsheetRowsToObjects(rows: string[][]): Record<string, unknown>[] {
  const [headerRow, ...dataRows] = rows;
  if (!headerRow) return [];
  const headers = headerRow.map((header, index) => header || `Coloana ${index + 1}`);
  return dataRows
    .map((row) =>
      Object.fromEntries(
        headers.map((header, index) => [header, row[index] ?? ""]),
      ),
    )
    .filter((row) => Object.values(row).some((value) => String(value).trim().length > 0));
}
