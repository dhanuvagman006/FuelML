import React, { useState, useEffect, useRef } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, LineChart, Line, Area, AreaChart
} from 'recharts';
import {
  FlaskConical, Gauge, Droplets, Thermometer, Flame,
  MessageCircle, Send, Zap, Activity, RotateCcw,
  Cpu, CheckCircle2, AlertCircle, Beaker, Wind,
  TrendingUp, TrendingDown, Minus
} from 'lucide-react';
import './App.css';

/* ── Constants ─────────────────────────────────────────────── */
const BASE_DIESEL = {
  BTE: 30.0, BSFC: 250.0, NOx: 500.0,
  Smoke: 40.0, Thrust: 10.0, SFC: 15.0, EGT: 600.0
};

const FUEL_CONFIG = {
  Diesel_pct: { label: 'Diesel', color: '#2563eb', bg: '#eff6ff', gradFrom: '#2563eb', gradTo: '#60a5fa' },
  Coconut_pct: { label: 'Coconut Oil', color: '#059669', bg: '#ecfdf5', gradFrom: '#059669', gradTo: '#34d399' },
  Castor_pct: { label: 'Castor Oil', color: '#7c3aed', bg: '#f5f3ff', gradFrom: '#7c3aed', gradTo: '#a78bfa' },
  IPA_pct: { label: 'IPA', color: '#ea580c', bg: '#fff7ed', gradFrom: '#ea580c', gradTo: '#fb923c' },
};

/* ── Trend Icon ────────────────────────────────────────────── */
const TrendIcon = ({ val, base, positiveIsGood = true }) => {
  const delta = val - base;
  const pct = ((delta / base) * 100).toFixed(1);
  const isGood = positiveIsGood ? delta > 0 : delta < 0;
  if (Math.abs(delta) < 0.5) return <span style={{ color: '#94a3b8', fontSize: 11, display: 'flex', alignItems: 'center', gap: 2 }}><Minus size={12} /> 0%</span>;
  return (
    <span style={{ color: isGood ? '#16a34a' : '#dc2626', fontSize: 11, fontWeight: 700, display: 'flex', alignItems: 'center', gap: 2 }}>
      {delta > 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
      {delta > 0 ? '+' : ''}{pct}%
    </span>
  );
};

/* ── Custom Tooltip ────────────────────────────────────────── */
const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#fff',
      border: '1px solid #e4e9f2',
      borderRadius: 12,
      padding: '11px 15px',
      boxShadow: '0 8px 30px rgba(13,27,46,0.12)',
      fontFamily: 'Inter, Outfit, sans-serif',
      fontSize: 13,
      minWidth: 168
    }}>
      <p style={{ fontWeight: 700, color: '#0d1b2e', marginBottom: 8, fontSize: 12 }}>{label}</p>
      {payload.map((entry, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: entry.fill, flexShrink: 0 }} />
          <span style={{ color: '#8494a9', flex: 1 }}>{entry.name}:</span>
          <span style={{ color: '#0d1b2e', fontWeight: 700, fontFamily: 'JetBrains Mono, monospace' }}>
            {typeof entry.value === 'number' ? entry.value.toFixed(2) : entry.value}
          </span>
        </div>
      ))}
    </div>
  );
};

/* ── Main App ───────────────────────────────────────────────── */
export default function App() {
  const [blend, setBlend] = useState({
    Diesel_pct: 100, Coconut_pct: 0, Castor_pct: 0, IPA_pct: 0
  });
  const [predictions, setPredictions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [chatMessages, setChatMessages] = useState([{
    text: "Hello! I'm your AI Biofuel expert. Try asking: \"What happens if I use 20% Castor oil and 5% IPA?\"",
    sender: 'bot'
  }]);
  const [chatInput, setChatInput] = useState('');
  const messagesEndRef = useRef(null);

  const total = Object.values(blend).reduce((a, b) => a + b, 0);
  const isValid = Math.abs(total - 100) < 0.1;

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleSliderChange = (fuel, value) =>
    setBlend(prev => ({ ...prev, [fuel]: parseFloat(value) }));

  const handleReset = () => {
    setBlend({ Diesel_pct: 100, Coconut_pct: 0, Castor_pct: 0, IPA_pct: 0 });
    setPredictions(null);
  };

  const handlePredict = async () => {
    if (!isValid) return;
    setLoading(true);
    try {
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(blend)
      });
      const data = await res.json();
      setPredictions(data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  const handleChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    const userMsg = chatInput;
    setChatMessages(prev => [...prev, { text: userMsg, sender: 'user' }]);
    setChatInput('');
    try {
      const res = await fetch('/api/chatbot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: userMsg })
      });
      const data = await res.json();
      setChatMessages(prev => [...prev, { text: data.response, sender: 'bot' }]);
      if (data.parsed_blend) {
        setBlend(data.parsed_blend);
        if (data.predictions) setPredictions(data.predictions);
      }
    } catch {
      setChatMessages(prev => [...prev, {
        text: 'Error connecting to AI. Please ensure the backend server is running.',
        sender: 'bot'
      }]);
    }
  };

  const getChartData = () => {
    if (!predictions) return [];
    return [
      { metric: 'BTE (%)', Diesel: BASE_DIESEL.BTE, Blend: +predictions.ic_engine_predictions.BTE_pct.toFixed(2) },
      { metric: 'BSFC', Diesel: BASE_DIESEL.BSFC, Blend: +predictions.ic_engine_predictions.BSFC_gkWh.toFixed(2) },
      { metric: 'Smoke (%)', Diesel: BASE_DIESEL.Smoke, Blend: +predictions.ic_engine_predictions.Smoke_Opacity_pct.toFixed(2) },
      { metric: 'Thrust (kN)', Diesel: BASE_DIESEL.Thrust, Blend: +predictions.jet_engine_predictions.Thrust_kN.toFixed(2) },
    ];
  };

  const getEmissionsData = () => {
    if (!predictions) return [];
    return [
      { metric: 'NOx (ppm)', Diesel: BASE_DIESEL.NOx, Blend: +predictions.ic_engine_predictions.NOx_ppm.toFixed(2) },
      { metric: 'EGT (°C)', Diesel: BASE_DIESEL.EGT, Blend: +predictions.jet_engine_predictions.EGT_C.toFixed(2) },
    ];
  };

  const AXIS_TICK = { fill: '#8494a9', fontSize: 11, fontFamily: 'Inter, Outfit, sans-serif' };
  const GRID_STROKE = '#f0f2f7';
  const CHART_MARGIN = { top: 8, right: 12, left: -8, bottom: 0 };
  const LEGEND_STYLE = { fontSize: 12, fontFamily: 'Inter, Outfit, sans-serif', color: '#8494a9', paddingTop: 10 };

  return (
    <div className="dashboard-container">

      {/* ══════════════ SIDEBAR ══════════════ */}
      <aside className="sidebar">
        <div className="sidebar-top">
          {/* Brand */}
          <div className="sidebar-brand">
            <div className="brand-icon-wrap">
              <FlaskConical size={20} strokeWidth={2.5} />
            </div>
            <div className="brand-text">
              <span className="brand-name">FuelML</span>
              <span className="brand-tagline">Biofuel AI Optimizer</span>
            </div>
          </div>

          <div className="section-label" style={{ marginTop: 0 }}>Blend Configuration</div>
        </div>

        <div className="sidebar-scroll">
          {/* Fuel Sliders */}
          <div className="fuel-sliders">
            {Object.entries(FUEL_CONFIG).map(([key, cfg]) => (
              <div className="input-group" key={key}>
                <div className="slider-header">
                  <div className="fuel-name-wrap">
                    <span className="fuel-dot" style={{ background: cfg.color }} />
                    <span className="fuel-name-text">{cfg.label}</span>
                  </div>
                  <span className="fuel-badge">{blend[key].toFixed(1)}%</span>
                </div>
                <div className="slider-track-wrap">
                  <div
                    className="slider-fill"
                    style={{
                      width: `${blend[key]}%`,
                      background: `linear-gradient(90deg, ${cfg.gradFrom}, ${cfg.gradTo})`
                    }}
                  />
                  <input
                    type="range"
                    className="slider"
                    min="0" max="100" step="0.5"
                    value={blend[key]}
                    style={{ '--thumb-color': cfg.color }}
                    onChange={e => handleSliderChange(key, e.target.value)}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Composition Bar */}
          <div className="composition-section">
            <div className="comp-bar-label">Composition</div>
            <div className="composition-bar">
              {Object.entries(FUEL_CONFIG).map(([key, cfg]) =>
                blend[key] > 0 ? (
                  <div
                    key={key}
                    className="comp-segment"
                    style={{
                      width: `${blend[key]}%`,
                      background: `linear-gradient(90deg, ${cfg.gradFrom}, ${cfg.gradTo})`
                    }}
                  />
                ) : null
              )}
            </div>
            <div className="comp-legend">
              {Object.entries(FUEL_CONFIG).map(([key, cfg]) =>
                blend[key] > 0 ? (
                  <div key={key} className="comp-legend-item">
                    <span className="comp-legend-dot" style={{ background: cfg.color }} />
                    {cfg.label} {blend[key].toFixed(1)}%
                  </div>
                ) : null
              )}
            </div>
          </div>

          {/* Blend validity */}
          <div className={`blend-status ${isValid ? 'valid' : 'invalid'}`}>
            <div className="blend-status-left">
              {isValid
                ? <CheckCircle2 size={15} />
                : <AlertCircle size={15} />
              }
              {isValid ? 'Valid blend' : 'Invalid blend'}
            </div>
            <span className="blend-total-val">{total.toFixed(1)}%</span>
          </div>
          {!isValid && (
            <div className="blend-hint">Total must equal exactly 100%</div>
          )}
        </div>

        {/* Footer buttons */}
        <div className="sidebar-footer">
          <button
            className="run-btn"
            onClick={handlePredict}
            disabled={!isValid || loading}
            id="run-btn-main"
          >
            {loading
              ? <><div className="spinner" /> Analyzing...</>
              : <><Zap size={15} strokeWidth={2.5} /> Run</>
            }
          </button>
          <button
            className="reset-btn"
            onClick={handleReset}
            id="reset-btn"
          >
            <RotateCcw size={13} /> Reset to Default
          </button>
        </div>
      </aside>

      {/* ══════════════ MAIN CONTENT ══════════════ */}
      <main className="main-content">
        {/* Top bar */}
        <div className="topbar">
          <div className="topbar-left">
            <h1>Engine Performance Analysis</h1>
            <p>Real-time ML predictions &nbsp;·&nbsp; IC Engine &amp; Jet Engine &nbsp;·&nbsp; vs. Diesel Baseline</p>
          </div>
          <div className="topbar-right">
            <div className="status-badge">
              <span className="status-dot" />
              ML Models Active
            </div>
          </div>
        </div>

        {predictions ? (
          <>
            {/* Metric Cards */}
            <div className="metrics-grid">
              <div className="metric-card card-cyan">
                <div className="metric-icon" style={{ background: '#eff6ff' }}>
                  <Droplets size={18} style={{ color: '#2563eb' }} />
                </div>
                <div>
                  <div className="metric-label">Viscosity</div>
                  <div className="metric-val-row">
                    <span className="metric-value">{predictions.calculated_properties.Viscosity_cSt}</span>
                    <span className="metric-unit">cSt</span>
                  </div>
                </div>
              </div>

              <div className="metric-card card-amber">
                <div className="metric-icon" style={{ background: '#fff7ed' }}>
                  <Flame size={18} style={{ color: '#ea580c' }} />
                </div>
                <div>
                  <div className="metric-label">Flash Point</div>
                  <div className="metric-val-row">
                    <span className="metric-value">{predictions.calculated_properties.Flash_Point_C}</span>
                    <span className="metric-unit">°C</span>
                  </div>
                </div>
              </div>

              <div className="metric-card card-violet">
                <div className="metric-icon" style={{ background: '#f5f3ff' }}>
                  <Thermometer size={18} style={{ color: '#7c3aed' }} />
                </div>
                <div>
                  <div className="metric-label">Calorific Value</div>
                  <div className="metric-val-row">
                    <span className="metric-value">{predictions.calculated_properties.Calorific_Value_MJkg}</span>
                    <span className="metric-unit">MJ/kg</span>
                  </div>
                </div>
              </div>

              <div className="metric-card card-green">
                <div className="metric-icon" style={{ background: '#ecfdf5' }}>
                  <Gauge size={18} style={{ color: '#059669' }} />
                </div>
                <div>
                  <div className="metric-label">Jet Thrust</div>
                  <div className="metric-val-row">
                    <span className="metric-value">{predictions.jet_engine_predictions.Thrust_kN}</span>
                    <span className="metric-unit">kN</span>
                  </div>
                </div>
              </div>
            </div>

            {/* Charts */}
            <div className="charts-container">
              <div className="chart-card">
                <div className="chart-top">
                  <div>
                    <div className="chart-title">Efficiency &amp; Performance</div>
                    <div className="chart-desc">BTE · BSFC · Smoke Opacity · Thrust</div>
                  </div>
                  <span className="chart-tag tag-blue">
                    <Activity size={10} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                    IC + Jet
                  </span>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={getChartData()} margin={CHART_MARGIN} barCategoryGap="32%">
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRID_STROKE} />
                    <XAxis dataKey="metric" axisLine={false} tickLine={false} tick={AXIS_TICK} />
                    <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f5f7fa' }} />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={LEGEND_STYLE} />
                    <Bar dataKey="Diesel" fill="#c7d2dd" radius={[5, 5, 0, 0]} barSize={24} />
                    <Bar dataKey="Blend" fill="#2563eb" radius={[5, 5, 0, 0]} barSize={24} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              <div className="chart-card">
                <div className="chart-top">
                  <div>
                    <div className="chart-title">Emissions &amp; Temperature</div>
                    <div className="chart-desc">NOx concentration · Exhaust Gas Temperature</div>
                  </div>
                  <span className="chart-tag tag-red">
                    <Flame size={10} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
                    Emissions
                  </span>
                </div>
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={getEmissionsData()} margin={CHART_MARGIN} barCategoryGap="45%">
                    <CartesianGrid strokeDasharray="3 3" vertical={false} stroke={GRID_STROKE} />
                    <XAxis dataKey="metric" axisLine={false} tickLine={false} tick={AXIS_TICK} />
                    <YAxis axisLine={false} tickLine={false} tick={AXIS_TICK} />
                    <Tooltip content={<CustomTooltip />} cursor={{ fill: '#f5f7fa' }} />
                    <Legend iconType="circle" iconSize={8} wrapperStyle={LEGEND_STYLE} />
                    <Bar dataKey="Diesel" fill="#c7d2dd" radius={[5, 5, 0, 0]} barSize={44} />
                    <Bar dataKey="Blend" fill="#dc2626" radius={[5, 5, 0, 0]} barSize={44} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <div className="empty-icon-wrap">
              <Cpu size={28} />
            </div>
            <div className="empty-title">Ready to Simulate</div>
            <div className="empty-desc">
              Configure your biofuel blend ratios using the sliders on the left, then click
              <strong> Run</strong> for real-time AI predictions.
            </div>
            <div className="empty-steps">
              <div className="empty-step"><span className="step-num">1</span> Adjust fuel sliders</div>
              <div className="empty-step"><span className="step-num">2</span> Total must = 100%</div>
              <div className="empty-step"><span className="step-num">3</span> Click Run</div>
            </div>
          </div>
        )}
      </main>

      {/* ══════════════ CHATBOT ══════════════ */}
      <div className="chat-container">
        <div className="chat-header">
          <div className="chat-avatar">
            <MessageCircle size={15} strokeWidth={2.5} />
          </div>
          <div className="chat-header-info">
            <div className="chat-title">AI Fuel Expert</div>
            <div className="chat-online">
              <span className="chat-online-dot" /> Online · Gemini Powered
            </div>
          </div>
        </div>

        <div className="chat-messages">
          {chatMessages.map((msg, i) => (
            <div key={i} className={`msg-row ${msg.sender === 'user' ? 'user-row' : ''}`}>
              <div className={`msg-av ${msg.sender === 'bot' ? 'bot-av' : 'user-av'}`}>
                {msg.sender === 'bot' ? 'AI' : 'U'}
              </div>
              <div className={`message ${msg.sender}`}>{msg.text}</div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <form className="chat-form" onSubmit={handleChat}>
            <input
              type="text"
              className="chat-input"
              placeholder="Ask about a fuel blend..."
              value={chatInput}
              onChange={e => setChatInput(e.target.value)}
              id="chat-input"
            />
            <button type="submit" className="chat-send" id="chat-send-btn">
              <Send size={14} strokeWidth={2.5} />
            </button>
          </form>
        </div>
      </div>

    </div>
  );
}
