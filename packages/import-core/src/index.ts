export { ADAPTERS, getAdapter, recognizePage } from "./adapters";
export type { AdapterDescriptor, AdapterStatus, Recognition } from "./adapters";
export { actualDateFor, getEffectiveTemplate, shanghaiIsoNow } from "./calendar";
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
