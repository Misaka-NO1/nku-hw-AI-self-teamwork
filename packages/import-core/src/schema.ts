import Ajv2020 from "ajv/dist/2020";
import type { ValidateFunction } from "ajv";
import coreSchema from "../../../contracts/core.schema.json";

/**
 * 使用与后端完全相同的 contracts/core.schema.json（draft 2020-12），
 * 不手写另一份字段定义。$id 是 example.invalid，不进行任何联网解析。
 */

let timetableValidator: ValidateFunction | null = null;

export function getTimetableValidator(): ValidateFunction {
  if (!timetableValidator) {
    const ajv = new Ajv2020({ allErrors: true, strict: false });
    timetableValidator = ajv.compile({
      $schema: "https://json-schema.org/draft/2020-12/schema",
      $ref: "#/$defs/TimetableImport",
      $defs: (coreSchema as { $defs: Record<string, unknown> }).$defs,
    });
  }
  return timetableValidator;
}

export interface SchemaViolation {
  field: string;
  code: string;
  message: string;
}

export function validateTimetableStructure(payload: unknown): SchemaViolation[] {
  const validate = getTimetableValidator();
  if (validate(payload)) {
    return [];
  }
  return (validate.errors ?? []).slice(0, 20).map((error) => ({
    field: error.instancePath || "$",
    code: error.keyword,
    message: error.message ?? "schema violation",
  }));
}
