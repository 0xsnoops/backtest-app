"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

export default function LandingPage() {
  const router = useRouter();
  const { setAuth, token } = useAuthStore();
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (token) {
    router.push("/dashboard");
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (!isLogin) {
        await api.register(email, password);
      }
      const data = await api.login(email, password);
      const user = await api.me();
      setAuth(data.access_token, user);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-400 to-purple-500 bg-clip-text text-transparent">
            Market Replay Backtester
          </h1>
          <p className="mt-3 text-gray-400">
            Practice trading with historical market replay. No hindsight bias.
          </p>
        </div>

        <div className="bg-gray-800 rounded-xl p-6 space-y-4">
          <div className="flex gap-2 mb-4">
            <button
              onClick={() => setIsLogin(true)}
              className={`flex-1 py-2 rounded text-sm font-bold ${
                isLogin ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-400"
              }`}
            >
              Login
            </button>
            <button
              onClick={() => setIsLogin(false)}
              className={`flex-1 py-2 rounded text-sm font-bold ${
                !isLogin ? "bg-blue-600 text-white" : "bg-gray-700 text-gray-400"
              }`}
            >
              Register
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-gray-900 border border-gray-600 rounded px-4 py-2 text-white"
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={6}
              className="w-full bg-gray-900 border border-gray-600 rounded px-4 py-2 text-white"
            />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded font-bold disabled:opacity-50"
            >
              {loading ? "..." : isLogin ? "Login" : "Register"}
            </button>
          </form>
        </div>

        <div className="grid grid-cols-3 gap-4 text-center text-sm">
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl mb-1">&#x1F4CA;</div>
            <p className="text-gray-400">Realistic candle replay</p>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl mb-1">&#x1F3AF;</div>
            <p className="text-gray-400">Hidden dates, no bias</p>
          </div>
          <div className="bg-gray-800/50 rounded-lg p-3">
            <div className="text-2xl mb-1">&#x1F4B0;</div>
            <p className="text-gray-400">Track PnL & metrics</p>
          </div>
        </div>
      </div>
    </div>
  );
}
