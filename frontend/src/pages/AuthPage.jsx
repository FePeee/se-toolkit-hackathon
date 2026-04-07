import { useState } from "react";
import { api } from "../api/client";

export default function AuthPage({ onLogin }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      let data;
      if (mode === "login") {
        data = await api.login(email, password);
      } else {
        data = await api.register(email, password, name);
      }
      localStorage.setItem("token", data.access_token);
      onLogin(data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center", background: "#f5f5f0" }}>
      <div style={{ background: "#fff", border: "0.5px solid #e0ddd4", borderRadius: 16, padding: "40px 36px", width: "100%", maxWidth: 400 }}>
        <h1 style={{ fontSize: 22, fontWeight: 500, marginBottom: 6 }}>Habit Tracker</h1>
        <p style={{ color: "#888", fontSize: 14, marginBottom: 28 }}>
          {mode === "login" ? "Sign in to your account" : "Create a new account"}
        </p>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {mode === "register" && (
            <input
              placeholder="Your name"
              value={name}
              onChange={e => setName(e.target.value)}
              required
              style={{ padding: "10px 14px", borderRadius: 8, border: "0.5px solid #ccc", fontSize: 14 }}
            />
          )}
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            style={{ padding: "10px 14px", borderRadius: 8, border: "0.5px solid #ccc", fontSize: 14 }}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            style={{ padding: "10px 14px", borderRadius: 8, border: "0.5px solid #ccc", fontSize: 14 }}
          />

          {error && <p style={{ color: "#c0392b", fontSize: 13 }}>{error}</p>}

          <button
            type="submit"
            disabled={loading}
            style={{ marginTop: 4, padding: "11px", borderRadius: 8, border: "none", background: "#1D9E75", color: "#fff", fontSize: 14, fontWeight: 500, cursor: "pointer" }}
          >
            {loading ? "Loading..." : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p style={{ marginTop: 20, textAlign: "center", fontSize: 13, color: "#888" }}>
          {mode === "login" ? "No account? " : "Already have one? "}
          <span
            onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}
            style={{ color: "#1D9E75", cursor: "pointer", fontWeight: 500 }}
          >
            {mode === "login" ? "Register" : "Sign in"}
          </span>
        </p>
      </div>
    </div>
  );
}
