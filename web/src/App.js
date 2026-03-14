import React, { useState, useEffect, useMemo } from 'react';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import { Shield, Brain, TrendingUp, Activity, AlertTriangle, CheckCircle } from 'lucide-react';

const Dashboard = () => {
  const [ticks, setTicks] = useState([]);
  const [agentSignals, setAgentSignals] = useState([]);
  const [consensus, setConsensus] = useState(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    const ws = new WebSocket(`wss://khaval-gateway-v3.onrender.com/ws`);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.stream === 'market:data:stream') {
        const payload = JSON.parse(msg.data.payload);
        setTicks(prev => [...prev.slice(-49), { time: new Date().toLocaleTimeString(), price: payload.price }]);
      } else if (msg.stream === 'agent:signals:stream') {
        setAgentSignals(prev => [msg.data, ...prev.slice(0, 9)]);
      } else if (msg.stream === 'execution:signal:stream') {
        setConsensus(msg.data);
      }
    };

    return () => ws.close();
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 text-slate-100 p-6 font-sans">
      {/* Header */}
      <div className="flex justify-between items-center mb-8 border-b border-slate-700 pb-4">
        <div className="flex items-center gap-3">
          <TrendingUp className="text-emerald-400 w-8 h-8" />
          <h1 className="text-2xl font-bold tracking-tight">KhayaL Al Trade <span className="text-slate-500 text-sm font-normal tracking-normal ml-2">v3.0</span></h1>
        </div>
        <div className="flex items-center gap-4">
          <div className="px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-xs flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`}></div>
            {connected ? 'LIVE' : 'DISCONNECTED'}
          </div>
          <div className="px-3 py-1 rounded-full bg-amber-500/10 border border-amber-500/50 text-amber-500 text-xs font-bold">
            PAPER TRADING MODE
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6">
        {/* Main Chart */}
        <div className="col-span-8 bg-slate-800/50 border border-slate-700 rounded-xl p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-sm font-semibold text-slate-400 flex items-center gap-2 uppercase tracking-wider">
              <Activity className="w-4 h-4" /> Real-time Market Feed
            </h2>
            <div className="text-xl font-mono text-emerald-400">
              ${ticks[ticks.length - 1]?.price.toFixed(2) || '0.00'}
            </div>
          </div>
          <div className="h-[300px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={ticks}>
                <XAxis dataKey="time" hide />
                <YAxis domain={['auto', 'auto']} hide />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', color: '#f8fafc' }}
                  itemStyle={{ color: '#34d399' }}
                />
                <Line type="monotone" dataKey="price" stroke="#10b981" strokeWidth={2} dot={false} animationDuration={300} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Consensus / The Judge */}
        <div className="col-span-4 bg-slate-800 border-2 border-emerald-500/30 rounded-xl p-6 shadow-lg shadow-emerald-500/5">
          <h2 className="text-sm font-semibold text-slate-400 flex items-center gap-2 uppercase tracking-wider mb-6">
            <Brain className="w-5 h-5 text-emerald-400" /> Consensus Judge
          </h2>
          {consensus ? (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <span className={`text-3xl font-black ${consensus.decision === 'CALL' ? 'text-emerald-500' : 'text-rose-500'}`}>
                  {consensus.decision}
                </span>
                <div className="text-right">
                  <div className="text-xs text-slate-500">CONFIDENCE</div>
                  <div className="text-xl font-bold">{(consensus.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>
              <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700 italic text-slate-300 text-sm leading-relaxed">
                "{consensus.reasoning}"
              </div>
              <div className="flex items-center gap-2 text-xs text-emerald-400 font-bold bg-emerald-500/10 p-2 rounded">
                <Shield className="w-4 h-4" /> RISK GATEKEEPER: VERIFIED
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center text-slate-500 py-12">
              <div className="w-8 h-8 border-2 border-slate-700 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
              Waiting for consensus...
            </div>
          )}
        </div>

        {/* Agent Debates */}
        <div className="col-span-12">
          <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Agent Signals</h2>
          <div className="grid grid-cols-3 gap-6">
            {['technical', 'news', 'sentiment'].map(agentType => {
              const lastSignal = agentSignals.find(s => s.agent === agentType);
              return (
                <div key={agentType} className="bg-slate-800/50 border border-slate-700 rounded-xl p-5">
                  <div className="flex justify-between items-center mb-4">
                    <span className="text-xs font-bold text-slate-500 uppercase">{agentType} Agent</span>
                    {lastSignal ? (
                      <span className={`text-xs font-bold px-2 py-0.5 rounded ${lastSignal.signal.includes('BUY') ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'}`}>
                        {lastSignal.signal}
                      </span>
                    ) : <span className="text-xs text-slate-600">WAITING...</span>}
                  </div>
                  <p className="text-xs text-slate-400 line-clamp-3">
                    {lastSignal?.reasoning || 'Analyzing market patterns and streaming data...'}
                  </p>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
