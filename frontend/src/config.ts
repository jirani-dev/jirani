const value = import.meta.env.VITE_API_BASE;
if (!value) {
    throw new Error(
        "VITE_API_BASE is not set. The SPA must be served behind the same-origin proxy (/api/*) — see docs/superpowers/specs/react-kickoff-annex.md §Topology."
    );
}
const API_BASE: string = value;

export default API_BASE;
