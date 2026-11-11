import { FormEvent, useId } from 'react';
import { Loader2, Eye, EyeOff } from 'lucide-react';

const inputBase =
    "w-full px-3.5 py-2.5 border border-[#E8E4DE] rounded-[10px] text-sm text-[#1C1A17] bg-white outline-none box-border font-sans appearance-none [-webkit-text-fill-color:#1C1A17]";
const labelStyle = "text-xs text-[#6B6560] block mb-1.5 font-sans";

interface LoginFormProps {
    username: string;
    password: string;
    showPassword: boolean;
    loading: boolean;
    error: string;
    // Guidance that is not a failure, e.g. how to get a forgotten password reset.
    notice: string;
    onUsernameChange: (v: string) => void;
    onPasswordChange: (v: string) => void;
    onToggleShowPassword: () => void;
    onSubmit: (e: FormEvent<HTMLFormElement>) => void;
    onForgotPassword: () => void;
}

export const LoginForm = ({
    username, password, showPassword, loading, error, notice,
    onUsernameChange, onPasswordChange, onToggleShowPassword,
    onSubmit, onForgotPassword,
}: LoginFormProps) => {
    const usernameId = useId();
    const passwordId = useId();

    return (
        <form onSubmit={onSubmit} className="flex flex-col gap-3">
            <div>
                <label htmlFor={usernameId} className={labelStyle}>Username</label>
                <input
                    id={usernameId}
                    type="text"
                    value={username}
                    onChange={e => onUsernameChange(e.target.value)}
                    placeholder="Enter username..."
                    autoComplete="username"
                    className={inputBase}
                />
            </div>
            <div>
                <label htmlFor={passwordId} className={labelStyle}>Password</label>
                <div className="relative">
                    <input
                        id={passwordId}
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={e => onPasswordChange(e.target.value)}
                        placeholder="Enter password..."
                        autoComplete="current-password"
                        className={`${inputBase} pr-10`}
                    />
                    <button type="button" onClick={onToggleShowPassword}
                        aria-label={showPassword ? "Hide password" : "Show password"}
                        className="absolute right-3 top-1/2 -translate-y-1/2 bg-transparent border-none cursor-pointer text-[#A09890] p-0 flex">
                        {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                </div>
            </div>

            {error && <p role="alert" className="m-0 text-xs text-center text-[#A09890]">{error}</p>}
            {!error && notice && <p className="m-0 text-xs text-center text-[#B8922A]">{notice}</p>}

            <button type="submit" disabled={loading}
                className={`py-3.5 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 mt-1 ${loading ? "bg-[#E8E4DE] text-[#A09890] cursor-not-allowed" : "bg-[#B8922A] text-white cursor-pointer"}`}>
                {loading ? <><Loader2 size={14} className="animate-spin" /> Signing in...</> : "Sign In"}
            </button>

            <button type="button" onClick={onForgotPassword}
                className="bg-transparent border-none text-[#A09890] text-xs cursor-pointer text-center">
                Forgot password?
            </button>
        </form>
    );
};
