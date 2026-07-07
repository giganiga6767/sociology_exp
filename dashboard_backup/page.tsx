"use client";

import React, { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  BarChart,
  Bar
} from "recharts";

// Define TypeScript interfaces matching FastAPI and Gemini schema
interface AgentEvaluation {
  agent_name: string;
  channel_name: string;
  regional_term_count: number;
  cosmopolitan_term_count: number;
  identified_regional_terms: string[];
  identified_cosmo_terms: string[];
}

interface AnalyticsPayload {
  evaluations: AgentEvaluation[];
}

interface HistoryDataPoint {
  time: string;
  globalSquareLAR: number;
  tier2FamilyLAR: number;
  cosmoFamilyLAR: number;
  cosmoSlangCount: number;
  regionalSlangCount: number;
}

export default function Dashboard() {
  const [data, setData] = useState<AnalyticsPayload | null>(null);
  const [history, setHistory] = useState<HistoryDataPoint[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [tick, setTick] = useState<number>(0);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/analytics");
        if (!res.ok) {
          throw new Error(`FastAPI server returned status: ${res.status}`);
        }
        const json: AnalyticsPayload = await res.json();
        setData(json);
        setError(null);

        // Calculate metrics for history (Fix 7: Per-channel LAR tracking)
        let gsReg = 0, gsCos = 0;
        let t2fReg = 0, t2fCos = 0;
        let cfReg = 0, cfCos = 0;
        let overallRegCount = 0;
        let overallCosCount = 0;

        json.evaluations.forEach((evalItem) => {
          const reg = evalItem.regional_term_count;
          const cos = evalItem.cosmopolitan_term_count;
          
          overallRegCount += reg;
          overallCosCount += cos;

          const isTier2 = evalItem.agent_name.includes(" T") || evalItem.agent_name.includes("Student T") || evalItem.agent_name.includes("Parent T");
          const isCosmo = evalItem.agent_name.includes(" C") || evalItem.agent_name.includes("Student C") || evalItem.agent_name.includes("Parent C");

          if (evalItem.channel_name === "Global_Square") {
            if (isTier2) {
              gsReg += reg;
              gsCos += cos;
            }
          } else if (evalItem.channel_name === "Tier2_Family") {
            if (isTier2) {
              t2fReg += reg;
              t2fCos += cos;
            }
          } else if (evalItem.channel_name === "Cosmopolitan_Family") {
            if (isCosmo) {
              cfReg += reg;
              cfCos += cos;
            }
          }
        });

        const gsRatio = (gsReg + gsCos) > 0 ? Math.round((gsCos / (gsReg + gsCos)) * 100) : 0;
        const t2fRatio = (t2fReg + t2fCos) > 0 ? Math.round((t2fCos / (t2fReg + t2fCos)) * 100) : 0;
        const cfRatio = (cfReg + cfCos) > 0 ? Math.round((cfReg / (cfReg + cfCos)) * 100) : 0;

        setHistory((prevHistory) => {
          const newPoint: HistoryDataPoint = {
            time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            globalSquareLAR: gsRatio,
            tier2FamilyLAR: t2fRatio,
            cosmoFamilyLAR: cfRatio,
            cosmoSlangCount: overallCosCount,
            regionalSlangCount: overallRegCount
          };
          // Cap history at last 15 points
          const sliced = prevHistory.length >= 15 ? prevHistory.slice(1) : prevHistory;
          return [...sliced, newPoint];
        });
      } catch (err: any) {
        console.error(err);
        setError("Could not connect to FastAPI backend at http://127.0.0.1:8000. Ensure server is running.");
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, 10000); // Poll every 10 seconds

    return () => clearInterval(interval);
  }, [tick]);

  // Totals calculations for display
  const totalReg = data?.evaluations.reduce((sum, item) => sum + item.regional_term_count, 0) || 0;
  const totalCos = data?.evaluations.reduce((sum, item) => sum + item.cosmopolitan_term_count, 0) || 0;
  const currentRatio = history.length > 0 ? history[history.length - 1].globalSquareLAR : 0;

  return (
    <div className="min-h-screen bg-[#0B0F19] text-gray-100 p-8 font-sans">
      {/* Glow decorations */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-cyan-500/10 rounded-full blur-3xl -z-10" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-violet-600/10 rounded-full blur-3xl -z-10" />

      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 border-b border-gray-800 pb-6 gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-cyan-400 to-violet-400 bg-clip-text text-transparent">
            Diglossia Simulation Control Centre
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Analyzing emergent code-switching and accommodation behavior of autonomous LLM cohorts.
          </p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={() => setTick(t => t + 1)}
            className="px-4 py-2 bg-gradient-to-r from-cyan-500 to-cyan-600 hover:from-cyan-600 hover:to-cyan-700 text-white rounded-lg font-medium shadow-lg shadow-cyan-500/20 transition duration-150 text-sm flex items-center gap-2"
          >
            🔄 Sync Live
          </button>
          <div className="px-3 py-2 bg-gray-900 border border-gray-800 rounded-lg flex items-center text-xs text-cyan-400 font-mono">
            ● POLLING ACTIVE (10S)
          </div>
        </div>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-950/40 border border-red-800/80 rounded-xl text-red-300 text-sm flex items-center gap-3 backdrop-blur-md">
          ⚠️ <span>{error}</span>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-[#111827]/60 border border-gray-800/80 p-6 rounded-2xl relative overflow-hidden backdrop-blur-md">
          <div className="absolute top-0 right-0 w-24 h-24 bg-cyan-500/5 rounded-full blur-2xl" />
          <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-wider">Accommodation Ratio (T2)</h2>
          <div className="text-4xl font-black text-cyan-400 mt-2">{currentRatio}%</div>
          <p className="text-gray-500 text-xs mt-2">Percentage of Cosmopolitan terms adopted by Tier-2 agents</p>
        </div>

        <div className="bg-[#111827]/60 border border-gray-800/80 p-6 rounded-2xl relative overflow-hidden backdrop-blur-md">
          <div className="absolute top-0 right-0 w-24 h-24 bg-violet-500/5 rounded-full blur-2xl" />
          <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-wider">Cosmopolitan Slang Count</h2>
          <div className="text-4xl font-black text-violet-400 mt-2">{totalCos}</div>
          <p className="text-gray-500 text-xs mt-2">Total occurrences of tech/Gen-Z terms across all channels</p>
        </div>

        <div className="bg-[#111827]/60 border border-gray-800/80 p-6 rounded-2xl relative overflow-hidden backdrop-blur-md">
          <div className="absolute top-0 right-0 w-24 h-24 bg-emerald-500/5 rounded-full blur-2xl" />
          <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-wider">Tier-2 Regional Count</h2>
          <div className="text-4xl font-black text-emerald-400 mt-2">{totalReg}</div>
          <p className="text-gray-500 text-xs mt-2">Total occurrences of traditional honorifics and regional terms</p>
        </div>

        <div className="bg-[#111827]/60 border border-gray-800/80 p-6 rounded-2xl relative overflow-hidden backdrop-blur-md">
          <div className="absolute top-0 right-0 w-24 h-24 bg-yellow-500/5 rounded-full blur-2xl" />
          <h2 className="text-gray-400 text-xs font-semibold uppercase tracking-wider">Evaluated Conversations</h2>
          <div className="text-4xl font-black text-yellow-400 mt-2">
            {data?.evaluations.length || 0}
          </div>
          <p className="text-gray-500 text-xs mt-2">Active conversational pairs parsed by Gemini agent evaluator</p>
        </div>
      </div>

      {/* Main Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mb-8">
        {/* Accommodation Ratio Live Line Chart */}
        <div className="lg:col-span-2 bg-[#111827]/40 border border-gray-800/80 p-6 rounded-3xl backdrop-blur-md">
          <h3 className="text-base font-bold text-gray-200 mb-4 flex items-center gap-2">
            📈 Lexical Accommodation Timeline (Live)
          </h3>
          <div className="h-80 w-full">
            {loading && history.length === 0 ? (
              <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
                Awaiting first logs...
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={history} margin={{ top: 10, right: 10, left: -20, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                  <XAxis dataKey="time" stroke="#9CA3AF" fontSize={11} tickLine={false} />
                  <YAxis domain={[0, 100]} stroke="#9CA3AF" fontSize={11} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#111827", borderColor: "#374151", borderRadius: "12px", color: "#F9FAFB" }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px", color: "#9CA3AF" }} />
                  <Line
                    type="monotone"
                    name="Global Square LAR (Peer Square)"
                    dataKey="globalSquareLAR"
                    stroke="#22D3EE"
                    strokeWidth={3}
                    activeDot={{ r: 6 }}
                    dot={{ stroke: "#0E7490", strokeWidth: 2, r: 4 }}
                  />
                  <Line
                    type="monotone"
                    name="Tier-2 Family LAR (Home Dialect)"
                    dataKey="tier2FamilyLAR"
                    stroke="#34D399"
                    strokeWidth={2}
                    activeDot={{ r: 4 }}
                    dot={{ stroke: "#065F46", strokeWidth: 2, r: 3 }}
                  />
                  <Line
                    type="monotone"
                    name="Cosmopolitan Family LAR (Prestige Dialect)"
                    dataKey="cosmoFamilyLAR"
                    stroke="#A78BFA"
                    strokeWidth={2}
                    activeDot={{ r: 4 }}
                    dot={{ stroke: "#5B21B6", strokeWidth: 2, r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Bar Chart comparing regional vs cosmopolitan terms by channel */}
        <div className="bg-[#111827]/40 border border-gray-800/80 p-6 rounded-3xl backdrop-blur-md">
          <h3 className="text-base font-bold text-gray-200 mb-4">
            📊 Vocabulary Distribution by Group
          </h3>
          <div className="h-80 w-full">
            {loading && !data ? (
              <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
                No active records.
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[
                    { name: "Total Regional", Count: totalReg, fill: "#10B981" },
                    { name: "Total Cosmo", Count: totalCos, fill: "#8B5CF6" }
                  ]}
                  margin={{ top: 20, right: 10, left: -20, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#1F2937" />
                  <XAxis dataKey="name" stroke="#9CA3AF" fontSize={11} tickLine={false} />
                  <YAxis stroke="#9CA3AF" fontSize={11} tickLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: "#111827", borderColor: "#374151", borderRadius: "12px" }}
                  />
                  <Bar dataKey="Count" fill="#2563EB" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Semantic Vocabulary Table */}
      <div className="bg-[#111827]/40 border border-gray-800/80 rounded-3xl overflow-hidden backdrop-blur-md">
        <div className="p-6 border-b border-gray-800">
          <h3 className="text-base font-bold text-gray-200">
            🔍 Dynamic Vocabulary & Accommodation Logs
          </h3>
          <p className="text-xs text-gray-500 mt-1">
            Dynamic detection records of Dravidian code-switching and Gen-Z tech terms analyzed in real-time.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-[#111827]/80 text-gray-400 text-xs font-semibold tracking-wider uppercase border-b border-gray-800">
                <th className="py-4 px-6">Agent Name</th>
                <th className="py-4 px-6">Channel</th>
                <th className="py-4 px-6 text-center">Reg. Count</th>
                <th className="py-4 px-6 text-center">Cosmo Count</th>
                <th className="py-4 px-6">Identified Regional Terms</th>
                <th className="py-4 px-6">Identified Cosmopolitan Terms</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60 text-sm">
              {data?.evaluations.map((item, index) => (
                <tr key={index} className="hover:bg-gray-800/20 transition">
                  <td className="py-4 px-6 font-semibold text-gray-200">{item.agent_name}</td>
                  <td className="py-4 px-6">
                    <span className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium border ${
                      item.channel_name === "Global_Square" 
                        ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
                        : item.channel_name.includes("Tier2")
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                        : "bg-violet-500/10 text-violet-400 border-violet-500/20"
                    }`}>
                      {item.channel_name}
                    </span>
                  </td>
                  <td className="py-4 px-6 text-center font-bold text-emerald-400">{item.regional_term_count}</td>
                  <td className="py-4 px-6 text-center font-bold text-violet-400">{item.cosmopolitan_term_count}</td>
                  <td className="py-4 px-6 text-gray-400 font-mono text-xs">
                    {item.identified_regional_terms.length > 0 
                      ? item.identified_regional_terms.join(", ") 
                      : <span className="text-gray-600">-</span>}
                  </td>
                  <td className="py-4 px-6 text-gray-400 font-mono text-xs">
                    {item.identified_cosmo_terms.length > 0 
                      ? item.identified_cosmo_terms.join(", ") 
                      : <span className="text-gray-600">-</span>}
                  </td>
                </tr>
              ))}
              {!data?.evaluations.length && (
                <tr>
                  <td colSpan={6} className="py-8 px-6 text-center text-gray-500">
                    No simulation analysis data available. Run your simulation and execute analytics.py.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
