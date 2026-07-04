import { describe, expect, it } from "vitest";
import ExcelJS from "exceljs";

import { readSpreadsheetFile, spreadsheetRowsToObjects } from "./spreadsheet-import";

describe("spreadsheet import", () => {
  it("reads semicolon-delimited CSV exports", async () => {
    const file = new File(
      ["Prenume;Nume de familie;Email\nAna;Popescu;ana@example.com\n"],
      "contacts.csv",
      { type: "text/csv" },
    );

    const spreadsheet = await readSpreadsheetFile(file);
    const rows = spreadsheetRowsToObjects(spreadsheet.rows);

    expect(rows).toEqual([
      {
        Prenume: "Ana",
        "Nume de familie": "Popescu",
        Email: "ana@example.com",
      },
    ]);
  });

  it("trims padded blank rows and columns from xlsx files", async () => {
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet("Revised");
    worksheet.getCell("C3").value = "Nume";
    worksheet.getCell("D3").value = "Email";
    worksheet.getCell("C4").value = "Ana Popescu";
    worksheet.getCell("D4").value = "ana@example.com";

    const buffer = await workbook.xlsx.writeBuffer();
    const file = new File(
      [buffer],
      "contacts.xlsx",
      { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
    );

    const spreadsheet = await readSpreadsheetFile(file);
    const rows = spreadsheetRowsToObjects(spreadsheet.rows);

    expect(spreadsheet.rows[0]).toEqual(["Nume", "Email"]);
    expect(rows).toEqual([
      {
        Nume: "Ana Popescu",
        Email: "ana@example.com",
      },
    ]);
  });
});
