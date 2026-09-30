// Structural types retained with the viewer, independent of schema generation.
export type DataType = "Boolean" | "String" | "DateTime" | "Enum" | "Integer" | "Real" | "Reference" | "Object" | "Array";
export type ImportNode = {uri: string};
export type IfcxValueDescription = {
    dataType: DataType;
    optional?: boolean;
    inherits?: string[];
    quantityKind?: string;
    enumRestrictions?: {options: string[]};
    objectRestrictions?: {values: Record<string, IfcxValueDescription>};
    arrayRestrictions?: {value: IfcxValueDescription};
};
export type IfcxSchema = {value: IfcxValueDescription};
export type IfcxNode = {
    path: string;
    children?: Record<string, string | null>;
    inherits?: Record<string, string | null>;
    attributes?: Record<string, any>;
};
export type IfcxFile = {
    header: {id: string; ifcxVersion: string; dataVersion: string; author: string; timestamp?: string};
    imports: ImportNode[];
    schemas: Record<string, IfcxSchema>;
    data: IfcxNode[];
};


