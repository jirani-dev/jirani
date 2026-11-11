// src/types.ts
// Shapes come from the generated OpenAPI schema (src/api/generated).
// Do not hand-write API shapes here; add short aliases only.
import type { components } from './api/generated/schema';

type Schemas = components['schemas'];

export type Tag = Schemas['TagRead'];
export type Book = Schemas['BookRead'];
export type Video = Schemas['VideoRead'];
export type Audio = Schemas['AudioRead'];
export type LoginResponse = Schemas['TokenResponse'];
export type Role = Schemas['RoleEnum'];

export interface Page<T> {
    items: T[];
    total: number;
    limit: number;
    offset: number;
}