import { FormEvent, useId, useState } from 'react';
import { KeyRound, Loader2 } from 'lucide-react';
import * as authApi from '../../services/api/auth';
import { Role } from '../../types';

const inputStyle =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-[13px] text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";
const labelStyle = "text-xs text-[#6B6560] block mb-1.5 font-sans";

// Mirrors AuthService.validate_credentials; the server remains the authority.
const minLengthFor = (role: Role): number => (role === 'student' ? 4 : 8);

interface ChangePasswordModalProps {
    role: Role;
    onChanged: () => void;
    onSignOut: () => void;
}

// Shown over the library until an account that still has its temporary
// password has chosen its own. It cannot be dismissed, only completed or
// left by signing out.
export const ChangePasswordModal = ({ role, onChanged, onSignOut }: ChangePasswordModalProps) => {
    const [current, setCurrent] = useState('');
    const [next, setNext] = useState('');
    const [confirm, setConfirm] = useState('');
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState('');
    const currentId = useId();
    const nextId = useId();
    const confirmId = useId();
    const minLength = minLengthFor(role);

    const submit = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (next.length < minLength) { setError(`The new password needs at least ${minLength} characters.`); return; }
        if (next !== confirm) { setError('The two new passwords do not match.'); return; }
        if (next === current) { setError('Choose a password different from the temporary one.'); return; }
        setSaving(true); setError('');
        try {
            await authApi.changePassword(current, next);
            onChanged();
        } catch (err) {
            setError((err as Error).message || 'Failed to change password.');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div role="dialog" aria-modal="true" aria-labelledby={`${currentId}-title`}
            className="fixed inset-0 z-50 flex items-center justify-center bg-[#1C1A17]/40 backdrop-blur-sm">
            <form onSubmit={submit} className="bg-white rounded-[20px] w-full max-w-[420px] mx-4 shadow-[0_32px_80px_rgba(28,26,23,0.18)] p-6 flex flex-col gap-3.5">
                <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-[9px] bg-[#F5EDD8] flex items-center justify-center">
                        <KeyRound size={14} color="#B8922A" />
                    </div>
                    <span id={`${currentId}-title`} className="text-[19px] font-bold text-[#1C1A17]">Choose your password</span>
                </div>
                <p className="text-[13px] text-[#6B6560] m-0 leading-relaxed">
                    You signed in with a temporary password. Replace it with one only you know before using the library.
                </p>
                <div>
                    <label htmlFor={currentId} className={labelStyle}>Temporary password</label>
                    <input id={currentId} type="password" autoComplete="current-password" value={current}
                        onChange={e => setCurrent(e.target.value)} className={inputStyle} />
                </div>
                <div>
                    <label htmlFor={nextId} className={labelStyle}>New password (at least {minLength} characters)</label>
                    <input id={nextId} type="password" autoComplete="new-password" value={next}
                        onChange={e => setNext(e.target.value)} className={inputStyle} />
                </div>
                <div>
                    <label htmlFor={confirmId} className={labelStyle}>New password again</label>
                    <input id={confirmId} type="password" autoComplete="new-password" value={confirm}
                        onChange={e => setConfirm(e.target.value)} className={inputStyle} />
                </div>
                {error && <p role="alert" className="m-0 text-xs text-[#A09890] text-center">{error}</p>}
                <button type="submit" disabled={saving || !current || !next || !confirm}
                    className={`py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 ${saving || !current || !next || !confirm ? "bg-[#E8E4DE] text-[#A09890] cursor-not-allowed" : "bg-[#B8922A] text-white cursor-pointer"}`}>
                    {saving ? <><Loader2 size={14} className="animate-spin" /> Saving...</> : "Save password"}
                </button>
                <button type="button" onClick={onSignOut}
                    className="bg-transparent border-none text-[#A09890] text-xs cursor-pointer text-center">
                    Sign out instead
                </button>
            </form>
        </div>
    );
};
