// src/types.ts
// Every shape here is taken from the generated API schema, so a field the
// backend renames or removes stops compiling instead of failing at runtime.
// List responses and fixtures often carry only part of a record, which is why
// the entity types name the fields the UI needs rather than the whole schema.
import type { components } from './api/generated/schema';

type Schemas = components['schemas'];

// The fields in `Required` exactly as the schema has them, plus the fields in
// `Optional` made optional.
type View<T, Required extends keyof T, Optional extends keyof T> =
    Pick<T, Required> & Partial<Pick<T, Optional>>;

export type Tag = Schemas['TagRead'];

// BookRead serialises author / level / genre under their alias names:
// author_name / level_name / genre_name.
export type Book = View<
    Schemas['BookRead'],
    'uid' | 'title' | 'extension',
    'cover_url' | 'author_name' | 'level_name' | 'genre_name' | 'language' | 'tags'
>;

// poster_url is a still frame extracted at upload; null when the server has
// no ffmpeg.
export type Video = View<Schemas['VideoRead'], 'id' | 'title', 'description' | 'poster_url' | 'tags'>;

export type Audio = View<Schemas['AudioRead'], 'id' | 'title', 'description' | 'audio_url' | 'tags'>;

export interface Page<T> {
    items: T[];
    total: number;
    limit: number;
    offset: number;
}

export type Role = Schemas['RoleEnum'];

export type LoginResponse = Schemas['TokenResponse'];
