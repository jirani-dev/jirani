// src/types.ts
export interface Tag {
    id: number | string;
    name: string;
}

export interface Book {
    uid: string;
    title: string;
    extension: string;
    cover_url?: string | null;
    // BookRead serialises these three under its alias names: the JSON keys
    // are author_name / level_name / genre_name, not author / level / genre.
    author_name?: string | null;
    level_name?: string | null;
    genre_name?: string | null;
    language?: string | null;
    tags?: Tag[];
}

export interface Video {
    id: number | string;
    title: string;
    description?: string | null;
    // Still frame extracted at upload; null when the server has no ffmpeg.
    poster_url?: string | null;
    tags?: Tag[];
}

export interface Audio {
    id: number | string;
    title: string;
    description?: string | null;
    audio_url?: string;
    tags?: Tag[];
}

export interface Page<T> {
    items: T[];
    total: number;
    limit: number;
    offset: number;
}

export type Role = "admin" | "teacher" | "student";

export interface LoginResponse {
    access_token: string;
    token_type: string;
    username: string;
    role: Role;
    first_login: boolean;
}
