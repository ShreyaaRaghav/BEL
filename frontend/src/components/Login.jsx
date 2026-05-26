import { useState } from "react";
import { login } from "../auth";

export default function Login({ onLogin }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(username, password);
      onLogin(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={S.page}>
      <div style={S.card}>
        <div style={S.header}>
          <div style={S.logo}>⚡</div>
          <div style={S.title}>BHARAT ELECTRONICS</div>
          <div style={S.subtitle}>Secure Checksheet Processing Portal</div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={S.formGroup}>
            <label style={S.label}>Employee ID / Username</label>
            <input 
              style={S.input} 
              type="text" 
              value={username} 
              autoFocus 
              required
              placeholder="e.g. bel_engineer"
              onChange={e => setUsername(e.target.value)} 
              autoComplete="username" 
            />
          </div>

          <div style={S.formGroup}>
            <label style={S.label}>Portal Password</label>
            <input 
              style={S.input} 
              type="password" 
              value={password} 
              required
              placeholder="••••••••••••"
              onChange={e => setPassword(e.target.value)} 
              autoComplete="current-password" 
            />
          </div>

          {error && <div style={S.error}>⚠️ {error}</div>}

          <button style={S.button} type="submit" disabled={loading}>
            {loading ? (
              <span style={S.btnContent}>
                <span style={S.spinner}></span> Signing in...
              </span>
            ) : "Access System"}
          </button>
        </form>

        <p style={S.notice}>
          Authorised BEL personal access only. All system events, access logs, and inspection reviews are subject to active cryptographic auditing.
        </p>
      </div>
    </div>
  );
}

const S = {
  page: {
    minHeight: "100vh",
    width: "100vw",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "linear-gradient(135deg, hsl(230, 25%, 8%), hsl(235, 30%, 4%))",
    fontFamily: "'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
    margin: 0,
    padding: 0,
    position: "absolute",
    top: 0,
    left: 0,
    overflow: "hidden"
  },
  card: {
    background: "hsla(228, 20%, 14%, 0.6)",
    backdropFilter: "blur(20px)",
    WebkitBackdropFilter: "blur(20px)",
    border: "1px solid hsla(228, 15%, 25%, 0.4)",
    borderRadius: 24,
    padding: "48px 40px",
    width: 400,
    boxShadow: "0 25px 50px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05)"
  },
  header: {
    textAlign: "center",
    marginBottom: 32
  },
  logo: {
    fontSize: 48,
    marginBottom: 12,
    background: "linear-gradient(135deg, hsl(265, 85%, 65%), hsl(190, 90%, 55%))",
    WebkitBackgroundClip: "text",
    WebkitTextFillColor: "transparent",
    display: "inline-block",
    animation: "float 3s ease-in-out infinite"
  },
  title: {
    fontSize: 18,
    fontWeight: 700,
    letterSpacing: "1.5px",
    color: "hsl(220, 40%, 96%)",
    marginBottom: 4
  },
  subtitle: {
    fontSize: 13,
    color: "hsl(220, 16%, 70%)",
    fontWeight: 400
  },
  formGroup: {
    marginBottom: 20
  },
  label: {
    display: "block",
    fontSize: 12,
    fontWeight: 600,
    color: "hsl(220, 16%, 70%)",
    marginBottom: 8,
    textTransform: "uppercase",
    letterSpacing: "0.5px"
  },
  input: {
    width: "100%",
    padding: "12px 16px",
    background: "hsla(228, 20%, 10%, 0.7)",
    border: "1.5px solid hsla(228, 15%, 25%, 0.4)",
    borderRadius: 12,
    color: "hsl(220, 40%, 96%)",
    fontSize: 15,
    boxSizing: "border-box",
    outline: "none",
    transition: "all 0.3s ease"
  },
  error: {
    marginTop: 16,
    padding: "12px 16px",
    background: "rgba(244, 63, 94, 0.15)",
    color: "rgb(251, 113, 133)",
    border: "1px solid rgb(244, 63, 94)",
    borderRadius: 12,
    fontSize: 13.5,
    fontWeight: 500
  },
  button: {
    width: "100%",
    marginTop: 24,
    padding: 14,
    background: "linear-gradient(135deg, hsl(265, 85%, 65%), hsl(265, 80%, 55%))",
    color: "#fff",
    border: "none",
    borderRadius: 12,
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
    boxShadow: "0 4px 15px hsla(265, 85%, 65%, 0.25)",
    transition: "all 0.3s ease"
  },
  btnContent: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 8
  },
  spinner: {
    width: 18,
    height: 18,
    border: "2px solid rgba(255, 255, 255, 0.3)",
    borderRadius: "50%",
    borderTopColor: "white",
    animation: "spin 0.8s linear infinite"
  },
  notice: {
    marginTop: 28,
    fontSize: 11,
    color: "hsl(220, 10%, 50%)",
    textAlign: "center",
    lineHeight: 1.6
  }
};
