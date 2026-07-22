import { describe, expect, it, vi } from "vitest";
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

  it("keeps quoted delimiters, escaped quotes, and multiline CSV values intact", async () => {
    const file = new File(
      [
        '"Contact ""preferred""; name";Company;Notes\r\n'
        + '"Ana ""Ace"" Popescu";"ACME; Europe";"First line\r\nSecond line"',
      ],
      "quoted-contacts.csv",
      { type: "text/csv" },
    );

    const spreadsheet = await readSpreadsheetFile(file);

    expect(spreadsheet.rows).toEqual([
      ['Contact "preferred"; name', "Company", "Notes"],
      ['Ana "Ace" Popescu', "ACME; Europe", "First line\r\nSecond line"],
    ]);
  });

  it("returns an empty dataset for an empty CSV read through the native File API", async () => {
    const file = {
      name: "empty.csv",
      text: vi.fn().mockResolvedValue(""),
    } as unknown as File;

    await expect(readSpreadsheetFile(file)).resolves.toEqual({
      sheetName: "CSV",
      sheetNames: ["CSV"],
      rows: [],
      cells: [],
    });
    expect(file.text).toHaveBeenCalledOnce();
  });

  it("rejects legacy and unrelated file formats", async () => {
    const file = new File(["legacy"], "contacts.xls", {
      type: "application/vnd.ms-excel",
    });

    await expect(readSpreadsheetFile(file)).rejects.toThrow("Format acceptat: CSV sau Excel .xlsx.");
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

  it("selects a requested worksheet and preserves typed Excel values and fill colors", async () => {
    const workbook = new ExcelJS.Workbook();
    workbook.addWorksheet("Ignored").getCell("A1").value = "Not selected";
    const worksheet = workbook.addWorksheet("Selected");
    worksheet.getCell("A1").value = new Date("2026-01-02T03:04:05.000Z");
    worksheet.getCell("A1").fill = {
      type: "pattern",
      pattern: "solid",
      fgColor: { argb: "FF00AA11" },
    };
    worksheet.getCell("B1").value = {
      richText: [{ text: "Ana" }, { text: " Popescu" }],
    };
    worksheet.getCell("C1").value = {
      text: "Profil",
      hyperlink: "https://codrut.example/profile",
    };
    worksheet.getCell("D1").value = { formula: "1+1", result: 2 };

    const buffer = await workbook.xlsx.writeBuffer();
    const file = {
      name: "typed.xlsx",
      arrayBuffer: vi.fn().mockResolvedValue(buffer),
    } as unknown as File;
    const selectSheet = vi.fn().mockReturnValue("Selected");

    const spreadsheet = await readSpreadsheetFile(file, selectSheet);

    expect(selectSheet).toHaveBeenCalledWith(["Ignored", "Selected"]);
    expect(file.arrayBuffer).toHaveBeenCalledOnce();
    expect(spreadsheet.sheetName).toBe("Selected");
    expect(spreadsheet.rows).toEqual([[
      "2026-01-02T03:04:05.000Z",
      "Ana Popescu",
      "Profil",
      "2",
    ]]);
    expect(spreadsheet.cells[0][0]).toEqual({
      text: "2026-01-02T03:04:05.000Z",
      rgb: "00AA11",
    });
  });

  it("returns workbook metadata when the selected worksheet does not exist", async () => {
    const workbook = new ExcelJS.Workbook();
    workbook.addWorksheet("Contacts").addRow(["Name", "Email"]);
    const buffer = await workbook.xlsx.writeBuffer();
    const file = new File(
      [buffer],
      "contacts.xlsx",
      { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" },
    );

    await expect(readSpreadsheetFile(file, () => "Missing")).resolves.toEqual({
      sheetName: null,
      sheetNames: ["Contacts"],
      rows: [],
      cells: [],
    });
  });

  it("fills blank headers and missing cells while dropping empty data rows", () => {
    expect(spreadsheetRowsToObjects([])).toEqual([]);
    expect(spreadsheetRowsToObjects([
      ["", "Email", "Role"],
      ["Ana", "ana@example.com"],
      ["", "", ""],
    ])).toEqual([
      {
        "Coloana 1": "Ana",
        Email: "ana@example.com",
        Role: "",
      },
    ]);
  });
});
