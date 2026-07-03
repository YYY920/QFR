import * as XLSX from 'xlsx'

export type ExportCell = string | number | boolean | null | undefined
export type ExportRow = Record<string, ExportCell>

function safeSheetName(name: string): string {
  return name.replace(/[:\\/?*\[\]]/g, ' ').slice(0, 31) || 'Sheet1'
}

function cleanRows(rows: ExportRow[]): Record<string, string | number | boolean | null>[] {
  return rows.map((row) => {
    const cleaned: Record<string, string | number | boolean | null> = {}
    Object.entries(row).forEach(([key, value]) => {
      cleaned[key] = value ?? null
    })
    return cleaned
  })
}

export function exportRowsToExcel(rows: ExportRow[], filename: string, sheetName = 'Export') {
  const exportRows = rows.length > 0 ? rows : [{ Message: 'No rows to export' }]
  const worksheet = XLSX.utils.json_to_sheet(cleanRows(exportRows))
  const workbook = XLSX.utils.book_new()
  XLSX.utils.book_append_sheet(workbook, worksheet, safeSheetName(sheetName))
  XLSX.writeFile(workbook, filename.endsWith('.xlsx') ? filename : `${filename}.xlsx`)
}
