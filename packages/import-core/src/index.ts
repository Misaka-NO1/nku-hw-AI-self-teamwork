export { ADAPTERS, getAdapter, recognizePage } from "./adapters";
export type { AdapterDescriptor, AdapterStatus, Recognition } from "./adapters";
export { EAMIS_OBSERVATION_HEADERS, EAMIS_GRID_SELECTOR, eamisObservationToRawRows, extractEamisGridFromDoc, parseEamisCellEntries } from "./eamis";
export type { EamisCellEntry, EamisConvertResult } from "./eamis";
export { actualDateFor, getEffectiveTemplate, shanghaiIsoNow, validateTermCalendarStructure } from "./calendar";
export type { EffectiveTemplate } from "./calendar";
export {
  normalizeCourses,
  parsePeriodRange,
  parseWeekday,
} from "./normalize";
export type { NormalizeOptions, RawMeetingRow } from "./normalize";
export {
  extractHtmlTable,
  IMPORT_LIMITS,
  parseImportFile,
  parseObservation,
  REQUIRED_TABLE_HEADERS,
  tableToRawRows,
} from "./parse";
export type { ImportFileInput, ImportFormat } from "./parse";
export { getTimetableValidator, validateTimetableStructure } from "./schema";
export { parseWeeks } from "./weeks";
export type { WeeksParseResult } from "./weeks";
export * from "./types";
