"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken } from "@/lib/api";
import { useAuthStore } from "@/lib/store";

interface Simulation {
  id: string;
  market: string;
  symbol: string;
  num_rounds: number;
  starting_capital: number;
  fee_bps: number;
  slippage_bps: number;
  session_filter: string | null;
  created_at: string;
}

export default function DashboardPage() {
  const router = useRouter();
  const { token, user, setAuth, logout } = useAuthStore();
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const t = getToken();
    if (!t) {
      router.push("/");
      return;
    }
    const loadData = async () => {
      try {
        if (!user) {
          const u = await api.me();
          setAuth(t, u);
        }
        const sims = await api.listSimulations();
        setSimulations(sims);
      } catch {
        logout();
        router.push("/");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const handleLogout = () => {
    logout();
    router.push("/");
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <div className="flex items-center gap-4">
          <span className="text-gray-400 text-sm">{user?.email}</span>
          <button
            onClick={handleLogout}
            className="text-gray-400 hover:text-white text-sm"
          >
            Logout
          </button>
        </div>
      </div>

      <button
        onClick={() => router.push("/simulation/create")}
        className="bg-blue-600 hover:bg-blue-500 text-white px-6 py-3 rounded-lg font-bold"
      >
        + Create Simulation
      </button>

      {simulations.length === 0 ? (
        <div className="bg-gray-800 rounded-xl p-8 text-center">
          <p className="text-gray-400">No simulations yet. Create your first one!</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {simulations.map((sim) => (
            <div
              key={sim.id}
              onClick={() => router.push(`/simulation/${sim.id}`)}
              className="bg-gray-800 rounded-xl p-4 cursor-pointer hover:bg-gray-750 transition border border-gray-700 hover:border-gray-600"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h3 className="font-bold text-lg">
                    {sim.symbol} ({sim.market})
                  </h3>
                  <p className="text-gray-400 text-sm">
                    {sim.num_rounds} rounds | ${sim.starting_capital.toLocaleString()} capital
                    | {sim.fee_bps}bps fee | {sim.slippage_bps}bps slippage
                  </p>
                  {sim.session_filter && (
                    <span className="text-xs bg-purple-600/30 text-purple-300 px-2 py-0.5 rounded mt-1 inline-block">
                      {sim.session_filter}
                    </span>
                  )}
                </div>
                <span className="text-gray-500 text-sm">
                  {new Date(sim.created_at).toLocaleDateString()}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
