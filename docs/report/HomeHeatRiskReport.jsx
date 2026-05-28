import React, { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
    ThermometerSun, Home, Building2, Wind, Trees,
    ShieldCheck, HelpCircle, MapPin, BarChart3, CloudSun, Users, Zap
} from "lucide-react";
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
    Cell, PieChart, Pie
} from "recharts";

const riskData = [
  { area: "Westminster", score: 61.2, tier: "High" },
  { area: "Haringey", score: 60.0, tier: "High" },
  { area: "Camden", score: 59.4, tier: "Medium" },
  { area: "Wandsworth", score: 58.6, tier: "Medium" },
  { area: "Brent", score: 58.5, tier: "Medium" },
  { area: "Nottingham", score: 48.4, tier: "Medium" },
  ];

const dataSources = [
  { name: "Weather", value: 30, icon: CloudSun, label: "How hot the area gets" },
  { name: "Homes", value: 25, icon: Home, label: "Flats, EPC and building type" },
  { name: "People", value: 25, icon: Users, label: "Renting, age and vulnerability" },
  { name: "Density", value: 10, icon: Building2, label: "How crowded the area is" },
  { name: "Carbon", value: 10, icon: Zap, label: "How clean electricity is" },
  ];

const sourceQuality = [
  { name: "Real EPC", value: 37 },
  { name: "Low coverage fallback", value: 1 },
  { name: "No EPC fallback", value: 3 },
  ];

function Badge({ children, tone = "neutral" }) {
    const styles = {
          green: "bg-emerald-100 text-emerald-800 border-emerald-200",
          amber: "bg-amber-100 text-amber-900 border-amber-200",
          red: "bg-rose-100 text-rose-800 border-rose-200",
          blue: "bg-sky-100 text-sky-800 border-sky-200",
          neutral: "bg-slate-100 text-slate-700 border-slate-200",
    };
    return (
          <span className={`inline-flex items-center rounded-full border px-3 py-1 text-sm font-medium ${styles[tone]}`}>
            {children}
          </span>span>
        );
}

function Card({ children, className = "" }) {
    return (
          <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm ${className}`}>
            {children}
          </div>div>
        );
}

function SimpleHouse({ heatLevel }) {
    const glow =
          heatLevel > 70
        ? "shadow-[0_0_60px_rgba(251,146,60,0.55)]"
            : heatLevel > 45
        ? "shadow-[0_0_40px_rgba(250,204,21,0.35)]"
            : "shadow-[0_0_25px_rgba(56,189,248,0.25)]";
    return (
          <div className="relative flex h-64 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-50 via-orange-50 to-rose-50 overflow-hidden">
                <motion.div
                          animate={{ y: [0, -8, 0], rotate: [0, 1.5, 0] }}
                          transition={{ repeat: Infinity, duration: 5 }}
                          className={`absolute right-8 top-8 flex h-20 w-20 items-center justify-center rounded-full bg-orange-300 ${glow}`}
                        >
                        <ThermometerSun className="h-10 w-10 text-orange-900" />
                </motion.div>motion.div>
                <motion.div initial={{ scale: 0.95 }} animate={{ scale: 1 }} className="relative">
                        <div className="mx-auto h-0 w-0 border-l-[90px] border-r-[90px] border-b-[70px] border-l-transparent border-r-transparent border-b-slate-700" />
                        <div className="mx-auto grid h-28 w-44 grid-cols-2 gap-4 rounded-b-xl bg-slate-200 p-5 shadow-lg">
                                  <div className="rounded-lg bg-sky-200" />
                                  <div className="rounded-lg bg-orange-200" />
                                  <div className="rounded-lg bg-orange-100" />
                                  <div className="rounded-lg bg-sky-100" />
                        </div>div>
                </motion.div>motion.div>
                <motion.div
                          animate={{ x: [-25, 35, -25] }}
                          transition={{ repeat: Infinity, duration: 6 }}
                          className="absolute bottom-8 left-8 flex items-center gap-2 rounded-full bg-white/80 px-4 py-2 text-sm shadow-sm"
                        >
                        <Wind className="h-4 w-4" /> Passive cooling helps, but may not be enough
                </motion.div>motion.div>
          </div>div>
        );
}

function Quiz() {
    const [answer, setAnswer] = useState(null);
    return (
          <Card>
                <div className="flex items-start gap-3">
                        <HelpCircle className="mt-1 h-6 w-6 text-sky-600" />
                        <div>
                                  <h3 className="text-lg font-bold text-slate-900">Mini quiz</h3>h3>
                                  <p className="mt-1 text-slate-600">Which home is usually more likely to overheat in a heatwave?</p>p>
                                  <div className="mt-4 grid gap-3 sm:grid-cols-3">
                                    {[
            { id: "flat", label: "Top-floor flat", correct: true },
            { id: "detached", label: "Detached house with garden", correct: false },
            { id: "shaded", label: "Shaded house near trees", correct: false },
                        ].map((opt) => (
                                        <button
                                                          key={opt.id}
                                                          onClick={() => setAnswer(opt)}
                                                          className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left font-medium hover:bg-sky-50"
                                                        >
                                          {opt.label}
                                        </button>button>
                                      ))}
                                  </div>div>
                          {answer && (
                        <motion.div
                                        initial={{ opacity: 0, y: 8 }}
                                        animate={{ opacity: 1, y: 0 }}
                                        className="mt-4 rounded-xl bg-slate-50 p-4"
                                      >
                          {answer.correct ? (
                                                        <p className="text-emerald-800">
                                                                          <strong>Correct.</strong>strong> Top-floor flats can collect heat from the sun and may be harder to cool at night.
                                                        </p>p>
                                                      ) : (
                                                        <p className="text-amber-900">
                                                                          <strong>Good guess.</strong>strong> In this project, top-floor flats are usually more heat-risky because they can trap heat and have less cooling space.
                                                        </p>p>
                                      )}
                        </motion.div>motion.div>
                      )}
                        </div>div>
                </div>div>
          </Card>Card>
        );
}

export default function HomeHeatRiskReport() {
    const [tab, setTab] = useState("story");
    const [selectedArea, setSelectedArea] = useState(riskData[0]);
    const [property, setProperty] = useState("flat");
    const [floor, setFloor] = useState("top");
    const [hasAC, setHasAC] = useState("no");
  
    const demoRisk = useMemo(() => {
          let score = selectedArea.score;
          if (property === "flat") score += 10;
          if (floor === "top") score += 8;
          if (hasAC === "no") score += 5;
          return Math.min(100, Math.round(score));
    }, [selectedArea, property, floor, hasAC]);
  
    const riskTone = demoRisk >= 70 ? "red" : demoRisk >= 55 ? "amber" : "green";
  
    return (
          <div className="min-h-screen bg-slate-50 p-4 text-slate-900 sm:p-8">
                <div className="mx-auto max-w-6xl">
                
                  {/* Header */}
                        <motion.div
                                    initial={{ opacity: 0, y: 14 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    className="rounded-3xl bg-gradient-to-br from-slate-900 via-slate-800 to-sky-900 p-8 text-white shadow-xl"
                                  >
                                  <div className="flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
                                              <div>
                                                            <div className="mb-3 flex flex-wrap gap-2">
                                                                            <Badge tone="blue">Portfolio project</Badge>Badge>
                                                                            <Badge tone="green">Climate + AI</Badge>Badge>
                                                                            <Badge tone="amber">London + Nottingham MVP</Badge>Badge>
                                                            </div>div>
                                                            <h1 className="text-4xl font-black tracking-tight sm:text-5xl">Home Heat Risk AI</h1>h1>
                                                            <p className="mt-4 max-w-2xl text-lg text-slate-200">
                                                                            A child-friendly report about an app that asks: "Which homes might get too hot, and what can we do about it?"
                                                            </p>p>
                                              </div>div>
                                              <div className="rounded-2xl bg-white/10 p-5 backdrop-blur">
                                                            <div className="text-sm text-slate-200">Simple idea</div>div>
                                                            <div className="mt-2 text-3xl font-black">Heat risk score</div>div>
                                                            <div className="mt-2 text-slate-200">0 = cooler · 100 = more risky</div>div>
                                              </div>div>
                                  </div>div>
                        </motion.div>motion.div>
                
                  {/* Tab nav */}
                        <div className="mt-6 grid gap-3 sm:grid-cols-4">
                          {[
                        ["story", "The story", ThermometerSun],
                        ["data", "The data", BarChart3],
                        ["app", "Try it", MapPin],
                        ["honesty", "Limitations", ShieldCheck],
                      ].map(([id, label, Icon]) => (
                                    <button
                                                    key={id}
                                                    onClick={() => setTab(id)}
                                                    className={`flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 font-bold transition ${
                                                                      tab === id ? "border-sky-300 bg-white shadow-sm" : "border-slate-200 bg-slate-100 hover:bg-white"
                                                    }`}
                                                  >
                                                  <Icon className="h-5 w-5" /> {label}
                                    </button>button>
                                  ))}
                        </div>div>
                
                  {/* Story tab */}
                  {tab === "story" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 grid gap-6 lg:grid-cols-2">
                                  <Card>
                                                <h2 className="text-2xl font-black">Imagine your home is like a lunchbox</h2>h2>
                                                <p className="mt-3 text-lg leading-8 text-slate-700">
                                                                In winter, we want homes to keep heat inside, like a warm lunchbox. But in a heatwave, that same home can trap heat when we want it to escape.
                                                </p>p>
                                                <div className="mt-5 grid gap-3">
                                                                <div className="flex gap-3 rounded-xl bg-orange-50 p-4">
                                                                                  <ThermometerSun className="h-6 w-6 text-orange-700" />
                                                                                  <span><strong>Hot days</strong>strong> make homes heat up.</span>span>
                                                                </div>div>
                                                                <div className="flex gap-3 rounded-xl bg-sky-50 p-4">
                                                                                  <Wind className="h-6 w-6 text-sky-700" />
                                                                                  <span><strong>Cool nights</strong>strong> help homes breathe out heat.</span>span>
                                                                </div>div>
                                                                <div className="flex gap-3 rounded-xl bg-emerald-50 p-4">
                                                                                  <Trees className="h-6 w-6 text-emerald-700" />
                                                                                  <span><strong>Trees and shade</strong>strong> can help protect people.</span>span>
                                                                </div>div>
                                                </div>div>
                                  </Card>Card>
                                  <SimpleHouse heatLevel={demoRisk} />
                                  <Quiz />
                                  <Card>
                                                <h3 className="text-xl font-black">What makes this project creative?</h3>h3>
                                                <p className="mt-3 leading-7 text-slate-700">
                                                                It connects things that are usually separate: weather, buildings, people, energy, and fairness. It does not just say "buy air conditioning". It asks what kind of help each area might need first.
                                                </p>p>
                                  </Card>Card>
                      </motion.div>motion.div>
                    )}
                
                  {/* Data tab */}
                  {tab === "data" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 grid gap-6 lg:grid-cols-2">
                                  <Card>
                                                <h2 className="text-2xl font-black">The app uses different clues</h2>h2>
                                                <p className="mt-2 text-slate-600">Like a detective, it collects clues and turns them into one heat-risk score.</p>p>
                                                <div className="mt-6 h-72">
                                                                <ResponsiveContainer width="100%" height="100%">
                                                                                  <BarChart data={dataSources} layout="vertical" margin={{ left: 35 }}>
                                                                                                      <XAxis type="number" hide />
                                                                                                      <YAxis dataKey="name" type="category" width={75} />
                                                                                                      <Tooltip />
                                                                                                      <Bar dataKey="value" radius={[0, 10, 10, 0]}>
                                                                                                        {dataSources.map((_, index) => <Cell key={index} />)}
                                                                                                        </Bar>Bar>
                                                                                    </BarChart>BarChart>
                                                                </ResponsiveContainer>ResponsiveContainer>
                                                </div>div>
                                  </Card>Card>
                                  <Card>
                                                <h2 className="text-2xl font-black">EPC data quality check</h2>h2>
                                                <p className="mt-2 text-slate-600">Most areas use real EPC data. A few use a safe fallback because there were too few certificates.</p>p>
                                                <div className="mt-6 h-72">
                                                                <ResponsiveContainer width="100%" height="100%">
                                                                                  <PieChart>
                                                                                                      <Pie data={sourceQuality} dataKey="value" nameKey="name" outerRadius={95} label />
                                                                                                      <Tooltip />
                                                                                    </PieChart>PieChart>
                                                                </ResponsiveContainer>ResponsiveContainer>
                                                </div>div>
                                                <div className="mt-4 flex flex-wrap gap-2">
                                                                <Badge tone="green">37 real</Badge>Badge>
                                                                <Badge tone="amber">1 low coverage fallback</Badge>Badge>
                                                                <Badge tone="neutral">3 no coverage fallback</Badge>Badge>
                                                </div>div>
                                  </Card>Card>
                                  <Card className="lg:col-span-2">
                                                <h2 className="text-2xl font-black">Top areas in the demo</h2>h2>
                                                <div className="mt-6 h-80">
                                                                <ResponsiveContainer width="100%" height="100%">
                                                                                  <BarChart data={riskData} margin={{ top: 20, right: 20, left: 0, bottom: 30 }}>
                                                                                                      <XAxis dataKey="area" angle={-20} textAnchor="end" height={60} />
                                                                                                      <YAxis domain={[0, 70]} />
                                                                                                      <Tooltip />
                                                                                                      <Bar dataKey="score" radius={[10, 10, 0, 0]} />
                                                                                    </BarChart>BarChart>
                                                                </ResponsiveContainer>ResponsiveContainer>
                                                </div>div>
                                  </Card>Card>
                      </motion.div>motion.div>
                    )}
                
                  {/* Try it tab */}
                  {tab === "app" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 grid gap-6 lg:grid-cols-2">
                                  <Card>
                                                <h2 className="text-2xl font-black">Try a pretend home</h2>h2>
                                                <p className="mt-2 text-slate-600">This is a simple child-friendly version of the app idea.</p>p>
                                                <label className="mt-5 block text-sm font-bold">Choose area</label>label>
                                                <select
                                                                  className="mt-2 w-full rounded-xl border border-slate-200 p-3"
                                                                  value={selectedArea.area}
                                                                  onChange={(e) => setSelectedArea(riskData.find((d) => d.area === e.target.value))}
                                                                >
                                                  {riskData.map((d) => <option key={d.area}>{d.area}</option>option>)}
                                                </select>select>
                                                <label className="mt-4 block text-sm font-bold">Home type</label>label>
                                                <select className="mt-2 w-full rounded-xl border border-slate-200 p-3" value={property} onChange={(e) => setProperty(e.target.value)}>
                                                                <option value="flat">Flat</option>option>
                                                                <option value="house">House</option>option>
                                                </select>select>
                                                <label className="mt-4 block text-sm font-bold">Floor</label>label>
                                                <select className="mt-2 w-full rounded-xl border border-slate-200 p-3" value={floor} onChange={(e) => setFloor(e.target.value)}>
                                                                <option value="top">Top floor</option>option>
                                                                <option value="middle">Middle floor</option>option>
                                                                <option value="ground">Ground floor</option>option>
                                                </select>select>
                                                <label className="mt-4 block text-sm font-bold">Air conditioning?</label>label>
                                                <select className="mt-2 w-full rounded-xl border border-slate-200 p-3" value={hasAC} onChange={(e) => setHasAC(e.target.value)}>
                                                                <option value="no">No</option>option>
                                                                <option value="yes">Yes</option>option>
                                                </select>select>
                                  </Card>Card>
                                  <Card>
                                                <h2 className="text-2xl font-black">Result</h2>h2>
                                                <div className="mt-5 rounded-3xl bg-slate-50 p-6 text-center">
                                                                <div className="text-sm font-bold uppercase tracking-wide text-slate-500">Heat risk score</div>div>
                                                                <div className="mt-2 text-6xl font-black">{demoRisk}</div>div>
                                                                <div className="mt-3">
                                                                                  <Badge tone={riskTone}>
                                                                                    {demoRisk >= 70 ? "High risk" : demoRisk >= 55 ? "Medium risk" : "Lower risk"}
                                                                                    </Badge>Badge>
                                                                </div>div>
                                                </div>div>
                                                <div className="mt-5 space-y-3 text-slate-700">
                                                                <p><strong>What to try first:</strong>strong> shade windows, close curtains on hot days, open windows at cooler night times if safe.</p>p>
                                                                <p><strong>If still too hot:</strong>strong> consider fans, ventilation upgrades, or efficient cooling support.</p>p>
                                                                <p><strong>Important:</strong>strong> this is an area-level estimate, not a diagnosis of one exact home.</p>p>
                                                </div>div>
                                  </Card>Card>
                      </motion.div>motion.div>
                    )}
                
                  {/* Limitations tab */}
                  {tab === "honesty" && (
                      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 grid gap-6 md:grid-cols-3">
                                  <Card>
                                                <ShieldCheck className="h-8 w-8 text-emerald-700" />
                                                <h3 className="mt-3 text-xl font-black">What is strong</h3>h3>
                                                <p className="mt-2 text-slate-700">The project is clear, timely, useful, and honest about its limits. It has a working app and real data sources.</p>p>
                                  </Card>Card>
                                  <Card>
                                                <HelpCircle className="h-8 w-8 text-amber-700" />
                                                <h3 className="mt-3 text-xl font-black">What is not perfect yet</h3>h3>
                                                <p className="mt-2 text-slate-700">It does not measure exact indoor temperatures. Daily HadUK-Grid data is still a future upgrade.</p>p>
                                  </Card>Card>
                                  <Card>
                                                <BarChart3 className="h-8 w-8 text-sky-700" />
                                                <h3 className="mt-3 text-xl font-black">Why it is professional</h3>h3>
                                                <p className="mt-2 text-slate-700">It includes methodology, data dictionary, responsible AI notes, and explains when data is real or fallback.</p>p>
                                  </Card>Card>
                                  <Card className="md:col-span-3">
                                                <h2 className="text-2xl font-black">Final simple summary</h2>h2>
                                                <p className="mt-3 text-lg leading-8 text-slate-700">
                                                                This app is like a heat detective for homes. It looks at weather, buildings, people and energy, then says which areas may need help staying safe and cool. It is not magic, and it is not a final government tool, but it is a strong portfolio project because it solves a real problem in a careful way.
                                                </p>p>
                                  </Card>Card>
                      </motion.div>motion.div>
                    )}
                
                </div>div>
          </div>div>
        );
}</div>
