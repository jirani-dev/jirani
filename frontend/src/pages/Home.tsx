// src/pages/Home.tsx
import { useState, FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { BookOpen } from "lucide-react";
import * as authApi from "../services/api/auth";
import { LoginForm } from "../components/auth/LoginForm";

const Home = () => {
    const { login: loginToContext } = useAuth();
    const navigate = useNavigate();

    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [showPassword, setShowPassword] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");

    const handleLogin = async (e: FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        if (!username.trim() || !password.trim()) { setError("Please enter username and password."); return; }
        setLoading(true); setError(""); setNotice("");
        try {
            const data = await authApi.login(username.trim(), password);
            loginToContext(data);
            navigate("/library");
        } catch (e) {
            setError((e as Error).message || "Login failed.");
        } finally { setLoading(false); }
    };

    // The server is offline by design, so there is no e-mail recovery: staff
    // reset a forgotten password and hand over a temporary one.
    const handleForgotPassword = () => {
        setError("");
        setNotice("Ask a teacher or the administrator to reset your password. You will get a temporary one to sign in with.");
    };

    return (
        <div className="min-h-screen bg-[#FAFAF9] flex items-center justify-center font-sans p-6">
            <div className="w-full max-w-[420px]">

                <div className="text-center mb-10">
                    <div className="w-16 h-16 rounded-[18px] bg-[#F5EDD8] flex items-center justify-center mx-auto mb-4 shadow-[0_4px_16px_rgba(184,146,42,0.18)]">
                        <BookOpen size={28} color="#B8922A" />
                    </div>
                    <h1 className="text-[30px] font-bold text-[#1C1A17] mb-1.5 tracking-[-0.02em]">Offlib LLC</h1>
                </div>

                <div className="bg-white rounded-[20px] border border-[#E8E4DE] shadow-[0_4px_24px_rgba(28,26,23,0.07)] overflow-hidden">
                    <div className="px-7 py-7">
                        <p className="text-[10px] text-[#A09890] uppercase tracking-[0.1em] mb-5 font-semibold">Sign In</p>

                        <LoginForm
                            username={username}
                            password={password}
                            showPassword={showPassword}
                            loading={loading}
                            error={error}
                            notice={notice}
                            onUsernameChange={setUsername}
                            onPasswordChange={setPassword}
                            onToggleShowPassword={() => setShowPassword(p => !p)}
                            onSubmit={handleLogin}
                            onForgotPassword={handleForgotPassword}
                        />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Home;
