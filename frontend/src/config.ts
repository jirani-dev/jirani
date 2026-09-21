// Protected media (book/audio/video streaming) is served via nginx's
// X-Accel-Redirect, which only resolves when the request actually passes
// through nginx — hitting the backend on :8000 directly returns an empty
// 204. nginx is the documented entry point ("Run with Docker" in
// docs/team/operations.md), so that's the correct default; override with
// VITE_API_BASE only for the backend-container-less local dev flow.
const API_BASE: string = import.meta.env.VITE_API_BASE ?? "http://localhost/api";

export default API_BASE;
